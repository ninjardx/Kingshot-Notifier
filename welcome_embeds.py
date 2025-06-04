import discord
from typing import List, Tuple
from config_helpers import (
    get_bear_ping_settings,
    get_arena_ping_settings,
    get_event_ping_settings
)

# Common embed settings
EMBED_COLOR = discord.Color.blue()
FOOTER_TEXT = "Settings can be modified using /setbearpings, /setarenaping, or /seteventpings"

def _format_phase_line(emoji: str, name: str, description: str) -> str:
    """Format a single phase line with consistent styling"""
    return f"{emoji} **{name}** — {description}"

def make_bear_welcome_embed(guild_id: str) -> discord.Embed:
    """Generate a welcome embed for bear notifications based on current settings"""
    settings = get_bear_ping_settings(guild_id)
    
    # Build the description lines
    lines: List[str] = [
        "📢 **This channel posts upcoming Bear attack phases!**\n"
    ]
    
    # Add enabled phases in chronological order
    if settings.incoming_enabled:
        lines.append(_format_phase_line("⏱️", "Incoming", "60 minutes before the Bear"))
    
    if settings.pre_attack_enabled:
        lines.append(_format_phase_line("🎯", "Pre-Attack", f"{settings.pre_attack_offset} minutes before impact"))
    
    # Always include attack and victory phases
    lines.extend([
        _format_phase_line("💥", "Attack", "when the Bear arrives"),
        _format_phase_line("🏆", "Victory", "when the Bear is slain!")
    ])
    
    embed = discord.Embed(
        title="🐻 Bear Attack Notifications",
        description="\n".join(lines),
        color=EMBED_COLOR
    )
    
    # Add a note if all pings are disabled
    if not settings.incoming_enabled and not settings.pre_attack_enabled:
        embed.add_field(
            name="ℹ️ Note",
            value="All notification pings are currently disabled. Use `/setbearpings` to enable them.",
            inline=False
        )
    
    embed.set_footer(text=FOOTER_TEXT)
    return embed

def make_arena_welcome_embed(guild_id: str) -> discord.Embed:
    """Generate a welcome embed for arena notifications based on current settings"""
    settings = get_arena_ping_settings(guild_id)
    
    # Build the description lines
    lines: List[str] = [
        "📢 **This channel posts Arena opening notifications!**\n"
    ]
    
    # Add the ping phase if enabled
    if settings.ping_enabled:
        lines.append(_format_phase_line("⚔", "Opening Soon", f"{settings.ping_offset} minutes before the Arena opens"))
    
    # Always include the opening phase
    lines.append(_format_phase_line("🎯", "Arena Open", "when the Arena becomes available"))
    
    embed = discord.Embed(
        title="⚔ Arena Notifications",
        description="\n".join(lines),
        color=EMBED_COLOR
    )
    
    # Add a note if pings are disabled
    if not settings.ping_enabled:
        embed.add_field(
            name="ℹ️ Note",
            value="Notification pings are currently disabled. Use `/setarenaping` to enable them.",
            inline=False
        )
    
    embed.set_footer(text=FOOTER_TEXT)
    return embed

def make_event_welcome_embed(guild_id: str) -> discord.Embed:
    """Generate a welcome embed for event notifications based on current settings"""
    settings = get_event_ping_settings(guild_id)
    
    # Build the description lines
    lines: List[str] = [
        "📢 **This channel posts upcoming Event notifications!**\n"
    ]
    
    # Add enabled phases in chronological order
    if settings.reminder_enabled:
        lines.append(_format_phase_line("⏰", "Event Reminder", f"{settings.reminder_offset} minutes before start"))
    
    if settings.final_call_enabled:
        lines.append(_format_phase_line("🔔", "Final Call", f"{settings.final_call_offset} minutes before start"))
    
    # Always include the event start phase
    lines.append(_format_phase_line("🎯", "Event Start", "when the event begins"))
    
    embed = discord.Embed(
        title="🏆 Event Notifications",
        description="\n".join(lines),
        color=EMBED_COLOR
    )
    
    # Add a note if all pings are disabled
    if not settings.reminder_enabled and not settings.final_call_enabled:
        embed.add_field(
            name="ℹ️ Note",
            value="All notification pings are currently disabled. Use `/seteventpings` to enable them.",
            inline=False
        )
    
    embed.set_footer(text=FOOTER_TEXT)
    return embed

def get_all_welcome_embeds(guild_id: str) -> Tuple[discord.Embed, discord.Embed, discord.Embed]:
    """Get all welcome embeds for a guild"""
    return (
        make_bear_welcome_embed(guild_id),
        make_arena_welcome_embed(guild_id),
        make_event_welcome_embed(guild_id)
    ) 