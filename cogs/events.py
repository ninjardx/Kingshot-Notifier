# cogs/events.py

import asyncio
import time
import uuid
from datetime import datetime, timezone
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from helpers import save_config, ensure_channel
from config import gcfg, EVENT_CHANNEL, EMBED_COLOR_EVENT, EMOJI_THUMBNAILS_EVENTS
from command_center import live_feed
from config_helpers import get_event_ping_settings

EVENT_TEMPLATES = {
    "hall_of_governors": {
        "title": "Hall Of Governors",
        "description": "Compete in the Hall Of Governors event!",
        "thumbnail": "https://example.com/hog.png",
        "duration_minutes": 7 * 24 * 60  # 7 days
    },
    "all_out_event": {
        "title": "All Out Event",
        "description": "Participate in the All Out Event!",
        "thumbnail": "https://example.com/allout.png",
        "duration_minutes": 24 * 60  # 1 day
    },
    "viking_vengeance": {
        "title": "Viking Vengeance",
        "description": "Join the Viking Vengeance event!",
        "thumbnail": "https://example.com/viking.png",
        "duration_minutes": 30  # 30 minutes
    },
    "swordland_showdown": {
        "title": "Swordland Showdown",
        "description": "Enter the Swordland Showdown!",
        "thumbnail": "https://example.com/swordland.png",
        "duration_minutes": 60  # 1 hour
    },
    "kingdom_v_kingdom": {
        "title": "Kingdom V Kingdom",
        "description": "Battle in the Kingdom V Kingdom event!",
        "thumbnail": "https://example.com/kvk.png",
        "duration_minutes": 5 * 24 * 60  # 5 days
    }
}

def make_event_welcome_embed() -> discord.Embed:
    """
    Used by /install auto to send a friendly explanation
    into the Events channel.
    """
    embed = discord.Embed(
        title="🏆 Event Notifications 🏆",
        description=(
            "📢 **This channel will receive announcements for upcoming events!**\n\n"
            "<:stateagekingshot300x291:1375519500820025454> **Add** an event: `/addevent`\n"
            "🔍 **List** upcoming events: `/listevents`\n"
            "❌ **Cancel** an event: `/cancelevent`\n\n"
            "🛡️ Stay tuned for upcoming events! 🏆"
        ),
        color=EMBED_COLOR_EVENT
    )
    embed.set_footer(text="👑 Kingshot Bot • Events • UTC")
    return embed


class EventEntry:
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        start_epoch: int,
        end_epoch: int,
        guild_id: int,
        thumbnail: str = "",
        template_key: str = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.start_epoch = start_epoch
        self.end_epoch = end_epoch
        self.guild_id = guild_id   
        self.thumbnail = thumbnail
        self.template_key = template_key
        self.message: discord.Message | None = None
        self.message_id: int | None = None
        self.task: asyncio.Task | None = None

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            timestamp=datetime.fromtimestamp(self.start_epoch, tz=timezone.utc),
            color=EMBED_COLOR_EVENT
        )
        embed.add_field(
            name="🗓️ Starts",
            value=f"<t:{self.start_epoch}:F> (<t:{self.start_epoch}:R>)",
            inline=True
        )
        embed.add_field(
            name="⏳ Ends",
            value=f"<t:{self.end_epoch}:F> (<t:{self.end_epoch}:R>)",
            inline=True
        )
        # Use emoji thumbnail if available for template events
        if self.template_key and self.template_key in EMOJI_THUMBNAILS_EVENTS:
            embed.set_thumbnail(url=EMOJI_THUMBNAILS_EVENTS[self.template_key])
        elif self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)
        embed.set_footer(text="Kingshot Bot • Events • UTC")
        return embed

class AddEventModeSelect(discord.ui.View):
    def __init__(self, bot, scheduler):
        super().__init__(timeout=60)
        self.bot = bot
        self.scheduler = scheduler

    @discord.ui.select(
        placeholder="How would you like to add an event?",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Manual", value="manual", description="Enter all event details manually"),
            discord.SelectOption(label="Template", value="template", description="Choose from a curated template")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        mode = select.values[0]
        await interaction.response.defer(ephemeral=True)
        if mode == "manual":
            modal = ManualEventModal(self.scheduler)
            await interaction.followup.send_modal(modal)
        else:
            template_view = AddEventTemplateSelect(self.bot, self.scheduler)
            await interaction.followup.send("Select an event template:", view=template_view, ephemeral=True)

class AddEventTemplateSelect(discord.ui.View):
    def __init__(self, bot, scheduler):
        super().__init__(timeout=60)
        self.bot = bot
        self.scheduler = scheduler

    @discord.ui.select(
        placeholder="Select an event template",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Hall Of Governors", value="hall_of_governors", description="Pre-built Hall Of Governors event"),
            discord.SelectOption(label="All Out Event", value="all_out_event", description="Pre-built All Out Event"),
            discord.SelectOption(label="Viking Vengeance", value="viking_vengeance", description="Pre-built Viking Vengeance event"),
            discord.SelectOption(label="Sanctuary Battles", value="sanctuary_battles", description="Pre-built Sanctuary Battles event"),
            discord.SelectOption(label="Swordland Showdown", value="swordland_showdown", description="Pre-built Swordland Showdown event"),
            discord.SelectOption(label="Kingdom V Kingdom", value="kingdom_v_kingdom", description="Pre-built Kingdom V Kingdom event")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        template = select.values[0]
        modal = TemplateEventModal(self.scheduler, template)
        await interaction.response.send_modal(modal)

class ManualEventModal(discord.ui.Modal, title="Add Event Manually"):
    event_title = discord.ui.TextInput(label="Title", required=True)
    event_description = discord.ui.TextInput(label="Description", required=True, style=discord.TextStyle.paragraph)
    event_start = discord.ui.TextInput(label="Start (YYYY-MM-DD HH:MM UTC)", required=True)
    event_end = discord.ui.TextInput(label="End (YYYY-MM-DD HH:MM UTC)", required=True)
    event_thumbnail = discord.ui.TextInput(label="Thumbnail URL (optional)", required=False)

    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    async def on_submit(self, interaction: discord.Interaction):
        # Parse times
        try:
            st = datetime.strptime(self.event_start.value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            et = datetime.strptime(self.event_end.value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)
        s_epoch = int(st.timestamp())
        e_epoch = int(et.timestamp())
        if e_epoch <= s_epoch:
            return await interaction.response.send_message("❌ End must be after start.", ephemeral=True)
        await self.scheduler.create_event(
            interaction,
            title=self.event_title.value,
            description=self.event_description.value,
            s_epoch=s_epoch,
            e_epoch=e_epoch,
            thumbnail=self.event_thumbnail.value
        )

class TemplateEventModal(discord.ui.Modal, title="Schedule Hall Of Governors"):
    event_start = discord.ui.TextInput(label="Start (YYYY-MM-DD HH:MM UTC)", required=True)

    def __init__(self, scheduler, template_key):
        super().__init__()
        self.scheduler = scheduler
        self.template_key = template_key

    async def on_submit(self, interaction: discord.Interaction):
        template = EVENT_TEMPLATES[self.template_key]
        try:
            st = datetime.strptime(self.event_start.value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)
        s_epoch = int(st.timestamp())
        e_epoch = s_epoch + template["duration_minutes"] * 60
        await self.scheduler.create_event(
            interaction,
            title=template["title"],
            description=template["description"],
            s_epoch=s_epoch,
            e_epoch=e_epoch,
            thumbnail=template["thumbnail"],
            template_key=self.template_key
        )

class EventScheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.events: dict[str, EventEntry] = {}
        # Kick off loading existing events
        self._init_task = asyncio.create_task(self._initialize())

    def cog_unload(self):
        # Cancel startup loader
        self._init_task.cancel()
        # Cancel any in-flight event tasks
        for ev in self.events.values():
            if ev.task:
                ev.task.cancel()

    async def _initialize(self):
        await self.bot.wait_until_ready()
        now = int(time.time())

        for guild in self.bot.guilds:
            guild_cfg = gcfg.get(str(guild.id), {})
            if guild_cfg.get("mode") != "auto":
                continue

            live_feed.log(
                "Initializing events",
                f"Guild: {guild.name}",
                guild,
                None
            )

            # 1) Prune expired events
            ev_list = guild_cfg.setdefault("events", [])
            expired = [e for e in ev_list if e["end_epoch"] <= now]
            ev_list[:] = [e for e in ev_list if e["end_epoch"] > now]
            if expired:
                live_feed.log(
                    "Pruned expired events",
                    f"Guild: {guild.name} • Count: {len(expired)}",
                    guild,
                    None
                )
            save_config(gcfg)

            if not ev_list:
                continue

            # 2) Determine target channel
            chan_id = guild_cfg.get("event", {}).get("channel_id")
            if chan_id:
                ch = guild.get_channel(chan_id)
            else:
                ch = discord.utils.get(guild.text_channels, name=EVENT_CHANNEL)
                if not ch:
                    ch = await ensure_channel(guild, EVENT_CHANNEL)
                    live_feed.log(
                        "Created event channel",
                        f"Guild: {guild.name} • Channel: #{ch.name}",
                        guild,
                        ch
                    )

            # ─── Ensure welcome embed exists ─────────────────────
            evt_cfg = guild_cfg.setdefault("event", {})
            welcome_id = evt_cfg.get("message_id")
            welcome_msg = None
            if welcome_id:
                try:
                    welcome_msg = await ch.fetch_message(welcome_id)
                except (discord.NotFound, discord.Forbidden):
                    welcome_msg = None
            if not welcome_msg:
                msg = await ch.send(embed=make_event_welcome_embed())
                evt_cfg["message_id"] = msg.id
                save_config(gcfg)
                live_feed.log(
                    "Created welcome message",
                    f"Guild: {guild.name} • Channel: #{ch.name}",
                    guild,
                    ch
                )

            # 3) Reconstruct and schedule each event
            for entry in ev_list:
                ev = EventEntry(
                    entry["id"],
                    entry["title"],
                    entry["description"],
                    entry["start_epoch"],
                    entry["end_epoch"],
                    guild.id,
                    entry.get("thumbnail", ""),
                    entry.get("template_key")
                )
                # Try to re-fetch existing message
                msg_id = entry.get("message_id")
                if msg_id:
                    try:
                        ev.message = await ch.fetch_message(msg_id)
                        ev.message_id = msg_id
                        live_feed.log(
                            "Restored event message",
                            f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                            guild,
                            ch
                        )
                    except (discord.NotFound, discord.Forbidden):
                        ev.message = None
                        ev.message_id = None
                        live_feed.log(
                            "Failed to restore event message",
                            f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                            guild,
                            ch
                        )

                self.events[ev.id] = ev
                ev.task = asyncio.create_task(self._run_event_cycle(guild, ev, ch))
                live_feed.log(
                    "Scheduled event",
                    f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id} • Start: <t:{ev.start_epoch}:F>",
                    guild,
                    ch
                )

    async def _send_event_ping(self, ch: discord.TextChannel, guild_cfg: dict, minutes_left: int) -> int:
        # Get ping settings for this guild
        ping_settings = get_event_ping_settings(str(ch.guild.id))
        
        # Check if this ping phase is enabled
        if minutes_left == 60 and not ping_settings.reminder_enabled:
            live_feed.log(
                "Skipping 1-hour event reminder (disabled in settings)",
                f"Guild: {ch.guild.name}",
                ch.guild,
                ch
            )
            return None
        if minutes_left == 10 and not ping_settings.final_call_enabled:
            live_feed.log(
                "Skipping 10-minute event reminder (disabled in settings)",
                f"Guild: {ch.guild.name}",
                ch.guild,
                ch
            )
            return None

        role_id = guild_cfg.get("event", {}).get("role_id")
        role_mention = "@here"
        if role_id:
            role = ch.guild.get_role(role_id)
            if role:
                role_mention = role.mention
        if minutes_left == 60:
            msg = await ch.send(f"{role_mention} 🏆 Get ready for the event!")
            live_feed.log(
                "Sent 1-hour event reminder",
                f"Guild: {ch.guild.name} • Channel: #{ch.name} • Role: {role.name if role else '@here'}",
                ch.guild,
                ch
            )
        else:
            msg = await ch.send(f"{role_mention} 🏆 The event is starting soon!")
            live_feed.log(
                "Sent 10-minute event reminder",
                f"Guild: {ch.guild.name} • Channel: #{ch.name} • Role: {role.name if role else '@here'}",
                ch.guild,
                ch
            )
        return msg.id

    async def _run_event_cycle(
        self,
        guild: discord.Guild,
        ev: EventEntry,
        ch: discord.TextChannel
    ):
        try:
            now = int(time.time())
            guild_cfg = gcfg[str(guild.id)]
            
            # Get ping settings for this guild
            ping_settings = get_event_ping_settings(str(guild.id))
            
            # Calculate reminder times using configured offsets
            reminder_time = ev.start_epoch - (ping_settings.reminder_offset * 60)
            final_call_time = ev.start_epoch - (ping_settings.final_call_offset * 60)
            
            # Send reminder ping if enabled and not past that time
            reminder_id = None
            if ping_settings.reminder_enabled and now < reminder_time:
                await asyncio.sleep(reminder_time - now)
                reminder_id = await self._send_event_ping(ch, guild_cfg, ping_settings.reminder_offset)
                if reminder_id:
                    guild_cfg.setdefault("event", {})["reminder_id"] = reminder_id
                    save_config(gcfg)
                now = int(time.time())
            
            # Send final call ping if enabled and not past that time
            if ping_settings.final_call_enabled and now < final_call_time:
                await asyncio.sleep(final_call_time - now)
                # Delete reminder ping if it exists
                reminder_id = guild_cfg.get("event", {}).get("reminder_id")
                if reminder_id:
                    try:
                        msg = await ch.fetch_message(reminder_id)
                        await msg.delete()
                        live_feed.log(
                            "Deleted reminder ping",
                            f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                            guild,
                            ch
                        )
                    except (discord.NotFound, discord.Forbidden):
                        pass
                # Send final call ping
                reminder_id = await self._send_event_ping(ch, guild_cfg, ping_settings.final_call_offset)
                if reminder_id:
                    guild_cfg.setdefault("event", {})["reminder_id"] = reminder_id
                    save_config(gcfg)
                now = int(time.time())
            
            # Wait until event start
            if now < ev.start_epoch:
                await asyncio.sleep(ev.start_epoch - now)
            
            # Delete final call ping at event start
            reminder_id = guild_cfg.get("event", {}).get("reminder_id")
            if reminder_id:
                try:
                    msg = await ch.fetch_message(reminder_id)
                    await msg.delete()
                    live_feed.log(
                        "Deleted final call ping",
                        f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                        guild,
                        ch
                    )
                except (discord.NotFound, discord.Forbidden):
                    pass
                guild_cfg["event"]["reminder_id"] = None
                save_config(gcfg)

            # Send or edit embed at start
            embed = ev.make_embed()
            if ev.message:
                try:
                    await ev.message.edit(embed=embed)
                    live_feed.log(
                        "Updated event embed",
                        f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                        guild,
                        ch
                    )
                except (discord.NotFound, discord.Forbidden):
                    ev.message = await ch.send(embed=embed)
                    ev.message_id = ev.message.id
                    live_feed.log(
                        "Created new event embed",
                        f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                        guild,
                        ch
                    )
            else:
                ev.message = await ch.send(embed=embed)
                ev.message_id = ev.message.id
                live_feed.log(
                    "Created event embed",
                    f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                    guild,
                    ch
                )

            # Persist message_id
            for e in gcfg[str(guild.id)]["events"]:
                if e["id"] == ev.id:
                    e["message_id"] = ev.message_id
            save_config(gcfg)

            # 4b) Wait until event end
            now = int(time.time())
            await asyncio.sleep(max(ev.end_epoch - now, 0))

            # Delete the embed
            try:
                await ev.message.delete()
                live_feed.log(
                    "Event ended",
                    f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                    guild,
                    ch
                )
            except (discord.NotFound, discord.Forbidden):
                pass

            # 4c) Remove event from memory & config
            self.events.pop(ev.id, None)
            guild_cfg = gcfg[str(guild.id)]
            guild_cfg["events"] = [
                e for e in guild_cfg.get("events", []) if e["id"] != ev.id
            ]
            save_config(gcfg)

            # Start next soonest event if any
            ev_list = guild_cfg.get("events", [])
            if ev_list:
                next_entry = min(ev_list, key=lambda x: x["start_epoch"])
                next_ev = EventEntry(
                    next_entry["id"],
                    next_entry["title"],
                    next_entry["description"],
                    next_entry["start_epoch"],
                    next_entry["end_epoch"],
                    guild.id,
                    next_entry.get("thumbnail", ""),
                    next_entry.get("template_key")
                )
                self.events[next_ev.id] = next_ev
                chan_id = guild_cfg.get("event", {}).get("channel_id")
                if chan_id:
                    ch = guild.get_channel(chan_id)
                else:
                    ch = discord.utils.get(guild.text_channels, name=EVENT_CHANNEL)
                    if not ch:
                        ch = await ensure_channel(guild, EVENT_CHANNEL)
                next_ev.task = asyncio.create_task(self._run_event_cycle(guild, next_ev, ch))
                live_feed.log(
                    "Started next event",
                    f"Guild: {guild.name} • Event: {next_ev.title} • ID: {next_ev.id} • Start: <t:{next_ev.start_epoch}:F>",
                    guild,
                    ch
                )

        except asyncio.CancelledError:
            live_feed.log(
                "Event task cancelled",
                f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                guild,
                ch
            )
            raise

    async def create_event(self, interaction, title, description, s_epoch, e_epoch, thumbnail, template_key=None):
        guild = interaction.guild
        now = int(time.time())
        if s_epoch <= now:
            live_feed.log(
                "Failed to create event",
                f"Guild: {guild.name} • Error: Start time in past • By: {interaction.user}",
                guild,
                interaction.channel
            )
            return await interaction.response.send_message(
                "❌ Time must be in the future.", ephemeral=True
            )
        guild_cfg = gcfg.setdefault(str(guild.id), {})
        new_id = str(uuid.uuid4())[:8]
        entry = {
            "id": new_id,
            "title": title,
            "description": description,
            "start_epoch": s_epoch,
            "end_epoch": e_epoch,
            "thumbnail": thumbnail,
            "message_id": None,
            "template_key": template_key
        }
        ev_list = guild_cfg.setdefault("events", [])
        ev_list.append(entry)
        ev_list.sort(key=lambda x: x["start_epoch"])
        save_config(gcfg)

        live_feed.log(
            "Created new event",
            f"Guild: {guild.name} • Event: {title} • ID: {new_id} • Start: <t:{s_epoch}:F> • By: {interaction.user}",
            guild,
            interaction.channel
        )

        # Determine the channel
        chan_id = guild_cfg.get("event", {}).get("channel_id")
        if chan_id:
            ch = guild.get_channel(chan_id)
        else:
            ch = discord.utils.get(guild.text_channels, name=EVENT_CHANNEL)
            if not ch:
                ch = await ensure_channel(guild, EVENT_CHANNEL)

        # If this is the soonest event, cancel the current active event and start this one
        soonest_entry = min(ev_list, key=lambda x: x["start_epoch"])
        if soonest_entry["id"] == new_id:
            # Cancel all current event tasks for this guild
            for ev in list(self.events.values()):
                if ev.guild_id == guild.id and ev.task:
                    ev.task.cancel()
                    try:
                        await ev.task
                    except asyncio.CancelledError:
                        pass
                    # Delete the old event's embed message if it exists
                    if ev.message:
                        try:
                            await ev.message.delete()
                            live_feed.log(
                                "Deleted old event message",
                                f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                                guild,
                                ch
                            )
                        except (discord.NotFound, discord.Forbidden):
                            pass
            # Start the new soonest event
            ev = EventEntry(
                id=new_id,
                title=title,
                description=description,
                start_epoch=s_epoch,
                end_epoch=e_epoch,
                guild_id=guild.id,
                thumbnail=thumbnail,
                template_key=template_key
            )
            self.events[new_id] = ev
            # Send the embed immediately and persist its ID
            ev.message = await ch.send(embed=ev.make_embed())
            ev.message_id = ev.message.id
            for e in ev_list:
                if e["id"] == new_id:
                    e["message_id"] = ev.message_id
            save_config(gcfg)
            # Now schedule its lifecycle
            ev.task = asyncio.create_task(self._run_event_cycle(guild, ev, ch))
            # If the event is already within the reminder or final call window, send the appropriate notification immediately
            now = int(time.time())
            ping_settings = get_event_ping_settings(str(guild.id))
            
            reminder_time = s_epoch - (ping_settings.reminder_offset * 60)
            final_call_time = s_epoch - (ping_settings.final_call_offset * 60)
            
            if now >= reminder_time and now < final_call_time and ping_settings.reminder_enabled:
                reminder_id = await self._send_event_ping(ch, guild_cfg, ping_settings.reminder_offset)
                if reminder_id:
                    guild_cfg.setdefault("event", {})["reminder_id"] = reminder_id
                    save_config(gcfg)
            elif now >= final_call_time and now < s_epoch and ping_settings.final_call_enabled:
                reminder_id = await self._send_event_ping(ch, guild_cfg, ping_settings.final_call_offset)
                if reminder_id:
                    guild_cfg.setdefault("event", {})["reminder_id"] = reminder_id
                    save_config(gcfg)

        await interaction.response.send_message(
            f"✅ Event `{new_id}` scheduled for <t:{s_epoch}:F> to <t:{e_epoch}:F>.",
            ephemeral=True
        )

    @app_commands.command(name="addevent", description="🏆 Schedule a new event (manual or template)")
    async def addevent(self, interaction: discord.Interaction):
        live_feed.log(
            "Event creation started",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )
        view = AddEventModeSelect(self.bot, self)
        await interaction.response.send_message("How would you like to add an event?", view=view, ephemeral=True)

    @app_commands.command(name="cancelevent", description="❌ Cancel a scheduled event")
    async def cancelevent(
        self,
        interaction: discord.Interaction,
        event_id: str
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        guild_cfg = gcfg.get(str(guild.id), {})
        ev_list = guild_cfg.get("events", [])
        # Try to find event in memory first
        ev = self.events.pop(event_id, None)
        # If not in memory, try to find in config
        event_entry = None
        for e in ev_list:
            if e["id"] == event_id:
                event_entry = e
                break
        if not ev and not event_entry:
            live_feed.log(
                "Failed to cancel event",
                f"Guild: {guild.name} • Event ID: {event_id} • Error: Not found • By: {interaction.user}",
                guild,
                interaction.channel
            )
            return await interaction.followup.send("⚠️ Unknown event ID", ephemeral=True)
        # Cancel and cleanup
        if ev and ev.task:
            ev.task.cancel()
            try:
                await ev.task
            except asyncio.CancelledError:
                pass
        if ev and ev.message:
            try:
                await ev.message.delete()
                live_feed.log(
                    "Deleted event message",
                    f"Guild: {guild.name} • Event: {ev.title} • ID: {ev.id}",
                    guild,
                    interaction.channel
                )
            except:
                pass
        # Remove from config
        guild_cfg["events"] = [e for e in ev_list if e["id"] != event_id]
        save_config(gcfg)
        live_feed.log(
            "Cancelled event",
            f"Guild: {guild.name} • Event: {ev.title if ev else event_entry['title']} • ID: {event_id} • By: {interaction.user}",
            guild,
            interaction.channel
        )
        await interaction.followup.send(f"🗑️ Event `{event_id}` cancelled.", ephemeral=True)

    @app_commands.command(name="listevents", description="📋 List all upcoming events")
    async def listevents(self, interaction: discord.Interaction):
        live_feed.log(
            "Listing events",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild.id)
        now = int(time.time())
        # Always list from config for consistency
        all_events = gcfg.get(guild_id, {}).get("events", [])
        upcoming = [
            e for e in all_events
            if e["start_epoch"] > now
        ]
        if not upcoming:
            return await interaction.followup.send("📭 No events scheduled.", ephemeral=True)
        upcoming.sort(key=lambda e: e["start_epoch"])
        embed = discord.Embed(
            title="🏆 Upcoming Events",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Kingshot Bot • Events • UTC")
        for e in upcoming:
            embed.add_field(
                name=f"{e['id']} — {e['title']}",
                value=(
                    f"Starts <t:{e['start_epoch']}:F> (<t:{e['start_epoch']}:R>)\n"
                    f"Ends   <t:{e['end_epoch']}:F> (<t:{e['end_epoch']}:R>)"
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventScheduler(bot))
