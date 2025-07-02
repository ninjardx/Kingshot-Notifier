# 🏹 Kingshot Bot

A powerful multi-server Discord bot designed for gaming communities, featuring comprehensive event automation, reaction roles, and customizable notification systems. Built with reliability, dynamic embeds, and full slash command support.

---

## 🚀 Core Features

### 🐻 **Bear Attack System**
- **Multi-phase scheduling** with automatic progression
- **Customizable notifications** at 60min (incoming), pre-attack (1-60min), and attack phases
- **Dynamic embeds** that update automatically
- **Smart ping cleanup** to prevent spam
- **Role-based notifications** with @here fallback

### ⚔️ **Arena Scheduler**
- **Daily arena automation** with scheduled opening times
- **Customizable pre-arena notifications** (1-60 minutes before)
- **Self-correcting system** that syncs across bot restarts
- **Role-based pings** for arena participants

### 🏆 **Event Management**
- **Custom event scheduling** with manual or template-based creation
- **Multi-phase notifications** (reminder + final call)
- **Rich event embeds** with thumbnails and descriptions
- **Event lifecycle management** with automatic cleanup

### 📜 **Reaction Role System**
- **Persistent emoji-role mapping** (🐻 Bear, ⚔️ Arena, 🏆 Events)
- **Auto-restoration** on bot startup
- **Locked channel UI** to prevent tampering
- **Single embed interface** for easy management

### ⚙️ **Advanced Configuration**
- **Per-guild notification settings** for all systems
- **Customizable timing** for all notification phases
- **Welcome embeds** that reflect current settings
- **Auto/manual installation modes**

---

## 🛠️ Installation
**Use this link to add the bot to your server!**
https://discord.com/oauth2/authorize?client_id=1366499729923379271&permissions=139855391824&integration_type=0&scope=bot+applications.commands

### Support server
**join the support server to be notified of updates!**
[**Join the support server here!**](https://discord.gg/MPFdHdQXzf)

### Required Permissions
- **Send Messages** - Core functionality
- **Embed Links** - Rich notifications
- **Add Reactions** - Reaction roles
- **Manage Messages** - Content cleanup
- **Read Message History** - Reaction handling
- **Manage Roles** - Role assignment
- **Manage Channels** - Setup process

---

## 📋 Command Reference

### 🏗️ **Setup Commands**
| Command | Description |
|---------|-------------|
| `/install auto` | Automatic setup with default channels |
| `/install manual` | Manual channel selection setup |
| `/uninstall` | Remove all bot channels and roles |

### 🐻 **Bear Commands**
| Command | Description |
|---------|-------------|
| `/setbeartime` | Schedule a bear attack event |
| `/listbears` | View all scheduled bears |
| `/cancelbear` | Cancel an upcoming bear |
| `/setbearpings` | Configure bear notification settings |

### 🏆 **Event Commands**
| Command | Description |
|---------|-------------|
| `/addevent` | Schedule a new game event |
| `/listevents` | View all upcoming events |
| `/cancelevent` | Cancel an event |
| `/seteventpings` | Configure event notification settings |

### ⚔️ **Arena Commands**
| Command | Description |
|---------|-------------|
| `/setarenaping` | Configure arena notification settings |

### 🛠️ **Utility Commands**
| Command | Description |
|---------|-------------|
| `/help` | Comprehensive bot guide |
| `/purge` | Bulk message deletion |
| `/embed` | Create custom embeds (admin) |
| `/synccommands` | Force command re-sync |
| `/viewsettings` | View all notification settings |

---

## ⚙️ Configuration

### Notification Settings
Each system supports customizable notification timing:

- **Bear Notifications**: Incoming (60min), Pre-attack (1-60min), Attack
- **Arena Notifications**: Pre-arena (1-60min)
- **Event Notifications**: Reminder (1-60min), Final call (1-60min)

### Installation Modes
- **Auto Mode**: Creates all channels automatically with locked permissions
- **Manual Mode**: Select existing channels for each system

---

## 🎯 Key Features

- **🔄 Auto-sync** - Commands sync to all servers automatically
- **🛡️ Permission-aware** - Graceful handling of missing permissions
- **📊 Live logging** - Comprehensive activity tracking
- **⚡ Real-time updates** - Dynamic embeds and settings
- **🎨 Rich embeds** - Beautiful, informative notifications
- **🔧 Modular design** - Easy to extend and customize

---

## 🆘 Support

**Need help? Join our support server!**
https://discord.gg/MPFdHdQXzf

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.


