# cogs/installer.py

import discord
import asyncio
from discord import app_commands
from discord.ext import commands

from helpers import save_config, ensure_channel, ensure_role
from config import (
    gcfg,
    CATEGORY_NAME, ROLE_EMOJIS,
    REACTION_CHANNEL, BEAR_CHANNEL, BEAR_LOG_CHANNEL,
    ARENA_CHANNEL, EVENT_CHANNEL
)
from .reaction import ReactionRole
from cogs.events import make_event_welcome_embed
from cogs.bear   import make_bear_welcome_embed

def locked_channel_perms(bot_member: discord.Member, restrict_reactions=False):
    overwrites = {
        bot_member.guild.default_role: discord.PermissionOverwrite(
            send_messages=False,
            add_reactions=not restrict_reactions,
            manage_messages=False,
            create_public_threads=False,
            create_private_threads=False
        ),
        bot_member: discord.PermissionOverwrite(
            send_messages=True,
            add_reactions=True,
            manage_messages=True,
            read_message_history=True,
            embed_links=True
        )
    }
    return overwrites

class ChannelSelect(discord.ui.Select):
    def __init__(self, key: str, label: str, channels: list[discord.TextChannel], parent: "ManualChannelSelector", row: int = 0):
        self.key = key
        self.parent = parent
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in channels]
        super().__init__(
            placeholder=f"Select {label}",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=key,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent.channel_ids[self.key] = int(self.values[0])
        await interaction.response.defer()
        # Auto-save if all channels are selected
        if all(v is not None for v in self.parent.channel_ids.values()):
            guild_id = str(interaction.guild.id)
            guild_cfg = gcfg.setdefault(guild_id, {})
            guild_cfg["mode"] = "manual"
            guild_cfg.setdefault("bear", {})["channel_id"]     = self.parent.channel_ids["bear"]
            guild_cfg.setdefault("bear", {})["log_channel_id"] = self.parent.channel_ids["bear_log"]
            guild_cfg.setdefault("arena", {})["channel_id"]    = self.parent.channel_ids["arena"]
            guild_cfg.setdefault("event", {})["channel_id"]    = self.parent.channel_ids["event"]
            guild_cfg.setdefault("reaction", {})["channel_id"] = self.parent.channel_ids["reaction"]
            save_config(gcfg)
            # Send welcome embeds to Bear and Event channels and save message IDs
            bear_ch = interaction.guild.get_channel(self.parent.channel_ids["bear"])
            event_ch = interaction.guild.get_channel(self.parent.channel_ids["event"])
            if bear_ch:
                bm = await bear_ch.send(embed=make_bear_welcome_embed())
                guild_cfg["bear"]["welcome_message_id"] = bm.id
            if event_ch:
                em = await event_ch.send(embed=make_event_welcome_embed())
                guild_cfg.setdefault("event", {})["message_id"] = em.id
            # Create roles and save their IDs
            bear_role = await ensure_role(interaction.guild, "Bear 🐻", discord.Color.orange())
            arena_role = await ensure_role(interaction.guild, "Arena ⚔️", discord.Color.red())
            event_role = await ensure_role(interaction.guild, "Event 🏆", discord.Color.gold())
            guild_cfg["bear"]["role_id"] = bear_role.id
            guild_cfg["arena"]["role_id"] = arena_role.id
            guild_cfg["event"]["role_id"] = event_role.id
            save_config(gcfg)
            # Trigger immediate setup
            if (c := self.parent.bot.get_cog("ReactionRole")):
                await c.setup_reactions(interaction.guild, interaction.guild.get_channel(guild_cfg["reaction"]["channel_id"]))
            if (a := self.parent.bot.get_cog("ArenaScheduler")):
                await a.sync_now(interaction.guild)
            await interaction.followup.send("✅ Manual install complete.", ephemeral=True)
            self.parent.stop()

class ManualChannelSelector(discord.ui.View):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, cfg: dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.interaction = interaction
        self.cfg = cfg
        self.channel_ids = {
            "bear": None,
            "bear_log": None,
            "arena": None,
            "event": None,
            "reaction": None
        }
        labels = {
            "bear": "🐻 Bear Channel",
            "bear_log": "🐾 Bear Log Channel",
            "arena": "⚔️ Arena Channel",
            "event": "🏆 Event Channel",
            "reaction": "📜 Reaction Role Channel"
        }
        for idx, (key, label) in enumerate(labels.items()):
            row = idx if idx < 5 else 4
            self.add_item(ChannelSelect(key, label, interaction.guild.text_channels, self, row=row))

    async def on_timeout(self):
        try:
            await self.interaction.followup.send("❌ Manual install timed out.", ephemeral=True)
        except:
            pass

class Installer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="install", description="⚙️ Set up the bot (auto or manual mode)")
    @app_commands.describe(mode="Choose 'auto' or 'manual'")
    async def install(self, interaction: discord.Interaction, mode: str):
        guild = interaction.guild
        if not guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        guild_id = str(guild.id)
        cfg = gcfg.setdefault(guild_id, {})

        # Already installed?
        if cfg.get("mode") and all(
            key in cfg for key in ("bear", "arena", "reaction", "event")
        ):
            return await interaction.followup.send("✅ Already installed. Use `/uninstall` to reset.", ephemeral=True)

        if mode == "auto":
            cfg["mode"] = "auto"
            await interaction.followup.send("⚙️ Auto-installing...", ephemeral=True)
            bot_member = guild.get_member(self.bot.user.id)

            # Create channels & roles
            bear_ch     = await ensure_channel(guild, BEAR_CHANNEL,     overwrites=locked_channel_perms(bot_member))
            bear_log    = await ensure_channel(guild, BEAR_LOG_CHANNEL, overwrites=locked_channel_perms(bot_member))
            arena_ch    = await ensure_channel(guild, ARENA_CHANNEL,    overwrites=locked_channel_perms(bot_member))
            event_ch    = await ensure_channel(guild, EVENT_CHANNEL,    overwrites=locked_channel_perms(bot_member))
            react_ch    = await ensure_channel(guild, REACTION_CHANNEL, overwrites=locked_channel_perms(bot_member, True))

            # Persist IDs
            cfg["bear"]     = {"channel_id": bear_ch.id,   "log_channel_id": bear_log.id}
            cfg["arena"]    = {"channel_id": arena_ch.id}
            cfg["event"]    = {"channel_id": event_ch.id}
            cfg["reaction"] = {"channel_id": react_ch.id}

            # Create roles
            bear_role  = await ensure_role(guild, "Bear 🐻",  discord.Color.orange())
            arena_role = await ensure_role(guild, "Arena ⚔️", discord.Color.red())
            event_role = await ensure_role(guild, "Event 🏆", discord.Color.gold())
            cfg["bear"]["role_id"]  = bear_role.id
            cfg["arena"]["role_id"] = arena_role.id
            cfg["event"]["role_id"] = event_role.id

            # Send welcome messages and trigger cogs
            msg = await event_ch.send(embed=make_event_welcome_embed())
            bm = await bear_ch.send(embed=make_bear_welcome_embed())
            cfg["bear"]["welcome_message_id"] = bm.id
            # Persist the welcome‐embed's message_id so events.py can pick it up
            cfg.setdefault("event", {})["channel_id"]  = event_ch.id
            cfg["event"]["message_id"] = msg.id
            if (a := self.bot.get_cog("ArenaScheduler")):
                await a.sync_now(guild)
            if (c := self.bot.get_cog("ReactionRole")):
                await c.setup_reactions(guild, react_ch)

            save_config(gcfg)
            await interaction.followup.send("✅ Installation complete.", ephemeral=True)

        elif mode == "manual":
            view = ManualChannelSelector(self.bot, interaction, gcfg)
            await interaction.followup.send(
                "⚙️ Please select channels and press Save 💾 below:", 
                view=view, ephemeral=True
            )
        else:
            await interaction.followup.send("❌ Unknown mode. Use `auto` or `manual`.", ephemeral=True)

    @app_commands.command(name="uninstall", description="🗑️ Remove all bot channels, roles, and settings")
    async def uninstall(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        guild_id = str(guild.id)
        cfg = gcfg.get(guild_id, {})
        deleted_roles, deleted_channels, deleted_categories, purged = 0, 0, 0, 0

        # Delete roles (bear, arena, event)
        for role_key in ("bear", "arena", "event"):
            role_id = cfg.get(role_key, {}).get("role_id")
            if role_id and (role := guild.get_role(role_id)):
                try:
                    await role.delete(reason="Uninstall")
                    deleted_roles += 1
                except discord.Forbidden:
                    pass

        # Auto mode: delete channels & category
        if cfg.get("mode") == "auto":
            for ch in guild.channels:
                if ch.category and ch.category.name == CATEGORY_NAME:
                    try:
                        await ch.delete()
                        deleted_channels += 1
                    except discord.Forbidden:
                        pass
            for cat in guild.categories:
                if cat.name == CATEGORY_NAME:
                    try:
                        await cat.delete()
                        deleted_categories += 1
                    except discord.Forbidden:
                        pass
        else:
            # Manual mode: purge bot messages only
            for sect in ("bear","bear_log","arena","event","reaction"):
                cid = cfg.get(sect, {}).get("channel_id")
                if cid and (ch := guild.get_channel(cid)):
                    def is_bot(m): return m.author.id == self.bot.user.id
                    try:
                        purged += len(await ch.purge(limit=100, check=is_bot))
                    except discord.Forbidden:
                        pass

        # Cancel any running BearScheduler tasks for this guild
        bear_cog = self.bot.get_cog("BearScheduler")
        if bear_cog:
            for ev in list(bear_cog.bear_events.values()):
                if ev.guild_id == guild.id and ev.task:
                    ev.task.cancel()
                    try:
                        await ev.task
                    except asyncio.CancelledError:
                        pass

        # Now remove the config entry
        gcfg.pop(guild_id, None)
        save_config(gcfg)

        await interaction.followup.send(
            f"🧹 Uninstalled: {deleted_roles} roles deleted, {deleted_channels} channels deleted, {deleted_categories} categories deleted, {purged} messages purged.", 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Installer(bot))
