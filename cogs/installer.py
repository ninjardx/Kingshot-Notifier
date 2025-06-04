# cogs/installer.py

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from helpers import ensure_channel, save_config, ensure_role
from config import (
    gcfg, BEAR_CHANNEL, ARENA_CHANNEL, EVENT_CHANNEL,
    CATEGORY_NAME, ROLE_EMOJIS,
    REACTION_CHANNEL, BEAR_LOG_CHANNEL,
)
from command_center import live_feed
from welcome_embeds import (
    make_bear_welcome_embed,
    make_arena_welcome_embed,
    make_event_welcome_embed,
    get_all_welcome_embeds
)
from cogs.reaction import ReactionRole

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
            
            # Move selected channels to the category
            category = await ensure_category(interaction.guild)
            if category:
                for key, channel_id in self.parent.channel_ids.items():
                    if channel := interaction.guild.get_channel(channel_id):
                        try:
                            await channel.edit(category=category)
                        except discord.Forbidden:
                            live_feed.log(
                                "Failed to move channel to category",
                                f"Guild: {interaction.guild.name} • Channel: {channel.name} • Error: No permission",
                                interaction.guild,
                                interaction.channel
                            )
            
            guild_cfg.setdefault("bear", {})["channel_id"]     = self.parent.channel_ids["bear"]
            guild_cfg.setdefault("bear", {})["log_channel_id"] = self.parent.channel_ids["bear_log"]
            guild_cfg.setdefault("arena", {})["channel_id"]    = self.parent.channel_ids["arena"]
            guild_cfg.setdefault("event", {})["channel_id"]    = self.parent.channel_ids["event"]
            guild_cfg.setdefault("reaction", {})["channel_id"] = self.parent.channel_ids["reaction"]
            save_config(gcfg)
            
            # Send welcome embeds to channels
            bear_ch = interaction.guild.get_channel(self.parent.channel_ids["bear"])
            arena_ch = interaction.guild.get_channel(self.parent.channel_ids["arena"])
            event_ch = interaction.guild.get_channel(self.parent.channel_ids["event"])
            
            if bear_ch:
                bm = await bear_ch.send(embed=make_bear_welcome_embed(guild_id))
                guild_cfg["bear"]["welcome_message_id"] = bm.id
            
            if arena_ch:
                am = await arena_ch.send(embed=make_arena_welcome_embed(guild_id))
                guild_cfg["arena"]["welcome_message_id"] = am.id
            
            if event_ch:
                em = await event_ch.send(embed=make_event_welcome_embed(guild_id))
                guild_cfg["event"]["welcome_message_id"] = em.id
            
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

async def ensure_category(guild: discord.Guild) -> discord.CategoryChannel:
    """Ensure a category exists, create if it doesn't"""
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)
    return category

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

        # Check if already installed - more strict check
        if cfg.get("mode"):
            current_mode = cfg.get("mode")
            live_feed.log(
                "Install attempt (already installed)",
                f"Guild: {guild.name} • Current mode: {current_mode} • Attempted mode: {mode} • By: {interaction.user}",
                guild,
                interaction.channel
            )
            return await interaction.followup.send(
                f"❌ Already installed in {current_mode} mode. Use `/uninstall` first to change modes.", 
                ephemeral=True
            )

        if mode not in ("auto", "manual"):
            live_feed.log(
                "Invalid install mode attempted",
                f"Guild: {guild.name} • Mode: {mode} • By: {interaction.user}",
                guild,
                interaction.channel
            )
            return await interaction.followup.send("❌ Unknown mode. Use `auto` or `manual`.", ephemeral=True)

        # Set the mode first so ensure_channel works correctly
        cfg["mode"] = mode
        save_config(gcfg)

        if mode == "auto":
            live_feed.log(
                "Starting auto-install",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel
            )
            await interaction.followup.send("⚙️ Auto-installing...", ephemeral=True)
            bot_member = guild.get_member(self.bot.user.id)

            # Ensure category once
            category = await ensure_category(guild)

            # Create all channels inside the same category
            bear_ch     = await ensure_channel(guild, BEAR_CHANNEL,     overwrites=locked_channel_perms(bot_member), category=category)
            bear_log    = await ensure_channel(guild, BEAR_LOG_CHANNEL, overwrites=locked_channel_perms(bot_member), category=category)
            arena_ch    = await ensure_channel(guild, ARENA_CHANNEL,    overwrites=locked_channel_perms(bot_member), category=category)
            event_ch    = await ensure_channel(guild, EVENT_CHANNEL,    overwrites=locked_channel_perms(bot_member), category=category)
            react_ch    = await ensure_channel(guild, REACTION_CHANNEL, overwrites=locked_channel_perms(bot_member, True), category=category)


            live_feed.log(
                "Created channels",
                f"Guild: {guild.name} • Category: {CATEGORY_NAME} • Channels: Bear, Bear Log, Arena, Event, Reaction",
                guild,
                interaction.channel
            )

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

            live_feed.log(
                "Created roles",
                f"Guild: {guild.name} • Roles: Bear, Arena, Event",
                guild,
                interaction.channel
            )

            # Send welcome messages
            bm = await bear_ch.send(embed=make_bear_welcome_embed(guild_id))
            am = await arena_ch.send(embed=make_arena_welcome_embed(guild_id))
            em = await event_ch.send(embed=make_event_welcome_embed(guild_id))
            
            # Store message IDs
            cfg["bear"]["welcome_message_id"] = bm.id
            cfg["arena"]["welcome_message_id"] = am.id
            cfg["event"]["welcome_message_id"] = em.id

            live_feed.log(
                "Sent welcome messages",
                f"Guild: {guild.name} • Channels: Bear, Arena, Event",
                guild,
                interaction.channel
            )

            if (a := self.bot.get_cog("ArenaScheduler")):
                await a.sync_now(guild)
            if (c := self.bot.get_cog("ReactionRole")):
                await c.setup_reactions(guild, react_ch)

            save_config(gcfg)
            live_feed.log(
                "Auto-install complete",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel
            )
            await interaction.followup.send("✅ Installation complete.", ephemeral=True)

        else:  # manual mode
            live_feed.log(
                "Starting manual install",
                f"Guild: {guild.name} • By: {interaction.user}",
                guild,
                interaction.channel
            )
            view = ManualChannelSelector(self.bot, interaction, gcfg)
            await interaction.followup.send(
                "⚙️ Please select channels and press Save 💾 below:", 
                view=view, ephemeral=True
            )

    @app_commands.command(name="uninstall", description="🗑️ Remove all bot channels, roles, and settings")
    async def uninstall(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        live_feed.log(
            "Starting uninstall",
            f"Guild: {guild.name} • By: {interaction.user}",
            guild,
            interaction.channel
        )

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
                    live_feed.log(
                        f"Deleted {role_key} role",
                        f"Guild: {guild.name} • Role: {role.name}",
                        guild,
                        interaction.channel
                    )
                except discord.Forbidden:
                    live_feed.log(
                        f"Failed to delete {role_key} role",
                        f"Guild: {guild.name} • Role: {role.name} • Error: No permission",
                        guild,
                        interaction.channel
                    )

        # Auto mode: delete channels & category
        if cfg.get("mode") == "auto":
            # First try to delete channels by their stored IDs
            channels_to_delete = []
            
            # Handle bear and bear log channels
            if bear_cfg := cfg.get("bear", {}):
                if channel_id := bear_cfg.get("channel_id"):
                    if channel := guild.get_channel(channel_id):
                        channels_to_delete.append(channel)
                if log_channel_id := bear_cfg.get("log_channel_id"):
                    if channel := guild.get_channel(log_channel_id):
                        channels_to_delete.append(channel)
            
            # Handle other channels
            for sect in ("arena", "event", "reaction"):
                if channel_id := cfg.get(sect, {}).get("channel_id"):
                    if channel := guild.get_channel(channel_id):
                        channels_to_delete.append(channel)

            # Delete each channel
            for channel in channels_to_delete:
                try:
                    await channel.delete(reason="Uninstall")
                    deleted_channels += 1
                    live_feed.log(
                        "Deleted channel",
                        f"Guild: {guild.name} • Channel: {channel.name}",
                        guild,
                        interaction.channel
                    )
                except discord.Forbidden:
                    live_feed.log(
                        "Failed to delete channel",
                        f"Guild: {guild.name} • Channel: {channel.name} • Error: No permission",
                        guild,
                        interaction.channel
                    )
                except discord.NotFound:
                    live_feed.log(
                        "Channel already deleted",
                        f"Guild: {guild.name} • Channel ID: {channel.id}",
                        guild,
                        interaction.channel
                    )

            # Try to delete the category regardless of whether it's empty
            category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
            if category:
                try:
                    # First try to move any remaining channels out of the category
                    for channel in category.channels:
                        try:
                            await channel.edit(category=None)
                        except (discord.Forbidden, discord.NotFound):
                            pass
                    
                    # Then delete the category
                    await category.delete(reason="Uninstall")
                    deleted_categories += 1
                    live_feed.log(
                        "Deleted category",
                        f"Guild: {guild.name} • Category: {category.name}",
                        guild,
                        interaction.channel
                    )
                except discord.Forbidden:
                    live_feed.log(
                        "Failed to delete category",
                        f"Guild: {guild.name} • Category: {category.name} • Error: No permission",
                        guild,
                        interaction.channel
                    )
                except discord.NotFound:
                    live_feed.log(
                        "Category already deleted",
                        f"Guild: {guild.name} • Category: {category.name}",
                        guild,
                        interaction.channel
                    )
        else:
            # Manual mode: purge bot messages only
            for sect in ("bear", "bear_log", "arena", "event", "reaction"):
                channel_id = cfg.get(sect, {}).get("channel_id")
                if channel_id and (channel := guild.get_channel(channel_id)):
                    def is_bot(m): return m.author.id == self.bot.user.id
                    try:
                        purged += len(await channel.purge(limit=100, check=is_bot))
                        if purged > 0:
                            live_feed.log(
                                "Purged bot messages",
                                f"Guild: {guild.name} • Channel: {channel.name} • Count: {purged}",
                                guild,
                                interaction.channel
                            )
                    except discord.Forbidden:
                        live_feed.log(
                            "Failed to purge messages",
                            f"Guild: {guild.name} • Channel: {channel.name} • Error: No permission",
                            guild,
                            interaction.channel
                        )

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
                    live_feed.log(
                        "Cancelled bear task",
                        f"Guild: {guild.name} • Bear ID: {ev.id}",
                        guild,
                        interaction.channel
                    )

        # Now remove the config entry
        gcfg.pop(guild_id, None)
        save_config(gcfg)

        live_feed.log(
            "Uninstall complete",
            f"Guild: {guild.name} • Stats: {deleted_roles} roles, {deleted_channels} channels, {deleted_categories} categories, {purged} messages",
            guild,
            interaction.channel
        )

        await interaction.followup.send(
            f"🧹 Uninstalled: {deleted_roles} roles deleted, {deleted_channels} channels deleted, {deleted_categories} categories deleted, {purged} messages purged.", 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Installer(bot))
