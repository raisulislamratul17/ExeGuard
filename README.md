# ExeGuard

**Futuristic Discord Server Protection Bot**

ExeGuard is a powerful, all-in-one Discord security bot that protects your server from spam, raids, nukes, and abuse. It features automatic threat detection, moderation tools, member verification, and comprehensive logging — all controlled through simple slash commands.

---

## Features

### Anti-Spam Protection
Automatically detects and punishes:
- **Rapid messaging** — flooding the chat with messages
- **Duplicate messages** — repeating the same message
- **Emoji spam** — excessive emoji usage
- **Mention spam** — mass-mentioning users or roles
- **Caps spam** — excessive use of capital letters
- **Link spam** — posting too many links

**Punishment escalation:** Warning → Timeout → Ban (after repeated offenses)

### Anti-Raid Protection
Detects and responds to raid attempts:
- **Mass join detection** — triggers lockdown when too many users join rapidly
- **Young account filtering** — kicks accounts that are too new
- **Suspicious username detection** — auto-kicks users with names containing raid/nuke/hack keywords
- **Auto-lockdown** — locks all channels and enables slowmode during a raid
- **Auto-recovery** — automatically lifts lockdown after a set duration

### Anti-Nuke Protection
Monitors audit logs for destructive actions:
- **Channel deletions** — detects mass channel deletion
- **Role deletions** — detects mass role deletion
- **Mass bans/kicks** — detects when someone bans or kicks many members
- **Permission escalation** — detects unauthorized permission changes on roles
- **Webhook abuse** — detects unauthorized webhook creation

**Response:** Automatically bans the offender, strips their roles, and notifies the server owner.

### AutoMod
- **Webhook protection** — deletes unauthorized webhooks
- **Mention abuse protection** — detects @everyone/@here abuse and mass mentions, auto-timeouts the user

### Member Verification
Gate new members before they access the server:
- **Button verification** — simple one-click verify
- **Captcha verification** — users must solve a captcha code

### Comprehensive Logging
Logs all server events to dedicated channels:
- Message edits and deletions
- Member joins and leaves
- Role creates, deletes, and updates
- Channel creates and deletes
- Webhook changes

---

## Setup

### Prerequisites
- Python 3.10+
- A Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/raisulislamratul17/ExeGuard.git
cd ExeGuard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your `.env` file:
```env
DISCORD_TOKEN=your_bot_token_here
BOT_PREFIX=\
OWNER_IDS=your_discord_user_id
DATABASE_PATH=data/exeguard.db
```

4. Run the bot:
```bash
python main.py
```

### Quick Setup in Discord
Once the bot is running and invited to your server, run:
```
/setup log_channel:#security-logs mod_log_channel:#mod-logs join_log_channel:#join-logs verified_role:@Verified
```

---

## Commands

### Setup & Configuration

| Command | Description | Permission |
|---------|-------------|------------|
| `/setup` | Quick setup wizard — set log channels, mod log, join log, and verified role all at once | Administrator |
| `/settings` | View current ExeGuard settings for the server | Manage Server |
| `/logs` | Configure log channels (security, moderation, joins) | Manage Server |

### Protection Toggles

| Command | Description | Permission |
|---------|-------------|------------|
| `/antinuke <enabled>` | Enable or disable anti-nuke protection | Administrator |
| `/antiraid <level>` | Set anti-raid protection level: `low`, `medium`, or `high` | Manage Server |
| `/antispam [enabled] [threshold] [timeout]` | Configure anti-spam settings | Manage Server |

### Moderation

| Command | Description | Permission |
|---------|-------------|------------|
| `/ban <user> [reason]` | Ban a user from the server | Ban Members |
| `/kick <member> [reason]` | Kick a member from the server | Kick Members |
| `/timeout <member> [duration] [reason]` | Timeout a member (default: 300 seconds) | Moderate Members |
| `/warn <member> [reason]` | Warn a member (also DMs them) | Manage Messages |
| `/purge <amount>` | Bulk delete messages (max 100) | Manage Messages |
| `/lock [channel]` | Lock a channel (prevent members from sending messages) | Manage Channels |
| `/unlock [channel]` | Unlock a channel | Manage Channels |

### Server Control

| Command | Description | Permission |
|---------|-------------|------------|
| `/lockdown` | Manually lock down the entire server | Manage Server |
| `/unlockdown` | Lift the server lockdown | Manage Server |
| `/trust <user>` | Add a trusted admin (exempt from anti-nuke detection) | Administrator |
| `/untrust <user>` | Remove a user from the trusted admin list | Administrator |

### Verification

| Command | Description | Permission |
|---------|-------------|------------|
| `/verify <method> <role>` | Send a verification panel — method: `button` or `captcha` | Manage Server |

---

## Configuration Defaults

| Setting | Default Value |
|---------|---------------|
| Spam message threshold | 5 messages |
| Spam message interval | 5 seconds |
| Duplicate message threshold | 3 messages |
| Duplicate message interval | 10 seconds |
| Emoji limit | 10 emojis |
| Mention limit | 5 mentions |
| Caps ratio trigger | 70% |
| Spam timeout duration | 300 seconds |
| Raid join threshold | 10 joins |
| Raid join interval | 10 seconds |
| Minimum account age | 7 days |
| Raid slowmode delay | 10 seconds |
| Raid lockdown duration | 300 seconds |
| Nuke action threshold | 3 actions |
| Nuke action interval | 10 seconds |
| Verification timeout | 300 seconds |

---

## Required Bot Permissions
Make sure to enable the following when inviting ExeGuard:
- **Manage Channels**
- **Manage Roles**
- **Kick Members**
- **Ban Members**
- **Moderate Members**
- **Manage Messages**
- **View Audit Log**
- **Manage Webhooks**
- **Send Messages**
- **Read Message History**

Also enable **all Privileged Gateway Intents** (Presence, Server Members, Message Content) in the Discord Developer Portal.

---

## Tech Stack
- **Python** with **discord.py**
- **aiosqlite** for async SQLite database
- **python-dotenv** for environment configuration

---

## License
See the [LICENSE](LICENSE) file for details.
