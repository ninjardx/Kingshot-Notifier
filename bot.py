# bot.py
import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from config import DEFAULT_ACTIVITY, DEFAULT_ACTIVITY_TYPE, DEFAULT_STATUS
import sys
from admin_tools import start_admin_tools

load_dotenv()  # ⬅️ This loads variables from .env into os.environ

# Development mode detection
DISCORD_ENABLED = os.getenv("DISCORD_ENABLED", "1") == "1"
if os.getenv("CODESPACES") or "codex" in sys.argv[0].lower():
    DISCORD_ENABLED = False
    logging.info("🔄 Development mode detected - Discord connection disabled")

# Validate token
token = os.getenv("KINGSHOT_DEV_TOKEN")

if not token and DISCORD_ENABLED:
    raise ValueError("❌ Bot token is missing. Set KINGSHOT_DEV_TOKEN in .env")


# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("kingshot")

# ─── Intents & Bot ───────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned, help_command=None, intents=intents)
bot.role_message_ids = {}

# ─── Cogs List ───
COGS = [    
    "cogs.reaction",
    "cogs.arena",
    "cogs.bear",
    "cogs.commands",
    "cogs.events",
    "cogs.installer",
    "cogs.ping_config"
]

async def dummy_lifecycle():
    """Keeps bot alive and lets all startup tasks/cogs initialize without Discord connection"""
    await asyncio.sleep(2)
    log.info("Dummy lifecycle complete (no Discord connection)")

# ─── Main Entrypoint ───
async def main():
    log.info("Starting Kingshot Bot...")
    try:
        if DISCORD_ENABLED:
            log.info("Connecting to Discord...")
            await bot.login(token)
            bot_task = asyncio.create_task(bot.connect())
            await bot.wait_until_ready()
        else:
            log.info("🚫 Discord gateway connection disabled (DEV MODE)")
            bot_task = asyncio.create_task(dummy_lifecycle())

        log.info("Loading cogs...")
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")
                if DISCORD_ENABLED:  # Only raise in production mode
                    raise

        if DISCORD_ENABLED:
            # Sync commands after all cogs are loaded
            log.info("Syncing commands...")
            synced = await bot.tree.sync()
            log.info(f"✅ Globally synced {len(synced)} commands.")
        
        # Keep the bot running
        await bot_task
        
    except Exception as e:
        log.exception("Bot encountered an exception:", exc_info=e)
        if DISCORD_ENABLED:  # Only exit in production mode
            sys.exit(1)
    finally:
        log.info("Shutting down bot...")
        if DISCORD_ENABLED:
            try:
                await bot.close()
            except Exception as e:
                log.error(f"Error during shutdown: {e}")

@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Start command center after bot is ready
    start_admin_tools(bot)
    log.info("Admin tools started")

    for guild in bot.guilds:
        log.info(f"Available in: {guild.name} ({guild.id})")
        
if __name__ == "__main__":
    asyncio.run(main())