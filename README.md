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
- **Blacklisted Words** — custom word/phrase filtering
- **External App Spam** — blocks unauthorized User-Installed Apps from posting (e.g., promo bots)

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

### Fun & Games
Interactive entertainment for your community:
- **Classic Games** — RPS, Tic-Tac-Toe, Wordle, 2048, Connect Four, Chess
- **Casino Games** — Blackjack, Slots (with animated GIF generation)
- **Social Commands** — Hug, slap, pat, meme, howgay, tharki
- **AI Tools** — AI Image generation (Imagine)

### Utility & Automation
- **AFK System** — Notifies mentions and welcomes you back with a summary
- **AutoRole** — Automatically assign roles to new members
- **Welcome System** — Customizable welcome messages in dedicated channels
- **Giveaways** — Host and manage giveaways (coming soon)

### AutoMod
- **Webhook protection** — deletes unauthorized webhooks
- **@everyone/@here protection** — detects abuse and auto-timeouts the user
- **Emoji Spam** — prevents excessive emoji usage

### Member Verification
Gate new members before they access the server:
- **Button verification** — simple one-click verify
- **Captcha verification** — users must solve a captcha code (3 attempt limit)

### Comprehensive Logging
Logs all server events to dedicated channels:
- Message edits and deletions
- Member joins and leaves
- Role creates, deletes, and updates
- Channel creates and deletes
- Webhook changes

### Moderation & Security Dashboard
- **Ban/Kick/Timeout/Purge/Warn** — standard moderation tools
- **Tempbans** — temporary bans with auto-unban
- **Security Audit** — real-time server security scoring (0-100)
- **Panic Mode** — emergency lockdown with one command
- **Bot Protection** — prevents staff from accidentally banning invited bots
- **Command Cooldowns** — rate limits on all slash commands to prevent abuse

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
BOT_PREFIX=!
OWNER_IDS=your_discord_user_id
DATABASE_PATH=data/exeguard.db
PORT=8080
```

4. Run the bot:
```bash
python main.py
```

### Deploying to Render / Replit
ExeGuard includes a built-in web server to keep the bot alive on hosting platforms that require open ports.

1. **Render**: Set service type to **Web Service**, build command `pip install -r requirements.txt`, start command `python main.py`.
2. **Keep it awake**: Use a free uptime monitor (e.g., [UptimeRobot](https://uptimerobot.com)) to ping your Render URL every 5 minutes to prevent the free tier from sleeping.

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
| `/antispam [...]` | Configure anti-spam settings (thresholds, limits, links, invites) | Manage Server |
| `/blockuserapps <enabled>` | Toggle blocking unauthorized external app messages (e.g., spam bots) | Manage Server |
| `/botprotection <enabled>` | Prevent accidental bans/kicks of invited bots | Manage Server |

### Moderation

| Command | Description | Permission |
|---------|-------------|------------|
| `/ban <user> [reason]` | Ban a user from the server | Ban Members |
| `/tempban <user> <duration> [reason]` | Temporarily ban a user with auto-expiry | Ban Members |
| `/kick <member> [reason]` | Kick a member from the server | Kick Members |
| `/timeout <member> [duration] [reason]` | Timeout a member (e.g., `10m`, `1h`) | Moderate Members |
| `/warn <member> [reason]` | Warn a member (also DMs them) | Manage Messages |
| `/purge <amount>` | Bulk delete messages (max 100) | Manage Messages |
| `/lock [channel]` | Lock a channel (prevent members from sending messages) | Manage Channels |
| `/unlock [channel]` | Unlock a channel | Manage Channels |
| `/panic <enabled>` | Emergency panic mode — locks all channels and maxes protections | Administrator |

### Security Dashboard

| Command | Description | Permission |
|---------|-------------|------------|
| `/security-audit` | Scan server for vulnerabilities and get a security score | Manage Server |
| `/trust <user>` | Add a trusted admin (exempt from anti-nuke detection) | Administrator |
| `/untrust <user>` | Remove a user from the trusted admin list | Administrator |
| `/trustbots <enabled>` | Toggle whether all bots are exempt from anti-nuke | Administrator |

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
| External App Blocking | Enabled by default |
| Bot Protection | Enabled by default |

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
- **Use External Apps** (for verification and logging)

Also enable **all Privileged Gateway Intents** (Presence, Server Members, Message Content) in the Discord Developer Portal.

---

## Tech Stack
- **Python** with **discord.py**
- **aiosqlite** for async SQLite database
- **python-dotenv** for environment configuration
- **aiohttp** for hosting platform web server (Render/Replit uptime)

---

## License
See the [LICENSE](LICENSE) file for details.
