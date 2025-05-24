# 📦 Kingshot Bot – Repo Manifest

A robust multi-server Discord bot designed for **event automation**, **reaction roles**, and **immersive notifications**. Built with reliability, dynamic embeds, and full slash command support.

---

## 📂 Root Files

- **`bot.py`** – Main startup script. Loads cogs, initializes the bot client, and syncs global slash commands.
- **`bot_config.json`** – Persistent per-guild config file storing channel IDs, role IDs, events, bears, and message tracking.
- **`config.py`** – Defines global constants, default settings, emoji maps, and loads the config file.
- **`helpers.py`** – Utility functions for async-safe config saves and Discord resource setup (roles/channels).

---

## 📂 Cogs (Features)

### ⚙️ `installer.py`
- Slash commands: `/install auto`, `/install manual`, `/uninstall`
- Handles full or custom setup of:
  - Bear, Arena, Events, Reaction channels
  - Roles for each module
  - Welcome embeds
- Detects existing installations and prevents redundant setup.

### 🐻 `bear.py`
- New per-event Bear Scheduler system.
- Phases: `scheduled`, `incoming`, `pre_attack`, `attack`, `victory`
- Each bear has an async task managing phase transitions and pings.
- Features:
  - Dynamic embeds and ping cleanup
  - Ping deduplication by scanning channel history
  - Slash commands:
    - `/setbeartime`
    - `/listbears`
    - `/cancelbear`

### ⚔️ `arena.py`
- Daily arena phase automation (scheduled/open).
- Posts an arena embed and role ping during open window.
- Self-correcting across restarts.
- Manual override: `sync_now()` to update embed immediately.

### 🏆 `events.py`
- Full lifecycle support for scheduled game events.
- Add events manually or via template.
- Sends embeds and automated pings at:
  - 1 hour before
  - 10 minutes before
  - Event start
- Slash commands:
  - `/addevent`
  - `/listevents`
  - `/cancelevent`

### 📜 `reaction.py`
- Persistent reaction-role system with emoji-role mapping.
- Auto-restores roles on bot startup.
- Locked channel UI to prevent tampering.
- Uses a single embed message, tracked via config.

### 💬 `commands.py`
- Core commands and listeners.
- Slash commands:
  - `/help` – comprehensive command overview
  - `/synccommands` – force re-sync of slash commands
  - `/purge` – delete recent messages
  - `/embed` – create custom embeds (admin-only)
- Sends welcome embed on joining a new guild.

---

## 📂 Emoji & Branding

- 🐻 Bear Phase Emojis and Thumbnails: mapped via `config.py > EMOJI_THUMBNAILS`
- 🏆 Event Templates and Thumbnails: see `EMOJI_THUMBNAILS_EVENTS`
- Footer branding and bot avatar applied throughout embeds.

---

## 🧪 Development Notes

- Changes to `bot_config.json` are queued via `helpers.py` to minimize write operations.
- All times are managed in **UTC** for consistency.
- Use `/uninstall` before switching setup mode (auto <-> manual).
- Ensure the bot’s top role is above reaction roles for permission success.

---

## ✅ Slash Commands Summary

| Module    | Command              | Description                         |
|-----------|----------------------|-------------------------------------|
| Installer | `/install`           | Setup bot in a guild (auto/manual)  |
| Installer | `/uninstall`         | Cleanup bot setup from a guild      |
| Bear      | `/setbeartime`       | Schedule a bear attack              |
| Bear      | `/listbears`         | List all bears                      |
| Bear      | `/cancelbear`        | Cancel an upcoming bear             |
| Events    | `/addevent`          | Schedule a new event                |
| Events    | `/listevents`        | List upcoming events                |
| Events    | `/cancelevent`       | Cancel an event                     |
| Utility   | `/help`              | View full bot guide                 |
| Utility   | `/purge`             | Delete messages in bulk             |
| Utility   | `/embed`             | Create custom embed (admins only)   |
| Utility   | `/synccommands`      | Force command re-sync               |

---

