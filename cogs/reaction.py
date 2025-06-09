# cogs/reaction.py
import discord
from discord.ext import commands

import logging
from helpers import save_config
from config import ROLE_EMOJIS, gcfg
from admin_tools import live_feed

log = logging.getLogger("kingshot")


class ReactionRole(commands.Cog):
    """Handles reaction-role setup and add/remove events."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load persisted message IDs from unified config
        for guild_id, guild_cfg in gcfg.items():
            rr = guild_cfg.get("reaction", {})
            msg_id = rr.get("message_id")
            if msg_id:
                self.bot.role_message_ids[int(guild_id)] = msg_id

    async def setup_reactions(
        self, guild: discord.Guild, channel: discord.TextChannel
    ) -> discord.Message:
        """Send the embed, add reactions, and persist."""
        live_feed.log(
            "Setting up reaction roles",
            f"Guild: {guild.name} • Channel: #{channel.name}",
            guild,
            channel,
        )
        embed = discord.Embed(
            title="📜 Choose Your Adventure!",
            description=(
                "React below to gain access to special event pings!\n\n"
                "🐻 — **Bear Alerts**: Get notified before bear attacks\n"
                "⚔️ — **Arena Battles**: Be there when the arena opens\n"
                "🏆 — **Event Alerts**: Stay in the loop for in game events!"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="👑 Kingshot Bot • Role Reactions • UTC")
        embed.set_thumbnail(url="")

        msg = await channel.send(embed=embed)
        for emoji in ROLE_EMOJIS:
            await msg.add_reaction(emoji)

        # Persist in unified config.json
        guild_cfg = gcfg.setdefault(str(guild.id), {})
        guild_cfg["reaction"] = {"channel_id": channel.id, "message_id": msg.id}
        save_config(gcfg)

        # Also keep in memory
        self.bot.role_message_ids[guild.id] = msg.id

        live_feed.log(
            "Reaction role message created",
            f"Guild: {guild.name} • Channel: #{channel.name} • Message ID: {msg.id}",
            guild,
            channel,
        )

        # 🔁 Process existing reactions and apply roles immediately
        for reaction in msg.reactions:
            async for user in reaction.users():
                if user.bot:
                    continue
                member = guild.get_member(user.id)
                if not member:
                    continue
                await self.handle_reaction_logic(member, reaction.emoji, msg)

    async def handle_reaction_logic(
        self,
        member: discord.Member,
        emoji: discord.PartialEmoji | str,
        msg: discord.Message,
    ):
        """
        Add the role corresponding to this emoji on setup or on_existing.
        """
        role_name = ROLE_EMOJIS.get(str(emoji))
        if not role_name or member.bot:
            return

        role = discord.utils.get(member.guild.roles, name=role_name)
        if role and role not in member.roles:
            try:
                # Track roles before applying the new one
                before_roles = set(member.roles)
                await member.add_roles(role)
                # Determine which reaction roles were newly added
                new_roles = [
                    r
                    for r in member.roles
                    if r.name in ROLE_EMOJIS.values() and r not in before_roles
                ]
                if new_roles:
                    role_names = ", ".join(r.name for r in new_roles)
                    live_feed.log(
                        "Roles added via reaction",
                        f"Guild: {member.guild.name} • User: {member} • Roles: {role_names}",
                        member.guild,
                        msg.channel,
                    )
            except discord.Forbidden:
                log.warning(f"Cannot add role {role.name} to {member}.")
                live_feed.log(
                    "Failed to add role via reaction",
                    f"Guild: {member.guild.name} • User: {member} • Role: {role.name} • Error: No permission",
                    member.guild,
                    msg.channel,
                )

        return msg

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        # Check if this is a reaction-role message
        if payload.guild_id not in self.bot.role_message_ids:
            return
        if payload.message_id != self.bot.role_message_ids[payload.guild_id]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role_name = ROLE_EMOJIS.get(str(payload.emoji))
        if not role_name:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                # Track roles before adding the reaction role
                before_roles = set(member.roles)
                await member.add_roles(role)
                # Determine which reaction roles were newly added
                new_roles = [
                    r
                    for r in member.roles
                    if r.name in ROLE_EMOJIS.values() and r not in before_roles
                ]
                if new_roles:
                    role_names = ", ".join(r.name for r in new_roles)
                    live_feed.log(
                        "Roles added via reaction",
                        f"Guild: {guild.name} • User: {member} • Roles: {role_names}",
                        guild,
                        None,
                    )
            except discord.Forbidden:
                log.warning(f"Cannot add role {role.name} to {member}.")
                live_feed.log(
                    "Failed to add role via reaction",
                    f"Guild: {guild.name} • User: {member} • Role: {role.name} • Error: No permission",
                    guild,
                    None,
                )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if payload.guild_id not in self.bot.role_message_ids:
            return
        if payload.message_id != self.bot.role_message_ids[payload.guild_id]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role_name = ROLE_EMOJIS.get(str(payload.emoji))
        if not role_name:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                # Get current roles before removing
                current_roles = set(member.roles)
                await member.remove_roles(role)
                # Get all roles that were removed
                removed_roles = [
                    r
                    for r in current_roles
                    if r.name in ROLE_EMOJIS.values() and r not in member.roles
                ]
                if removed_roles:
                    role_names = ", ".join(r.name for r in removed_roles)
                    live_feed.log(
                        "Roles removed via reaction",
                        f"Guild: {guild.name} • User: {member} • Roles: {role_names}",
                        guild,
                        None,
                    )
            except discord.Forbidden:
                log.warning(f"Cannot remove role {role.name} from {member}.")
                live_feed.log(
                    "Failed to remove role via reaction",
                    f"Guild: {guild.name} • User: {member} • Role: {role.name} • Error: No permission",
                    guild,
                    None,
                )

    @commands.Cog.listener()
    async def on_ready(self):
        # Load existing reaction-role messages on startup
        for guild in self.bot.guilds:
            guild_cfg = gcfg.get(str(guild.id), {})
            rr = guild_cfg.get("reaction", {})
            chan_id = rr.get("channel_id")
            msg_id = rr.get("message_id")

            if not chan_id or not msg_id:
                continue

            ch = guild.get_channel(chan_id)
            if not isinstance(ch, discord.TextChannel):
                continue

            try:
                msg = await ch.fetch_message(msg_id)
                live_feed.log(
                    "Loaded reaction role message",
                    f"Guild: {guild.name} • Channel: #{ch.name} • Message ID: {msg_id}",
                    guild,
                    ch,
                )
            except (discord.NotFound, discord.Forbidden):
                live_feed.log(
                    "Failed to load reaction role message",
                    f"Guild: {guild.name} • Channel ID: {chan_id} • Message ID: {msg_id} • Error: Message not found",
                    guild,
                    None,
                )
                continue

            self.bot.role_message_ids[guild.id] = msg.id

            # 🔁 Process reactions and apply roles
            # Track roles added per member to avoid duplicate logs
            member_roles_added = {}
            for reaction in msg.reactions:
                async for user in reaction.users():
                    if user.bot:
                        continue
                    member = guild.get_member(user.id)
                    if not member:
                        continue
                    role_name = ROLE_EMOJIS.get(str(reaction.emoji))
                    if role_name:
                        role = discord.utils.get(guild.roles, name=role_name)
                        if role and role not in member.roles:
                            try:
                                await member.add_roles(role)
                                if member.id not in member_roles_added:
                                    member_roles_added[member.id] = set()
                                member_roles_added[member.id].add(role)
                            except discord.Forbidden:
                                log.warning(f"Cannot add role {role.name} to {member}.")
                                live_feed.log(
                                    "Failed to add role via reaction",
                                    f"Guild: {guild.name} • User: {member} • Role: {role.name} • Error: No permission",
                                    guild,
                                    ch,
                                )

            # Log all roles added per member
            for member_id, roles in member_roles_added.items():
                member = guild.get_member(member_id)
                if member and roles:
                    role_names = ", ".join(r.name for r in roles)
                    live_feed.log(
                        "Roles added via reaction (startup)",
                        f"Guild: {guild.name} • User: {member} • Roles: {role_names}",
                        guild,
                        ch,
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
