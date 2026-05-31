<p align="center">
  <img src="https://img.shields.io/badge/ExeGuard-v1.0-6C5CE7?style=for-the-badge&logo=discord&logoColor=white" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-00D4FF?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-2ECC71?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/status-ACTIVE-FF4D4D?style=for-the-badge" alt="Status">
</p>

<div align="center">

```
███████╗██╗  ██╗███████╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗
██╔════╝╚██╗██╔╝██╔════╝██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗
█████╗   ╚███╔╝ █████╗  ██║  ███╗██║   ██║███████║██████╔╝██║  ██║
██╔══╝   ██╔██╗ ██╔══╝  ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║
███████╗██╔╝ ██╗███████╗╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝

```

**Futuristic Discord Server Protection — Watchdog. Shield. Guardian.**

</div>

---

## ⚡ Overview

ExeGuard is a next-gen **autonomous security bot** for Discord. It combines real-time threat detection, automated moderation, raid/nuke countermeasures, and a full-featured web dashboard — all controllable through slash commands. Whether you're running a small community or a large gaming server, ExeGuard **keeps the peace**.

```
🛡️  Anti-Nuke     →  Blocks mass deletions, bans, role nukes
🚫  Anti-Spam     →  Kills floods, dupes, mentions, caps, links
🔒  Anti-Raid     →  Detects storms, locks down, auto-recovers
👮  Moderation    →  Ban, kick, timeout, warn, purge, tempban
🧩  Verification  →  Button or captcha gate for new members
🎮  Games         →  Blackjack, slots, chess, wordle, 2048 & more
📊  Dashboard     →  Web UI with live stats, settings, mod center
```

---

## 🛡️ Protection Suite

### 🤖 AutoMod & Advanced
| Feature | Description |
|---------|-------------|
| **External App Blocking** | Detects & blocks unauthorized User-Installed Apps — 1st offense: 15m timeout, repeat: ban |
| **Webhook Protection** | Auto-deletes webhooks created by untrusted users |
| **@everyone/@here Guard** | Detects abuse & instantly times out the offender |
| **Emoji Spam Filter** | Prevents mass emoji flooding |

### 🚫 Anti-Spam
```
  5 msgs in 5s     →  Rapid messaging
  3 duplicate msgs  →  Content spam
  10+ emojis        →  Emoji abuse
  5+ mentions       →  Mass ping
  70% caps          →  SHOUTING
  3+ links          →  Link flooding
```

**Escalation:** `Warning → Timeout → Ban`

### 🔒 Anti-Raid
- **Mass join detection** — auto-lockdown when threshold is breached
- **Young account filter** — kicks accounts < 7 days old
- **Suspicious name detection** — pattern-matches raid/nuke/hack keywords
- **Auto-recovery** — lifts lockdown after 5 minutes

### ⚔️ Anti-Nuke
Watches audit logs for destructive action bursts (3+ within 10s):
- Channel / role mass deletion
- Mass bans & kicks
- Permission escalation on roles
- Webhook / integration creation

**Response:** Auto-bans the offender, strips roles, DMs the server owner.

---

## 🎮 Games & Fun

| Category | Games |
|----------|-------|
| **Classic** | Rock Paper Scissors, Tic-Tac-Toe, Wordle, 2048, Connect Four, Chess, Battleship |
| **Casino** | Blackjack (with card images), Slots (animated GIF) |
| **Social** | `hug`, `slap`, `pat`, `meme`, `howgay`, `tharki` |

---

## ⚙️ Commands

### Configuration
| Command | Permission |
|---------|------------|
| `/setup` — Quick wizard (logs, verified role, toggles) | Administrator |
| `/settings` — View current configuration | Manage Server |
| `/logs` — Configure log channels | Manage Server |

### Protection
| Command | Permission |
|---------|------------|
| `/antinuke <enabled>` | Administrator |
| `/antiraid <level>` — low / medium / high | Manage Server |
| `/antispam [...]` — thresholds, limits, invites, links | Manage Server |
| `/blockuserapps <enabled>` | Manage Server |
| `/botprotection <enabled>` | Manage Server |

### Moderation
| Command | Permission |
|---------|------------|
| `/ban <user> [reason]` | Ban Members |
| `/tempban <user> <duration> [reason]` | Ban Members |
| `/kick <member> [reason]` | Kick Members |
| `/timeout <member> [duration] [reason]` | Moderate Members |
| `/warn <member> [reason]` | Manage Messages |
| `/purge <amount>` — max 100 | Manage Messages |
| `/lock [channel]` / `/unlock [channel]` | Manage Channels |
| `/panic <enabled>` — emergency lockdown | Administrator |

### Security
| Command | Permission |
|---------|------------|
| `/security-audit` — vulnerability scan & score | Manage Server |
| `/trust <user>` / `/untrust <user>` | Administrator |
| `/trustbots <enabled>` | Administrator |

### Verification & Utility
| Command | Permission |
|---------|------------|
| `/verify <method> <role>` — button or captcha | Manage Server |
| `/afk [reason]` — set AFK | Everyone |
| `/autorole <add/remove> <role>` | Manage Roles |
| `/welcome <channel> <message> <enabled>` | Manage Guild |

---

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/raisulislamratul17/ExeGuard.git
cd ExeGuard

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Discord token, owner ID, etc.

# Launch
python main.py
```

### Environment Variables
```env
DISCORD_TOKEN=your_bot_token_here
BOT_PREFIX=!
OWNER_IDS=your_discord_user_id
DATABASE_PATH=data/exeguard.db
DASHBOARD_API_KEY=your_secret_api_key
PORT=8080
```

### Discord Setup
Invite the bot with required permissions, then run:
```
/setup log_channel:#security-logs mod_log_channel:#mod-logs join_log_channel:#join-logs verified_role:@Verified
```

---

## 🏗️ Architecture

```
ExeGuard
├── main.py              # Entry point, bot init, error handling
├── config.py            # Environment config & defaults
├── database/
│   ├── manager.py       # Async SQLite (guild settings, warnings, AFK, etc.)
├── cogs/
│   ├── antispam.py      # Message rate limiting & content filtering
│   ├── antiraid.py      # Mass join detection & lockdown
│   ├── antinuke.py      # Audit log monitoring & auto-ban
│   ├── automod.py       # Webhook & @everyone protection
│   ├── moderation.py    # Ban/kick/timeout/warn/purge/panic
│   ├── verification.py  # Button & captcha verification
│   ├── logging_cog.py   # Message/member/role/channel event logs
│   ├── dashboard_api.py # REST API for web dashboard
│   ├── games.py         # Game commands & blackjack engine
│   ├── fun.py           # Social & entertainment commands
│   └── utility.py       # AFK, autorole, welcome messages
├── games/               # Vendored discord_games library
├── utils/               # Embed builder, permission helpers
└── dashboard/           # Next.js web dashboard (standalone)
```

---

## 🧰 Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| **Runtime** | Python 3.10+ |
| **Framework** | [discord.py](https://github.com/Rapptz/discord.py) 2.3+ |
| **Database** | aiosqlite (async SQLite) |
| **API Server** | aiohttp |
| **Dashboard** | Next.js + TypeScript + Tailwind |
| **Auth** | Discord OAuth2 (next-auth) |
| **Assets** | Pillow (card images, slot GIFs, 2048 render) |

</div>

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<p align="center">
  <sub>Built with ❤️ for Discord communities that demand security.</sub>
</p>
