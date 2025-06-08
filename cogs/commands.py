# cogs/commands.py

import logging
import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction, Embed

from config import EMBED_COLOR_PRIMARY
from helpers import ensure_channel
from admin_tools import live_feed

log = logging.getLogger("kingshot")


class Core(commands.Cog):
    """Core listeners and admin sync command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        log.info(f"Joined guild: {guild.name} ({guild.id})")
        live_feed.log(
            "Bot joined new guild",
            f"Guild: {guild.name} • Members: {guild.member_count}",
            guild,
            None
        )
        # Send a welcome embed in the system channel or first writable channel
        dest = guild.system_channel or next(
            (c for c in guild.text_channels
             if c.permissions_for(guild.me).send_messages),
            None
        )
        if not dest:
            live_feed.log(
                "Failed to send welcome message",
                f"Guild: {guild.name} • Error: No suitable channel found",
                guild,
                None
            )
            return

        embed = Embed(
            title="👑 Kingshot Bot Has Arrived!",
            description=(
                "Thanks for inviting **Kingshot Bot** to your server!\n\n"
                "To get started, run `/install auto` and I'll create everything you need.\n"
                "Prefer to choose your own channels? Use `/install manual` instead.\n\n"
                "Need help? Use `/help` for a full list of commands."
            ),
            color=EMBED_COLOR_PRIMARY
        )
        embed.set_thumbnail(
            url=self.bot.user.avatar.url
                if self.bot.user.avatar
                else discord.Embed.Empty
        )
        embed.set_footer(
            text="made by ninjardx 🏆",
            icon_url=self.bot.user.avatar.url
                if self.bot.user.avatar
                else discord.Embed.Empty
        )
        await dest.send(embed=embed)
        live_feed.log(
            "Sent welcome message",
            f"Guild: {guild.name} • Channel: #{dest.name}",
            guild,
            dest
        )

    @app_commands.command(
        name="synccommands",
        description="🔧 Force sync of slash commands (Admins only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def synccommands(self, interaction: Interaction):
        """Sync the bot's slash commands to this server."""
        await interaction.response.defer(ephemeral=True)
        live_feed.log(
            "Syncing commands",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )
        synced = await self.bot.tree.sync(guild=interaction.guild)
        live_feed.log(
            "Commands synced",
            f"Guild: {interaction.guild.name} • Count: {len(synced)}",
            interaction.guild,
            interaction.channel
        )
        await interaction.followup.send(
            f"✅ Synced {len(synced)} commands to this server.",
            ephemeral=True
        )


class General(commands.Cog):
    """General utility slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="💠View all Kingshot Bot commands"
    )
    async def help(self, interaction: Interaction):
        """Show help information."""
        live_feed.log(
            "Help command used",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )
        embed = Embed(
            title="🤴 Kingshot Bot • Help",
            description=(
        "**Here's what I can do:**\n\n"
        "🛠️ **Admin Commands:**\n"
        "• `/install auto` — full automatic setup\n"
        "• `/install manual` — select your own channels\n"
        "• `/uninstall` — remove all bot channels/roles\n\n"
        "<:BEAREVENT:1375520846407270561> **Bear Events:**\n"
        "• `/setbeartime` — schedule a Bear attack\n"
        "• `/listbears` — list scheduled Bears\n"
        "• `/cancelbear` — cancel a Bear event\n\n"
        "⚔️ **Arena Battles:**\n"
        "• (Automatically posted daily)\n\n"
        "🏆 **Events:**\n"
        "• `/addevent` — schedule a new event\n"
        "• `/listevents` — list upcoming events\n"
        "• `/cancelevent` — cancel an event\n\n"
        "📣 **Notifications:**\n"
        "• `/viewsettings` — show current ping settings\n"
        "• `/setarenaping` — configure arena pings\n"
        "• `/setbearpings` — configure bear pings\n"
        "• `/seteventpings` — configure event pings\n\n"
        "🪄 **Misc:**\n"
        "• `/embed` — create an embed message with the bot\n"
        "• `/synccommands` — force sync of slash commands\n"
        "• `/purge` — quickly remove messages\n\n"
        "📌 **[Join the support server](https://discord.gg/MPFdHdQXzf)**"
            ),
            color=EMBED_COLOR_PRIMARY
        )
        embed.set_footer(
            text="Kingshot Bot • created by ninjardx 👑",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="purge",
        description="🧹 Delete a number of recent user messages in this channel"
    )
    @app_commands.describe(amount="How many messages to consider (1–100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: Interaction, amount: int):
        """Purge recent non-bot messages in the current channel."""
        await interaction.response.defer(ephemeral=True)
        ch = interaction.channel
        if not isinstance(ch, discord.TextChannel):
            live_feed.log(
                "Purge failed",
                f"Guild: {interaction.guild.name} • Error: Invalid channel type",
                interaction.guild,
                interaction.channel
            )
            return await interaction.followup.send(
                "❌ Could not determine the channel.", ephemeral=True
            )

        live_feed.log(
            "Starting message purge",
            f"Guild: {interaction.guild.name} • Channel: #{ch.name} • Amount: {amount} • By: {interaction.user}",
            interaction.guild,
            ch
        )

        # Clamp between 1 and 100
        limit = max(1, min(amount, 100))
        # Bulk-delete up to `limit` of the most recent non-bot messages
        deleted = await ch.purge(
            limit=limit,
            check=lambda m: not m.author.bot
        )
        # Any bot messages within those `limit` were skipped
        kept = limit - len(deleted)

        live_feed.log(
            "Purge complete",
            f"Guild: {interaction.guild.name} • Channel: #{ch.name} • Deleted: {len(deleted)} • Kept: {kept}",
            interaction.guild,
            ch
        )

        await interaction.followup.send(
            f"✅ Deleted {len(deleted)} message(s), kept {kept} bot message(s).",
            ephemeral=True
        )


class EmbedModal(ui.Modal, title="Create an Embed"):
    """Modal dialog for creating a custom embed."""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.title_input = ui.TextInput(
            label="Title",
            required=True,
            max_length=256
        )
        self.description_input = ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.footer_input = ui.TextInput(
            label="Footer (optional)",
            required=False,
            max_length=256
        )
        self.thumbnail_input = ui.TextInput(
            label="Thumbnail URL (optional)",
            required=False
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.footer_input)
        self.add_item(self.thumbnail_input)

    async def on_submit(self, interaction: Interaction):
        live_feed.log(
            "Embed created",
            f"Guild: {interaction.guild.name} • By: {interaction.user} • Title: {self.title_input.value[:30]}...",
            interaction.guild,
            interaction.channel
        )
        embed = Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=EMBED_COLOR_PRIMARY
        )
        if self.footer_input.value:
            embed.set_footer(
                text=self.footer_input.value,
                icon_url=(
                    self.bot.user.avatar.url
                    if self.bot.user.avatar
                    else discord.Embed.Empty
                )
            )
        if self.thumbnail_input.value:
            embed.set_thumbnail(url=self.thumbnail_input.value)
        await interaction.response.send_message(embed=embed, ephemeral=False)


class Utility(commands.Cog):
    """Utility commands that require mod/admin permissions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="embed",
        description="📄 Open a popup to create an embedded message (Admins only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def embed(self, interaction: Interaction):
        """Show the Embed creation modal."""
        live_feed.log(
            "Embed creation started",
            f"Guild: {interaction.guild.name} • By: {interaction.user}",
            interaction.guild,
            interaction.channel
        )
        await interaction.response.send_modal(EmbedModal(self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
    await bot.add_cog(General(bot))
    await bot.add_cog(Utility(bot))
