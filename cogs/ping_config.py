import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Literal, Optional
from config_helpers import (
    get_bear_ping_settings, update_bear_ping_setting,
    get_arena_ping_settings, update_arena_ping_setting,
    get_event_ping_settings, update_event_ping_setting,
    get_all_ping_settings, ConfigValidationError,
    _load_config, _save_config
)
from welcome_embeds import (
    make_bear_welcome_embed,
    make_arena_welcome_embed,
    make_event_welcome_embed
)

logger = logging.getLogger(__name__)

async def sync_welcome_embed(bot: commands.Bot, guild_id: str, system: Literal["bear", "arena", "event"]) -> None:
    """Update the welcome embed for a specific system"""
    try:
        config = _load_config()
        guild_config = config.get(str(guild_id), {})
        
        # Get channel and message IDs
        channel_id = guild_config.get(system, {}).get("channel_id")
        message_id = guild_config.get(system, {}).get("welcome_message_id")
        
        if not channel_id:
            logger.warning(f"No channel ID found for {system} in guild {guild_id}")
            return
        
        channel = bot.get_channel(channel_id)
        if not channel:
            logger.warning(f"Could not find channel {channel_id} for {system} in guild {guild_id}")
            return
        
        # Generate new embed
        if system == "bear":
            embed = make_bear_welcome_embed(guild_id)
        elif system == "arena":
            embed = make_arena_welcome_embed(guild_id)
        else:  # event
            embed = make_event_welcome_embed(guild_id)
        
        # Update or send new message
        try:
            if message_id:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                logger.info(f"Updated {system} welcome message in guild {guild_id}")
            else:
                message = await channel.send(embed=embed)
                # Store the new message ID
                if system not in guild_config:
                    guild_config[system] = {}
                guild_config[system]["welcome_message_id"] = message.id
                _save_config(config)
                logger.info(f"Sent new {system} welcome message in guild {guild_id}")
        except discord.NotFound:
            # Message was deleted, send new one
            message = await channel.send(embed=embed)
            if system not in guild_config:
                guild_config[system] = {}
            guild_config[system]["welcome_message_id"] = message.id
            _save_config(config)
            logger.info(f"Recreated {system} welcome message in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error updating {system} welcome message in guild {guild_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in sync_welcome_embed for {system} in guild {guild_id}: {e}")

class PingConfig(commands.Cog):
    """Cog for managing notification ping settings"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="setbearpings")
    @app_commands.describe(
        phase="The notification phase to modify (incoming or pre-attack)",
        action="Whether to toggle the ping on/off or set its timing",
        value="For toggle: true/false, For set: minutes before event (1-60)"
    )
    @app_commands.choices(
        phase=[
            app_commands.Choice(name="incoming", value="incoming"),
            app_commands.Choice(name="pre_attack", value="pre_attack")
        ],
        action=[
            app_commands.Choice(name="toggle", value="toggle"),
            app_commands.Choice(name="set", value="set")
        ]
    )
    async def setbearpings(
        self,
        interaction: discord.Interaction,
        phase: str,
        action: Literal["toggle", "set"],
        value: str
    ):
        """Configure bear notification settings"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if action == "toggle":
                if value.lower() not in ["true", "false"]:
                    await interaction.followup.send("❌ For toggle action, value must be 'true' or 'false'", ephemeral=True)
                    return
                
                bool_value = value.lower() == "true"
                current_settings = get_bear_ping_settings(str(interaction.guild_id))
                
                if phase == "incoming":
                    if current_settings.incoming_enabled == bool_value:
                        await interaction.followup.send(f"ℹ️ Incoming ping already {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                        return
                    update_bear_ping_setting(str(interaction.guild_id), "incoming_enabled", bool_value)
                    await interaction.followup.send(f"✅ Incoming ping {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                
                elif phase == "pre_attack":
                    if current_settings.pre_attack_enabled == bool_value:
                        await interaction.followup.send(f"ℹ️ Pre-attack ping already {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                        return
                    update_bear_ping_setting(str(interaction.guild_id), "pre_attack_enabled", bool_value)
                    await interaction.followup.send(f"✅ Pre-attack ping {'enabled' if bool_value else 'disabled'}", ephemeral=True)
            
            elif action == "set":
                if phase != "pre_attack":
                    await interaction.followup.send("❌ Only pre-attack timing can be modified. Incoming ping is fixed at 60 minutes.", ephemeral=True)
                    return
                
                try:
                    offset = int(value)
                    update_bear_ping_setting(str(interaction.guild_id), "pre_attack_offset", offset)
                    await interaction.followup.send(f"✅ Pre-attack ping updated to {offset} minutes before the bear", ephemeral=True)
                except ValueError:
                    await interaction.followup.send("❌ For set action, value must be a number between 1-60 minutes", ephemeral=True)
            
            # Update welcome message after any change
            await sync_welcome_embed(self.bot, str(interaction.guild_id), "bear")
        
        except ConfigValidationError as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in setbearpings: {e}")
            await interaction.followup.send("❌ An error occurred while updating settings", ephemeral=True)
    
    @app_commands.command(name="setarenaping")
    @app_commands.describe(
        action="Whether to toggle the ping on/off or set its timing",
        value="For toggle: true/false, For set: minutes before arena (1-60)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="toggle", value="toggle"),
            app_commands.Choice(name="set", value="set")
        ]
    )
    async def setarenaping(
        self,
        interaction: discord.Interaction,
        action: Literal["toggle", "set"],
        value: str
    ):
        """Configure arena notification settings"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if action == "toggle":
                if value.lower() not in ["true", "false"]:
                    await interaction.followup.send("❌ For toggle action, value must be 'true' or 'false'", ephemeral=True)
                    return
                
                bool_value = value.lower() == "true"
                current_settings = get_arena_ping_settings(str(interaction.guild_id))
                
                if current_settings.ping_enabled == bool_value:
                    await interaction.followup.send(f"ℹ️ Arena ping already {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                    return
                
                update_arena_ping_setting(str(interaction.guild_id), "ping_enabled", bool_value)
                await interaction.followup.send(f"✅ Arena ping {'enabled' if bool_value else 'disabled'}", ephemeral=True)
            
            elif action == "set":
                try:
                    offset = int(value)
                    update_arena_ping_setting(str(interaction.guild_id), "ping_offset", offset)
                    await interaction.followup.send(f"✅ Arena ping updated to {offset} minutes before opening", ephemeral=True)
                except ValueError:
                    await interaction.followup.send("❌ For set action, value must be a number between 1-60 minutes", ephemeral=True)
            
            # Update welcome message after any change
            await sync_welcome_embed(self.bot, str(interaction.guild_id), "arena")
        
        except ConfigValidationError as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in setarenaping: {e}")
            await interaction.followup.send("❌ An error occurred while updating settings", ephemeral=True)
    
    @app_commands.command(name="seteventpings")
    @app_commands.describe(
        phase="The notification phase to modify (reminder or final call)",
        action="Whether to toggle the ping on/off or set its timing",
        value="For toggle: true/false, For set: minutes before event (1-60)"
    )
    @app_commands.choices(
        phase=[
            app_commands.Choice(name="reminder", value="reminder"),
            app_commands.Choice(name="final_call", value="final_call")
        ],
        action=[
            app_commands.Choice(name="toggle", value="toggle"),
            app_commands.Choice(name="set", value="set")
        ]
    )
    async def seteventpings(
        self,
        interaction: discord.Interaction,
        phase: str,
        action: Literal["toggle", "set"],
        value: str
    ):
        """Configure event notification settings"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if action == "toggle":
                if value.lower() not in ["true", "false"]:
                    await interaction.followup.send("❌ For toggle action, value must be 'true' or 'false'", ephemeral=True)
                    return
                
                bool_value = value.lower() == "true"
                current_settings = get_event_ping_settings(str(interaction.guild_id))
                
                if phase == "reminder":
                    if current_settings.reminder_enabled == bool_value:
                        await interaction.followup.send(f"ℹ️ Reminder ping already {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                        return
                    update_event_ping_setting(str(interaction.guild_id), "reminder_enabled", bool_value)
                    await interaction.followup.send(f"✅ Reminder ping {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                
                elif phase == "final_call":
                    if current_settings.final_call_enabled == bool_value:
                        await interaction.followup.send(f"ℹ️ Final call ping already {'enabled' if bool_value else 'disabled'}", ephemeral=True)
                        return
                    update_event_ping_setting(str(interaction.guild_id), "final_call_enabled", bool_value)
                    await interaction.followup.send(f"✅ Final call ping {'enabled' if bool_value else 'disabled'}", ephemeral=True)
            
            elif action == "set":
                try:
                    offset = int(value)
                    if phase == "reminder":
                        update_event_ping_setting(str(interaction.guild_id), "reminder_offset", offset)
                        await interaction.followup.send(f"✅ Reminder ping updated to {offset} minutes before event", ephemeral=True)
                    elif phase == "final_call":
                        update_event_ping_setting(str(interaction.guild_id), "final_call_offset", offset)
                        await interaction.followup.send(f"✅ Final call ping updated to {offset} minutes before event", ephemeral=True)
                except ValueError:
                    await interaction.followup.send("❌ For set action, value must be a number between 1-60 minutes", ephemeral=True)
            
            # Update welcome message after any change
            await sync_welcome_embed(self.bot, str(interaction.guild_id), "event")
        
        except ConfigValidationError as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in seteventpings: {e}")
            await interaction.followup.send("❌ An error occurred while updating settings", ephemeral=True)
    
    @app_commands.command(name="viewsettings")
    async def viewsettings(self, interaction: discord.Interaction):
        """📋 View all notification settings"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            settings = get_all_ping_settings(str(interaction.guild_id))
            
            embed = discord.Embed(
                title="📋 Notification Settings Overview",
                color=discord.Color.blue()
            )
            
            # Bear settings
            bear = settings["bear"]
            bear_text = (
                f"**Incoming Ping:** {'✅ Enabled' if bear['incoming_enabled'] else '❌ Disabled'} (60 minutes)\n"
                f"**Pre-Attack Ping:** {'✅ Enabled' if bear['pre_attack_enabled'] else '❌ Disabled'} ({bear['pre_attack_offset']} minutes)"
            )
            embed.add_field(name="🐻 Bear Notifications", value=bear_text, inline=False)
            
            # Arena settings
            arena = settings["arena"]
            arena_text = f"**Arena Ping:** {'✅ Enabled' if arena['ping_enabled'] else '❌ Disabled'} ({arena['ping_offset']} minutes)"
            embed.add_field(name="⚔ Arena Notifications", value=arena_text, inline=False)
            
            # Event settings
            event = settings["event"]
            event_text = (
                f"**Reminder Ping:** {'✅ Enabled' if event['reminder_enabled'] else '❌ Disabled'} ({event['reminder_offset']} minutes)\n"
                f"**Final Call Ping:** {'✅ Enabled' if event['final_call_enabled'] else '❌ Disabled'} ({event['final_call_offset']} minutes)"
            )
            embed.add_field(name="🏆 Event Notifications", value=event_text, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in viewsettings: {e}")
            await interaction.followup.send("❌ An error occurred while fetching settings", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PingConfig(bot)) 