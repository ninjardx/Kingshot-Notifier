# -*- coding: utf-8 -*-
"""
Kingshot Bot – Bear Scheduler 
====================================================

"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, List

import discord
from discord import app_commands
from discord.ext import commands

from helpers import ensure_channel, save_config, is_installed
from config import (
    gcfg,
    BEAR_CHANNEL,
    BEAR_LOG_CHANNEL,
    BEAR_PHASE_OFFSETS,
    EMBED_COLOR_PRIMARY,
    EMBED_COLOR_INCOMING,
    EMBED_COLOR_PREATTACK,
    EMBED_COLOR_ATTACK,
    EMBED_COLOR_VICTORY,
    EMOJI_THUMBNAILS
)
from admin_tools import live_feed
from config_helpers import get_bear_ping_settings

# ────────────────────────────────────────────────────────────
# Embed Builders (copied exactly for visual parity)
# ────────────────────────────────────────────────────────────

def make_bear_welcome_embed() -> discord.Embed:
    embed = discord.Embed(
        title="<:BEAREVENT:1375520846407270561> **Bear Alerts** ",
        description=(
            "📢 **This channel posts upcoming Bear attack phases!**\n\n"
            "⏱️ **Incoming** — 60 minutes before the Bear\n"
            "<:BEAR:1375525056725258302> **Pre-Attack** — 10 minutes before impact\n"
            "<:BEARATTACKED:1375525984723275967> **Attack** — when the Bear arrives\n"
            "🏆 **Victory** — when the Bear is slain!\n\n"
            "🗓️ **Schedule** a Bear: `/setbeartime`\n"
            "📂 **Manage** Bears: `/cancelbear` / `/listbears`"
        ),
        color=EMBED_COLOR_PRIMARY,
    )
    embed.set_thumbnail(url=EMOJI_THUMBNAILS["scheduled"])
    embed.set_footer(text="👑 Kingshot Bot • Bear Alerts • UTC")
    return embed


def make_phase_embed(phase: str, epoch: int) -> discord.Embed:
    ts = epoch
    if phase == "scheduled":
        title = "<:BEAREVENT:1375520846407270561> Bear Scheduled!"
        color = EMBED_COLOR_PRIMARY
        desc = (
            f"🗓️ Bear Time: <t:{ts}:F>\n"
            f"⏳ Countdown: <t:{ts}:R>\n\n"
            "🛡️ Protect the alliance!"
        )
    elif phase == "incoming":
        title = "<:BEAREVENT:1375520846407270561> Bear Incoming!"
        color = EMBED_COLOR_INCOMING
        desc = (
            f"🗓️ Bear Time: <t:{ts}:F>\n"
            f"⏳ Countdown: <t:{ts}:R>\n\n"
            "🎯 Bear is near!\n🛡️ Protect the alliance!"
        )
    elif phase == "pre_attack":
        title = "⚔️ Prepare to Attack!"
        color = EMBED_COLOR_PREATTACK
        desc = (
            f"<:BEAR:1375525056725258302> Bear approaching, get ready!\n"
            f"🗓️ Bear Time: <t:{ts}:F>\n"
            f"⏳ Countdown: <t:{ts}:R>\n\n"
            "💥 Final prep time, \n<:chenkoavatar300x286:1375517387226484787> **CHENKO ONLY!**\n🛡️ Protect the alliance!"
        )
    elif phase == "attack":
        title = "<:BEARATTACKED:1375525984723275967> **Attack the Bear!**"
        color = EMBED_COLOR_ATTACK
        end_ts = ts + BEAR_PHASE_OFFSETS["victory"] * 60
        desc = (
            f"🗓️ Bear Began: <t:{ts}:F>\n"
            f"⏳ Bear Ends: <t:{end_ts}:R>\n\n"
            "<:chenkoavatar300x286:1375517387226484787> **CHENKO ONLY!**\n🍖 Feed the hungry bear!\n🛡️ Protect the alliance!"
        )
    else:  # victory
        title = "🏆 Victory!"
        color = EMBED_COLOR_VICTORY
        desc = (
            f"🗓️ Completed: <t:{ts}:F>\n\n"
            "🏆 The alliance stands strong.<:chenko:1375581626649546812>"
        )

    embed = discord.Embed(title=title, description=desc, color=color)
    thumbnail_url = EMOJI_THUMBNAILS.get(phase)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    embed.set_footer(text=f"👑 Kingshot Bot • Bear Phase: {phase} • UTC")
    return embed


# ────────────────────────────────────────────────────────────
# Data Model
# ────────────────────────────────────────────────────────────

class BearEvent:
    def __init__(self, guild_id: int, epoch: int, event_id: Optional[str] = None):
        self.id: str = event_id or str(uuid.uuid4())[:8]
        self.guild_id: int = guild_id
        self.epoch: int = epoch
        self.phase: str = "scheduled"
        self.message_id: Optional[int] = None
        self.task: Optional[asyncio.Task] = None


# ────────────────────────────────────────────────────────────
# Cog Definition
# ────────────────────────────────────────────────────────────

class NewBearScheduler(commands.Cog):
    """Schedules Bear attacks with reliable phase transitions and minimal JSON writes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.events: Dict[str, BearEvent] = {}
        # Load existing bears on startup
        asyncio.create_task(self._startup_sync())

    async def _startup_sync(self):
        await self.bot.wait_until_ready()
        now = int(time.time())

        for guild in self.bot.guilds:
            # Skip if guild is not installed
            if not is_installed(guild.id):
                continue

            cfg = gcfg.setdefault(str(guild.id), {})
            bears = cfg.setdefault("bears", [])

            # Handle cleanup of past bears that ended while bot was offline
            ch = await ensure_channel(guild, BEAR_CHANNEL)
            log_ch = await ensure_channel(guild, BEAR_LOG_CHANNEL)
            
            for bear in bears[:]:  # Create a copy to safely modify during iteration
                # Check if bear is past victory phase
                if now > bear["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60:
                    # Send victory message to log if it wasn't sent
                    await log_ch.send(embed=make_phase_embed("victory", bear["epoch"]))
                    dt = datetime.fromtimestamp(bear["epoch"], tz=timezone.utc)
                    live_feed.log(
                        "Cleaned up past bear (offline completion)",
                        f"Bear ID: {bear['id']} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        guild,
                        ch
                    )
                    
                    # Clean up the bear message if it exists
                    if bear.get("message_id"):
                        try:
                            msg = await ch.fetch_message(bear["message_id"])
                            await msg.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass
                    
                    # Clean up any remaining pings
                    await self._cleanup_pings(ch)
                    
                    # Remove from bears list
                    bears.remove(bear)
            
            # Save config after cleanup
            save_config(gcfg)

            if not bears:
                continue

            # Pick next-soonest bear that hasn't reached victory
            active_bears = [b for b in bears if now <= b["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60]
            if active_bears:
                next_entry = min(active_bears, key=lambda b: b["epoch"])
                ev = BearEvent(guild.id, next_entry["epoch"], next_entry["id"])
                ev.message_id = next_entry.get("message_id")
                self.events[ev.id] = ev
                # Kick off processing
                ev.task = asyncio.create_task(self._run_event_cycle(ev))
                dt = datetime.fromtimestamp(ev.epoch, tz=timezone.utc)
                live_feed.log(
                    "Started bear on bot startup",
                    f"Bear ID: {ev.id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    guild,
                    ch
                )

    # ────────────── Core Event Loop ──────────────

    async def _run_event_cycle(self, ev: BearEvent):
        guild = self.bot.get_guild(ev.guild_id)
        if not guild:
            return
        ch = await ensure_channel(guild, BEAR_CHANNEL)

        # Get ping settings for this guild
        ping_settings = get_bear_ping_settings(str(ev.guild_id))

        # Determine current phase and ensure we're in the correct phase
        now = int(time.time())
        current_phase = self._calc_phase(now, ev.epoch)
        ev.phase = current_phase

        # If we're past victory, clean up and exit
        if current_phase == "victory":
            # Post to log channel
            log_ch = await ensure_channel(guild, BEAR_LOG_CHANNEL)
            await log_ch.send(embed=make_phase_embed("victory", ev.epoch))
            # Clean up
            if ev.message_id:
                try:
                    msg = await ch.fetch_message(ev.message_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            await self._cleanup_pings(ch)
            # Remove from events and config
            self.events.pop(ev.id, None)
            cfg_bears = gcfg[str(ev.guild_id)]["bears"]
            cfg_bears[:] = [b for b in cfg_bears if b["id"] != ev.id]
            save_config(gcfg)
            
            # Start next bear if exists
            guild_cfg = gcfg[str(ev.guild_id)]
            remaining = [b for b in guild_cfg.get("bears", []) 
                        if b["epoch"] > ev.epoch and 
                        now <= b["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60]
            if remaining:
                next_bear = min(remaining, key=lambda b: b["epoch"])
                next_ev = BearEvent(ev.guild_id, next_bear["epoch"], next_bear["id"])
                self.events[next_ev.id] = next_ev
                next_ev.task = asyncio.create_task(self._run_event_cycle(next_ev))
            return

        # Sync embed and ping for current phase
        await self._send_or_edit_embed(ch, ev)
        await self._cleanup_pings(ch, keep_phase=ev.phase)
        
        # Only send ping if phase is enabled in settings
        if ev.phase == "incoming" and ping_settings.incoming_enabled:
            await self._send_ping(ch, ev, ev.phase)
        elif ev.phase == "pre_attack" and ping_settings.pre_attack_enabled:
            await self._send_ping(ch, ev, ev.phase)
        elif ev.phase == "attack":  # Attack phase is always enabled
            await self._send_ping(ch, ev, ev.phase)
        else:
            live_feed.log(
                f"Skipping {ev.phase} ping (disabled in settings)",
                f"Bear ID: {ev.id}",
                guild,
                ch
            )

        # Calculate time until next phase
        phase_seq = ["scheduled", "incoming", "pre_attack", "attack", "victory"]
        current_idx = phase_seq.index(current_phase)
        next_phase = phase_seq[current_idx + 1]
        
        if next_phase == "victory":
            target = ev.epoch + BEAR_PHASE_OFFSETS["victory"] * 60
        else:
            # Use configured offset for pre_attack phase
            if next_phase == "pre_attack":
                target = ev.epoch - (ping_settings.pre_attack_offset * 60)
            else:
                target = ev.epoch + BEAR_PHASE_OFFSETS[next_phase] * 60
        
        delay = target - now
        if delay > 0:
            await asyncio.sleep(delay)
            # Recalculate phase after sleep to ensure accuracy
            now = int(time.time())
            new_phase = self._calc_phase(now, ev.epoch)
            if new_phase != current_phase:
                ev.phase = new_phase
                await self._send_or_edit_embed(ch, ev)
                await self._cleanup_pings(ch, keep_phase=new_phase)
                
                # Only send ping if phase is enabled in settings
                if new_phase == "incoming" and ping_settings.incoming_enabled:
                    await self._send_ping(ch, ev, new_phase)
                elif new_phase == "pre_attack" and ping_settings.pre_attack_enabled:
                    await self._send_ping(ch, ev, new_phase)
                elif new_phase == "attack":  # Attack phase is always enabled
                    await self._send_ping(ch, ev, new_phase)
                else:
                    live_feed.log(
                        f"Skipping {new_phase} ping (disabled in settings)",
                        f"Bear ID: {ev.id}",
                        guild,
                        ch
                    )
                
                # If we've reached victory, handle cleanup
                if new_phase == "victory":
                    log_ch = await ensure_channel(guild, BEAR_LOG_CHANNEL)
                    await log_ch.send(embed=make_phase_embed("victory", ev.epoch))
                    if ev.message_id:
                        try:
                            msg = await ch.fetch_message(ev.message_id)
                            await msg.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass
                    await self._cleanup_pings(ch)
                    # Remove from events and config
                    self.events.pop(ev.id, None)
                    cfg_bears = gcfg[str(ev.guild_id)]["bears"]
                    cfg_bears[:] = [b for b in cfg_bears if b["id"] != ev.id]
                    save_config(gcfg)
                    
                    # Start next bear if exists
                    guild_cfg = gcfg[str(ev.guild_id)]
                    remaining = [b for b in guild_cfg.get("bears", []) 
                                if b["epoch"] > ev.epoch and 
                                now <= b["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60]
                    if remaining:
                        next_bear = min(remaining, key=lambda b: b["epoch"])
                        next_ev = BearEvent(ev.guild_id, next_bear["epoch"], next_bear["id"])
                        self.events[next_ev.id] = next_ev
                        next_ev.task = asyncio.create_task(self._run_event_cycle(next_ev))
                    return

        # Schedule remaining phases
        for phase in phase_seq[current_idx + 1:]:
            if phase == "victory":
                target = ev.epoch + BEAR_PHASE_OFFSETS["victory"] * 60
            else:
                # Use configured offset for pre_attack phase
                if phase == "pre_attack":
                    target = ev.epoch - (ping_settings.pre_attack_offset * 60)
                else:
                    target = ev.epoch + BEAR_PHASE_OFFSETS[phase] * 60
            delay = target - int(time.time())
            if delay > 0:
                await asyncio.sleep(delay)
                # Recalculate phase after sleep
                now = int(time.time())
                new_phase = self._calc_phase(now, ev.epoch)
                if new_phase != ev.phase:
                    ev.phase = new_phase
                    await self._send_or_edit_embed(ch, ev)
                    await self._cleanup_pings(ch, keep_phase=new_phase)
                    
                    # Only send ping if phase is enabled in settings
                    if new_phase == "incoming" and ping_settings.incoming_enabled:
                        await self._send_ping(ch, ev, new_phase)
                    elif new_phase == "pre_attack" and ping_settings.pre_attack_enabled:
                        await self._send_ping(ch, ev, new_phase)
                    elif new_phase == "attack":  # Attack phase is always enabled
                        await self._send_ping(ch, ev, new_phase)
                    else:
                        live_feed.log(
                            f"Skipping {new_phase} ping (disabled in settings)",
                            f"Bear ID: {ev.id}",
                            guild,
                            ch
                        )
                    
                    if new_phase == "victory":
                        log_ch = await ensure_channel(guild, BEAR_LOG_CHANNEL)
                        await log_ch.send(embed=make_phase_embed("victory", ev.epoch))
                        if ev.message_id:
                            try:
                                msg = await ch.fetch_message(ev.message_id)
                                await msg.delete()
                            except (discord.NotFound, discord.Forbidden):
                                pass
                        await self._cleanup_pings(ch)
                        # Remove from events and config
                        self.events.pop(ev.id, None)
                        cfg_bears = gcfg[str(ev.guild_id)]["bears"]
                        cfg_bears[:] = [b for b in cfg_bears if b["id"] != ev.id]
                        save_config(gcfg)
                        
                        # Start next bear if exists
                        guild_cfg = gcfg[str(ev.guild_id)]
                        remaining = [b for b in guild_cfg.get("bears", []) 
                                    if b["epoch"] > ev.epoch and 
                                    now <= b["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60]
                        if remaining:
                            next_bear = min(remaining, key=lambda b: b["epoch"])
                            next_ev = BearEvent(ev.guild_id, next_bear["epoch"], next_bear["id"])
                            self.events[next_ev.id] = next_ev
                            next_ev.task = asyncio.create_task(self._run_event_cycle(next_ev))
                        return

    # ────────────── Helpers ──────────────

    @staticmethod
    def _calc_phase(now: int, epoch: int) -> str:
        """Calculate the current phase based on time and ping settings"""
        delta = now - epoch
        if delta >= BEAR_PHASE_OFFSETS["victory"] * 60:
            return "victory"
        if delta >= 0:
            return "attack"
        
        # Get ping settings to determine pre-attack timing
        ping_settings = get_bear_ping_settings(str(epoch))  # Use epoch as guild_id since we don't have it here
        if delta >= -ping_settings.pre_attack_offset * 60:
            return "pre_attack"
        if delta >= BEAR_PHASE_OFFSETS["incoming"] * 60:
            return "incoming"
        return "scheduled"

    async def _send_or_edit_embed(self, ch: discord.TextChannel, ev: BearEvent):
        embed = make_phase_embed(ev.phase, ev.epoch)
        if ev.message_id:
            try:
                msg = await ch.fetch_message(ev.message_id)
                await msg.edit(embed=embed)
                dt = datetime.fromtimestamp(ev.epoch, tz=timezone.utc)
                live_feed.log(
                    f"Updated bear phase to {ev.phase}",
                    f"Bear ID: {ev.id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    ch.guild,
                    ch
                )
                return
            except (discord.NotFound, discord.Forbidden):
                ev.message_id = None
                live_feed.log(
                    "Failed to update bear embed",
                    f"Bear ID: {ev.id} • Message not found",
                    ch.guild,
                    ch
                )

        # Send new embed and persist its ID
        msg = await ch.send(embed=embed)
        ev.message_id = msg.id
        dt = datetime.fromtimestamp(ev.epoch, tz=timezone.utc)
        live_feed.log(
            f"Created new bear {ev.phase} embed",
            f"Bear ID: {ev.id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ch.guild,
            ch
        )
        # update JSON so we can re-fetch/edit on next startup
        for b in gcfg[str(ch.guild.id)]["bears"]:
            if b["id"] == ev.id:
                b["message_id"] = ev.message_id
                break
        save_config(gcfg)

    async def _cleanup_pings(self, ch: discord.TextChannel, keep_phase: Optional[str] = None):
        """
        Delete all ping messages for phases != keep_phase
        by scanning the last 25 messages.
        """
        # core phrases for each phase
        patterns_map = {
            "incoming":   "bear is approaching",
            "pre_attack": "get ready to attack the bear",
            "attack":     "attack the bear"
        }
        # we only want to delete phrases *not* matching keep_phase
        to_delete = [txt for phase, txt in patterns_map.items() if phase != keep_phase]

        async for msg in ch.history(limit=25):
            if msg.author.id != self.bot.user.id:
                continue
            content = msg.content.lower()
            if any(core in content for core in to_delete):
                try:
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

    async def _send_ping(self, ch: discord.TextChannel, ev: BearEvent, phase: str):
        if phase not in ("incoming", "pre_attack", "attack"):
            return

        # ——— don't resend if this phase's ping already exists ———
        core_map = {
            "incoming":   "bear is approaching",
            "pre_attack": "get ready to attack the bear",
            "attack":     "attack the bear"
        }
        core = core_map[phase]
        async for msg in ch.history(limit=25):
            if msg.author.id == self.bot.user.id and core in msg.content.lower():
                return

        # Determine role mention
        role_ping = "@here"
        role_id = gcfg[str(ev.guild_id)].get("bear", {}).get("role_id")
        if role_id:
            role = ch.guild.get_role(role_id)
            if role:
                role_ping = role.mention

        texts = {
            "incoming":   f"{role_ping} — 🐾 bear is approaching! 🐾",
            "pre_attack": f"{role_ping} — <:BEAREVENT:1375520846407270561> get ready to attack the bear! 🎯",
            "attack":     "**💥 ATTACK THE BEAR! <:BEARATTACKED:1375525984723275967>**",
        }
        # Send ping for this phase
        await ch.send(texts[phase])
        dt = datetime.fromtimestamp(ev.epoch, tz=timezone.utc)
        live_feed.log(
            f"Sent {phase} ping",
            f"Bear ID: {ev.id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ch.guild,
            ch
        )

    # ───────────── Slash Commands ─────────────

    @app_commands.command(name="setbeartime", description="📆 Schedule a new bear attack!")
    @app_commands.describe(timestamp="YYYY-MM-DD HH:MM (UTC) or epoch")
    async def setbeartime(self, interaction: discord.Interaction, timestamp: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admins only", ephemeral=True)

        try:
            epoch = int(timestamp) if timestamp.isdigit() else int(
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
            )
        except Exception:
            return await interaction.followup.send("❌ Invalid time format", ephemeral=True)

        now = int(time.time())
        if epoch <= now:
            return await interaction.followup.send("❌ Time must be in the future", ephemeral=True)

        guild_id = str(interaction.guild.id)
        cfg = gcfg.setdefault(guild_id, {})
        bears = cfg.setdefault("bears", [])
        if any(abs(b["epoch"] - epoch) < 3600 for b in bears):
            return await interaction.followup.send("❌ Conflicts with another bear (±1\u202Fhour)", ephemeral=True)

        # Persist new bear
        new_id = str(uuid.uuid4())[:8]
        bears.append({"id": new_id, "epoch": epoch})
        bears.sort(key=lambda b: b["epoch"])
        save_config(gcfg)

        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        live_feed.log(
            "Scheduled new bear",
            f"Bear ID: {new_id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )

        # Find the current active bear event for this guild
        active_ev = None
        active_ev_epoch = None
        for ev in self.events.values():
            if ev.guild_id == interaction.guild.id:
                if active_ev is None or ev.epoch < active_ev_epoch:
                    active_ev = ev
                    active_ev_epoch = ev.epoch

        # If the new bear is before the current active bear, replace it
        if active_ev is None or epoch < active_ev.epoch:
            # Cancel the current active bear if it exists
            if active_ev is not None:
                if active_ev.task:
                    active_ev.task.cancel()
                ch = await ensure_channel(interaction.guild, BEAR_CHANNEL)
                if active_ev.message_id:
                    try:
                        msg = await ch.fetch_message(active_ev.message_id)
                        await msg.delete()
                    except:
                        pass
                await self._cleanup_pings(ch)
                # Remove from self.events
                self.events.pop(active_ev.id, None)
                live_feed.log(
                    "Cancelled active bear for new schedule",
                    f"Old Bear ID: {active_ev.id} • New Bear ID: {new_id}",
                    interaction.guild,
                    interaction.channel
                )
            # Start the new bear event cycle
            ev = BearEvent(interaction.guild.id, epoch, new_id)
            self.events[ev.id] = ev
            ev.task = asyncio.create_task(self._run_event_cycle(ev))
            await interaction.followup.send(f"✅ Bear scheduled for <t:{epoch}:F> (now active)", ephemeral=True)
        else:
            # Just queue the new bear, don't start its event cycle yet
            await interaction.followup.send(f"✅ Bear scheduled for <t:{epoch}:F> (queued)", ephemeral=True)

    @app_commands.command(name="cancelbear", description="❌ Cancel an upcoming bear event")
    @app_commands.describe(bear_id="The ID of the bear to cancel (use /listbears to see IDs)")
    async def cancelbear(self, interaction: discord.Interaction, bear_id: str):
        await interaction.response.defer(ephemeral=True)
        
        # First check if the bear exists in the config
        guild_id = str(interaction.guild.id)
        cfg = gcfg.get(guild_id, {})
        bears = cfg.get("bears", [])
        
        # Find the bear in config
        bear_config = next((b for b in bears if b["id"] == bear_id), None)
        if not bear_config:
            return await interaction.followup.send("⚠️ Bear not found in schedule", ephemeral=True)
            
        # Now check if it's the active bear
        ev = self.events.get(bear_id)
        if not ev or ev.guild_id != interaction.guild.id:
            # Bear exists in config but not active - just remove from config
            cfg["bears"] = [b for b in bears if b["id"] != bear_id]
            save_config(gcfg)
            dt = datetime.fromtimestamp(bear_config["epoch"], tz=timezone.utc)
            live_feed.log(
                "Removed queued bear from schedule",
                f"Bear ID: {bear_id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')} • By: {interaction.user}",
                interaction.guild,
                interaction.channel
            )
            return await interaction.followup.send("🗑️ Removed bear from schedule", ephemeral=True)

        # Cancel the active bear
        if ev.task:
            ev.task.cancel()
            try:
                await ev.task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                live_feed.log(
                    "Error cancelling bear task",
                    f"Bear ID: {bear_id} • Error: {str(e)}",
                    interaction.guild,
                    interaction.channel
                )

        # Cleanup embed & pings
        ch = await ensure_channel(interaction.guild, BEAR_CHANNEL)
        if ev.message_id:
            try:
                msg = await ch.fetch_message(ev.message_id)
                await msg.delete()
            except discord.NotFound:
                live_feed.log(
                    "Bear message already deleted",
                    f"Bear ID: {bear_id}",
                    interaction.guild,
                    interaction.channel
                )
            except discord.Forbidden:
                live_feed.log(
                    "No permission to delete bear message",
                    f"Bear ID: {bear_id}",
                    interaction.guild,
                    interaction.channel
                )
            except Exception as e:
                live_feed.log(
                    "Error deleting bear message",
                    f"Bear ID: {bear_id} • Error: {str(e)}",
                    interaction.guild,
                    interaction.channel
                )

        await self._cleanup_pings(ch)

        # Remove from events and config
        self.events.pop(bear_id, None)
        cfg["bears"] = [b for b in bears if b["id"] != bear_id]
        save_config(gcfg)

        dt = datetime.fromtimestamp(ev.epoch, tz=timezone.utc)
        live_feed.log(
            "Cancelled active bear",
            f"Bear ID: {bear_id} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )

        # Start the next soonest bear if any are queued
        remaining_bears = [b for b in cfg.get("bears", []) if b["epoch"] > ev.epoch]
        if remaining_bears:
            next_bear = min(remaining_bears, key=lambda b: b["epoch"])
            # Only start if not already running
            if next_bear["id"] not in self.events:
                next_ev = BearEvent(interaction.guild.id, next_bear["epoch"], next_bear["id"])
                self.events[next_ev.id] = next_ev
                next_ev.task = asyncio.create_task(self._run_event_cycle(next_ev))
                dt = datetime.fromtimestamp(next_bear["epoch"], tz=timezone.utc)
                live_feed.log(
                    "Started next queued bear",
                    f"Bear ID: {next_bear['id']} • Time: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    interaction.guild,
                    interaction.channel
                )

        await interaction.followup.send("🗑️ Bear cancelled", ephemeral=True)

    @app_commands.command(name="listbears", description="📋 List all scheduled bears")
    async def listbears(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        all_bears = gcfg.get(guild_id, {}).get("bears", [])
        if not all_bears:
            return await interaction.response.send_message("📭 No bears scheduled", ephemeral=True)

        now = int(time.time())
        # sort by scheduled time
        all_bears.sort(key=lambda b: b["epoch"])

        embed = discord.Embed(title="<:BEAREVENT:1375520846407270561> Upcoming Bears", color=discord.Color.orange())
        for b in all_bears:
            phase = self._calc_phase(now, b["epoch"])
            # marker 📍 once it's moved out of "scheduled"
            marker = "📍" if phase != "scheduled" else "🆔"
            embed.add_field(
                name=f"{marker} {b['id']} — {phase}",
                value=f"<t:{b['epoch']}:F> • <t:{b['epoch']}:R>",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(NewBearScheduler(bot))
