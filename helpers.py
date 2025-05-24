# helpers.py

import asyncio
import json
from pathlib import Path
import discord

from config import CONFIG_PATH  # unify the path with config.py

# ─── Constants ──────────────────────────────────────────────
CATEGORY_NAME = "👑 Kingshot Bot"

# ─── Config File Helpers ────────────────────────────────────
# A queue to batch up config writes
_write_queue: asyncio.Queue[dict] = asyncio.Queue()

async def _config_writer():
    while True:
        data = await _write_queue.get()
        # drain any extra queued writes so we only write the most recent state
        while not _write_queue.empty():
            data = await _write_queue.get()
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _write_queue.task_done()

# start the writer as soon as this module is imported
asyncio.create_task(_config_writer())

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

# ─── Discord Setup Helpers ─────────────────────────────────
async def ensure_category(guild: discord.Guild) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not cat:
        cat = await guild.create_category(name=CATEGORY_NAME)
    return cat

async def ensure_channel(
    guild: discord.Guild,
    name: str,
    *,
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] | None = None,
    locked: bool = False
) -> discord.TextChannel:
    ch = discord.utils.get(guild.text_channels, name=name)
    if not ch:
        cat = await ensure_category(guild)
        if locked:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    send_messages=False,
                    add_reactions=False,
                    create_public_threads=False,
                    create_private_threads=False
                ),
                guild.me: discord.PermissionOverwrite(
                    send_messages=True,
                    manage_messages=True
                )
            }
        ch = await guild.create_text_channel(name, category=cat, overwrites=overwrites or {})
    return ch

async def ensure_role(
    guild: discord.Guild,
    name: str,
    color: discord.Color
) -> discord.Role:
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        role = await guild.create_role(
            name=name, color=color, mentionable=True,
            reason="Auto-created by /install"
        )
        try:
            bot_top = guild.me.top_role.position
            new_pos = max(1, bot_top - 1)
            await role.edit(position=new_pos)
        except Exception:
            pass
    return role
