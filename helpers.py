# helpers.py

import asyncio
import json
from pathlib import Path
import discord
from discord.ext import commands

from config import gcfg, CONFIG_PATH  # unify the path with config.py

# ─── Constants ──────────────────────────────────────────────
CATEGORY_NAME = "👑 Kingshot Bot"

# ─── Config File Helpers ────────────────────────────────────
# A queue to batch up config writes
_write_queue: asyncio.Queue[dict] = asyncio.Queue()
_config_writer_task = None


async def _config_writer():
    while True:
        data = await _write_queue.get()
        # drain any extra queued writes so we only write the most recent state
        while not _write_queue.empty():
            data = await _write_queue.get()
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _write_queue.task_done()


def start_config_writer():
    """Start the config writer task. Call this when the bot is running."""
    global _config_writer_task
    if _config_writer_task is None:
        _config_writer_task = asyncio.create_task(_config_writer())


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict) -> None:
    """
    Enqueue the latest config state for writing.
    The background writer will coalesce rapid calls and write only the newest.
    """
    # make a shallow copy to avoid mutation issues
    _write_queue.put_nowait(cfg.copy())


def is_installed(guild_id: int) -> bool:
    from config import gcfg

    return str(guild_id) in gcfg and gcfg[str(guild_id)].get("mode") in (
        "auto",
        "manual",
    )


# ─── Discord Setup Helpers ─────────────────────────────────
async def ensure_category(guild: discord.Guild) -> discord.CategoryChannel:
    if not is_installed(guild.id):
        return None
    cat = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not cat:
        cat = await guild.create_category(name=CATEGORY_NAME)
    return cat


async def ensure_channel(
    guild: discord.Guild,
    name: str,
    *,
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] | None = None,
    locked: bool = False,
    category: discord.CategoryChannel | None = None,
) -> discord.TextChannel | None:
    ch = discord.utils.get(guild.text_channels, name=name)
    if ch:
        return ch

    # 🛡 Only create channel if the server is installed
    if not is_installed(guild.id):
        return None

    # Get or create category if not provided
    if category is None:
        category = await ensure_category(guild)

    if locked:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            ),
            guild.me: discord.PermissionOverwrite(
                send_messages=True, manage_messages=True
            ),
        }

    ch = await guild.create_text_channel(
        name, category=category, overwrites=overwrites or {}
    )
    return ch


async def ensure_role(
    guild: discord.Guild, name: str, color: discord.Color
) -> discord.Role | None:
    role = discord.utils.get(guild.roles, name=name)
    if role:
        return role

    # 🛡 Prevent role creation in uninstalled servers
    if not is_installed(guild.id):
        return None

    role = await guild.create_role(
        name=name, color=color, mentionable=True, reason="Auto-created by /install"
    )
    try:
        bot_top = guild.me.top_role.position
        new_pos = max(1, bot_top - 1)
        await role.edit(position=new_pos)
    except Exception:
        pass

    return role


# ─── Guild Tracking ─────────────────────────────────────────
async def update_guild_count(bot: commands.Bot) -> None:
    """Update master guild voice channel name with current server count."""
    from config import MASTER_GUILD_ID, SERVER_COUNT_CHANNEL_ID

    guild = bot.get_guild(MASTER_GUILD_ID)
    if not guild:
        return

    channel = guild.get_channel(SERVER_COUNT_CHANNEL_ID)
    if not isinstance(channel, discord.VoiceChannel):
        return

    new_name = f"{len(bot.guilds)}-servers!"
    if channel.name != new_name:
        try:
            await channel.edit(name=new_name)
        except discord.Forbidden:
            pass
