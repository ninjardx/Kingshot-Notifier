# cogs/arena.py

import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from helpers import save_config, ensure_channel
from config import (
    gcfg,
    ARENA_CHANNEL,
    ARENA_OPEN_TIME,
    ARENA_RESET_TIME,
    EMBED_COLOR_INFO,
    EMBED_COLOR_WARNING,
    SCHEDULER_INTERVAL_SEC
)
from config_helpers import get_arena_ping_settings

def make_arena_embed(status: str, open_ts: int, reset_ts: int) -> discord.Embed:
    if status == "scheduled":
        title = "📅 Arena resets in"
        color = EMBED_COLOR_INFO
        desc = (
            f"🕓 **Opens:** <t:{open_ts}:F>  (<t:{open_ts}:R>)\n"
            f"🧭 **Daily Reset:** <t:{reset_ts}:F>\n\n"
            f"⚙️ Prepare your lineup and gear up for battle!"
        )
    else:
        title = "🚨 Arena is Now Open!"
        color = EMBED_COLOR_WARNING
        desc = (
            f"🏁 **Resets In:** <t:{reset_ts}:R>\n"
            f"⚙️ Don't miss your chance to attack today!"
        )

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text="👑 Kingshot Bot • Daily Arena • UTC")
    embed.set_thumbnail(url="")
    return embed

class ArenaScheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_map: dict[int, discord.Message] = {}
        # start the loop
        self.task: asyncio.Task | None = None

    async def cog_load(self):
        # Now that the bot is fully initialised, start our arena loop
        self.task = asyncio.create_task(self._arena_loop())

    def cog_unload(self):
        # Clean up on cog unload or shutdown
        if self.task:
            self.task.cancel()

    async def _arena_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.now(timezone.utc)
            today = now.date()
            open_h, open_m = map(int, ARENA_OPEN_TIME.split(":"))
            reset_h, reset_m = map(int, ARENA_RESET_TIME.split(":"))
            arena_open = datetime.combine(today, time(open_h, open_m, tzinfo=timezone.utc))
            arena_reset = datetime.combine(today + timedelta(days=1), time(reset_h, reset_m, tzinfo=timezone.utc))

            # Determine current phase & next target
            if now < arena_open:
                phase = "scheduled"
                target = arena_open
            elif now < arena_reset:
                phase = "open"
                target = arena_reset
            else:
                phase = "scheduled"
                target = arena_open + timedelta(days=1)

            # Process each guild
            for guild_id, guild_cfg in gcfg.items():
                arena_cfg = guild_cfg.get("arena", {})
                chan_id = arena_cfg.get("channel_id")
                if not chan_id:
                    continue

                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue

                ch = guild.get_channel(int(chan_id))
                if not ch:
                    continue

                # Get ping settings for this guild
                ping_settings = get_arena_ping_settings(guild_id)

                # Send ping when arena opens (if enabled)
                if phase == "open" and not arena_cfg.get("ping_id"):
                    if ping_settings.ping_enabled:
                        role_mention = "@here"
                        role = None
                        role_id = arena_cfg.get("role_id")
                        if role_id:
                            role = guild.get_role(int(role_id))
                        if not role:
                            role = discord.utils.get(guild.roles, name="Arena ⚔️")
                        if role:
                            role_mention = role.mention

                        ping_msg = await ch.send(f"{role_mention} ⚔️ Arena is now live!")
                        arena_cfg["ping_id"] = ping_msg.id
                        save_config(gcfg)
                    else:
                        live_feed.log(
                            "Skipping arena ping (disabled in settings)",
                            f"Guild: {guild.name}",
                            guild,
                            ch
                        )

                # Cleanup ping after reset
                if phase == "scheduled" and arena_cfg.get("ping_id"):
                    try:
                        ping_msg = await ch.fetch_message(arena_cfg["ping_id"])
                        await ping_msg.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    arena_cfg["ping_id"] = None
                    save_config(gcfg)

                # Create or update the arena embed
                guild_cfg = gcfg[str(guild_id)]
                msg = await self._get_or_fix_message(guild_cfg, ch, phase, arena_open, arena_reset)

                # Persist embed message ID
                if msg and msg.id != arena_cfg.get("message_id"):
                    arena_cfg["message_id"] = msg.id
                    save_config(gcfg)

                self.message_map[int(guild_id)] = msg

            # Sleep until next phase or fallback interval
            sleep_secs = (target - datetime.now(timezone.utc)).total_seconds()
            await asyncio.sleep(max(sleep_secs, SCHEDULER_INTERVAL_SEC))

    async def _get_or_fix_message(
        self,
        guild_cfg: dict,
        ch: discord.TextChannel,
        phase: str,
        arena_open: datetime,
        arena_reset: datetime
    ) -> discord.Message | None:
        """
        Fetch the existing arena embed via saved message_id, edit it,
        or send a new one and persist its ID.
        """
        # Build the up-to-date embed
        embed = make_arena_embed(
            phase,
            int(arena_open.timestamp()),
            int(arena_reset.timestamp())
        )

        # Try to fetch and edit the existing embed message
        msg_id = guild_cfg.get("arena", {}).get("message_id")
        if msg_id:
            try:
                msg = await ch.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return msg
            except (discord.NotFound, discord.Forbidden):
                # Message was deleted or we lost permissions; fall through
                pass
        # Otherwise send a fresh embed
        try:
            msg = await ch.send(embed=embed)
        except discord.Forbidden:
            return None

        # Persist the new message_id
        guild_cfg.setdefault("arena", {})["message_id"] = msg.id
        save_config(gcfg)
        return msg

    async def sync_now(self, guild: discord.Guild):
        """Manually sync the arena embed & ping for a single guild."""
        guild_cfg = gcfg.get(str(guild.id), {})
        arena_cfg = guild_cfg.get("arena", {})
        chan_id = arena_cfg.get("channel_id")

        if guild_cfg.get("mode") == "manual" and chan_id:
            ch = guild.get_channel(int(chan_id))
        else:
            ch = await ensure_channel(guild, ARENA_CHANNEL)

        if not ch:
            return

        # Get ping settings for this guild
        ping_settings = get_arena_ping_settings(str(guild.id))

        now = datetime.now(timezone.utc)
        today = now.date()
        open_h, open_m = map(int, ARENA_OPEN_TIME.split(":"))
        reset_h, reset_m = map(int, ARENA_RESET_TIME.split(":"))
        arena_open = datetime.combine(today, time(open_h, open_m, tzinfo=timezone.utc))
        arena_reset = datetime.combine(today + timedelta(days=1), time(reset_h, reset_m, tzinfo=timezone.utc))

        phase = "scheduled" if now < arena_open or now >= arena_reset else "open"

        msg = await self._get_or_fix_message(guild_cfg, ch, phase, arena_open, arena_reset)

        # Handle ping on manual sync (if enabled)
        if phase == "open" and not arena_cfg.get("ping_id"):
            if ping_settings.ping_enabled:
                role_mention = "@here"
                role = None
                role_id = arena_cfg.get("role_id")
                if role_id:
                    role = guild.get_role(int(role_id))
                if not role:
                    role = discord.utils.get(guild.roles, name="Arena ⚔️")
                if role:
                    role_mention = role.mention

                ping_msg = await ch.send(f"{role_mention} ⚔️ Arena is now live!")
                arena_cfg["ping_id"] = ping_msg.id
                save_config(gcfg)
            else:
                live_feed.log(
                    "Skipping arena ping (disabled in settings)",
                    f"Guild: {guild.name}",
                    guild,
                    ch
                )

        if msg and msg.id != arena_cfg.get("message_id"):
            arena_cfg["message_id"] = msg.id
            save_config(gcfg)

        self.message_map[guild.id] = msg

async def setup(bot: commands.Bot):
    await bot.add_cog(ArenaScheduler(bot))
