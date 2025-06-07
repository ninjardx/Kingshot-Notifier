Guidelines for AI agents (e.g. OpenAI Codex) working in this repository.

🧠 Code Style
🧼 Format all Python files using Black.

🐍 Follow PEP8 where applicable, especially for spacing and line length.

✏️ Use descriptive variable names; avoid unnecessary abbreviations.

🚫 Do not use wildcard imports (from x import *).

🧱 Maintain clear sectioning with emoji-style headers and consistent comments where possible.

✅ Bot Behavior Overview
The bot is a multi-server Discord assistant for timed events, reaction roles, and automated notifications.

Event logic is stored and restored from bot_config.json on startup.

All slash commands use discord.py app_commands and rely on cog-based modular design.

📦 File Conventions
bot.py: Main entrypoint; loads all cogs and starts the bot with token from environment.

config.py: Central constants and embed configuration.

helpers.py: Shared utility functions (channel/role setup, config save).

bot_config.json: Persistent config state for each server.

All cogs live in cogs/, each handling a specific function (e.g. bear.py, arena.py).

🧪 Testing Instructions
Always restart the bot after modifying cogs or config logic.

Run install and uninstall commands in a test guild to ensure proper setup/cleanup.

Use Discord's developer mode to validate embed formatting and reaction-role behavior.

🔧 PR Instructions
Title Format:
[Fix], [Feat], [Refactor], or [Cleanup] + short summary.
Example: [Feat] Add embed support for event countdowns

Description Sections:

Summary: One-line explanation of the change.

Testing Done: Describe test steps and expected outcomes.

Checklist Before PR Merge:

 Lint passes (flake8)

 Format checked (black)

 Cog loads cleanly in bot.py

 Slash commands respond as expected

🔒 Secrets & Env
Do not commit secrets like bot tokens.

.env or environment variables should contain:
KINGSHOT_BOT_TOKEN=your_token_here