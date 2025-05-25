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

from helpers import ensure_channel, save_config
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
            cfg = gcfg.setdefault(str(guild.id), {})
            bears = cfg.setdefault("bears", [])

            # Prune fully expired (past victory)
            bears[:] = [b for b in bears
                        if now <= b["epoch"] + BEAR_PHASE_OFFSETS["victory"] * 60]
            save_config(gcfg)

            if not bears:
                continue

            # Pick next-soonest
            next_entry = min(bears, key=lambda b: b["epoch"])
            ev = BearEvent(guild.id, next_entry["epoch"], next_entry["id"])
            ev.message_id = next_entry.get("message_id")
            self.events[ev.id] = ev
            # Kick off processing
            ev.task = asyncio.create_task(self._run_event_cycle(ev))

    # ────────────── Core Event Loop ──────────────

    async def _run_event_cycle(self, ev: BearEvent):
        guild = self.bot.get_guild(ev.guild_id)
        if not guild:
            return
        ch = await ensure_channel(guild, BEAR_CHANNEL)

        # Determine current phase
        now = int(time.time())
        ev.phase = self._calc_phase(now, ev.epoch)

        # Sync embed and ping for current phase only
        await self._send_or_edit_embed(ch, ev)
        await self._cleanup_pings(ch, keep_phase=ev.phase)
        await self._send_ping(ch, ev, ev.phase)

        # Schedule remaining phases
        phase_seq = ["incoming", "pre_attack", "attack", "victory"]
        for phase in phase_seq[phase_seq.index(ev.phase) + 1:]:
            # Compute delay until this phase
            if phase == "victory":
                target = ev.epoch + BEAR_PHASE_OFFSETS["victory"] * 60
            else:
                target = ev.epoch + BEAR_PHASE_OFFSETS[phase] * 60
            delay = target - int(time.time())
            if delay > 0:
                await asyncio.sleep(delay)

            ev.phase = phase
            await self._send_or_edit_embed(ch, ev)
            await self._cleanup_pings(ch, keep_phase=phase)
            await self._send_ping(ch, ev, phase)

            if phase == "victory":
                # Post to log channel
                log_ch = await ensure_channel(guild, BEAR_LOG_CHANNEL)
                await log_ch.send(embed=make_phase_embed("victory", ev.epoch))
                # Victory cleanup
                # Leave embed if no next bear, else wait & replace
                next_bears = [b for b in gcfg[str(guild.id)]["bears"] if b["epoch"] > ev.epoch]

                if next_bears:
                    # grace period before next bear
                    await asyncio.sleep(10)
                    # clear the old victory embed in the Bear channel
                    try:
                        prev_msg = await ch.fetch_message(ev.message_id)
                        await prev_msg.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                # Always break after victory phase to run cleanup
                break

        # On cycle complete: remove from JSON and schedule the next
        cfg_bears = gcfg[str(ev.guild_id)]["bears"]
        cfg_bears[:] = [b for b in cfg_bears if b["id"] != ev.id]
        save_config(gcfg)

        # Start next if exists
        guild_cfg = gcfg[str(ev.guild_id)]
        remaining = guild_cfg.get("bears", [])
        if remaining:
            nxt = min(remaining, key=lambda b: b["epoch"])
            nxt_ev = BearEvent(ev.guild_id, nxt["epoch"], nxt["id"])
            self.events[nxt_ev.id] = nxt_ev
            nxt_ev.task = asyncio.create_task(self._run_event_cycle(nxt_ev))

    # ────────────── Helpers ──────────────

    @staticmethod
    def _calc_phase(now: int, epoch: int) -> str:
        delta = now - epoch
        if delta >= BEAR_PHASE_OFFSETS["victory"] * 60:
            return "victory"
        if delta >= 0:
            return "attack"
        if delta >= BEAR_PHASE_OFFSETS["pre_attack"] * 60:
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
                return
            except (discord.NotFound, discord.Forbidden):
                ev.message_id = None

        # Send new embed and persist its ID
        msg = await ch.send(embed=embed)
        ev.message_id = msg.id
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

        # Find the current active bear event for this guild (the soonest future bear in self.events)
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
            # Start the new bear event cycle
            ev = BearEvent(interaction.guild.id, epoch, new_id)
            self.events[ev.id] = ev
            ev.task = asyncio.create_task(self._run_event_cycle(ev))
            await interaction.followup.send(f"✅ Bear scheduled for <t:{epoch}:F> (now active)", ephemeral=True)
        else:
            # Just queue the new bear, don't start its event cycle yet
            await interaction.followup.send(f"✅ Bear scheduled for <t:{epoch}:F> (queued)", ephemeral=True)

    @app_commands.command(name="cancelbear", description="❌ Cancel an upcoming bear event")
    async def cancelbear(self, interaction: discord.Interaction, bear_id: str):
        await interaction.response.defer(ephemeral=True)
        ev = self.events.pop(bear_id, None)
        if not ev or ev.guild_id != interaction.guild.id:
            return await interaction.followup.send("⚠️ Unknown bear ID", ephemeral=True)

        if ev.task:
            ev.task.cancel()
        # Cleanup embed & pings
        ch = await ensure_channel(interaction.guild, BEAR_CHANNEL)
        if ev.message_id:
            try:
                msg = await ch.fetch_message(ev.message_id)
                await msg.delete()
            except:
                pass
        await self._cleanup_pings(ch)

        # Remove from JSON
        cfg = gcfg[str(interaction.guild.id)]
        cfg["bears"] = [b for b in cfg.get("bears", []) if b["id"] != bear_id]
        save_config(gcfg)

        # Start the next soonest bear if any are queued
        bears = cfg.get("bears", [])
        if bears:
            next_bear = min(bears, key=lambda b: b["epoch"])
            # Only start if not already running
            if next_bear["id"] not in self.events:
                next_ev = BearEvent(interaction.guild.id, next_bear["epoch"], next_bear["id"])
                self.events[next_ev.id] = next_ev
                next_ev.task = asyncio.create_task(self._run_event_cycle(next_ev))

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
