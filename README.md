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

ExeGuard is a next-gen **autonomous security bot** for Discord. It combines real-time threat detection, automated moderation, and full raid/nuke countermeasures — all controllable through slash commands. Whether you're running a small community or a large gaming server, ExeGuard **keeps the peace**.

```
🛡️  Anti-Nuke     →  Blocks mass deletions, bans, role nukes
🚫  Anti-Spam     →  Kills floods, dupes, mentions, caps, links
🔒  Anti-Raid     →  Detects storms, locks down, auto-recovers
👮  Moderation    →  Ban, kick, timeout, warn, purge, tempban, voice mod
🧩  Verification  →  Button or captcha gate for new members
🏗️  Infrastructure →  Tickets, giveaways, dynamic VC, reaction roles
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
| **NSFW Filter** | Blocks NSFW content in messages |
| **Ghost Ping Detection** | Logs deleted ping messages |
| **Scam / Phishing Detection** | Regex-based malicious content blocking |

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
- **Safe onboarding** — protects new servers from fresh accounts
- **Auto-recovery** — lifts lockdown after 5 minutes

### ⚔️ Anti-Nuke
Watches audit logs for destructive action bursts (3+ within 10s):
- Channel / role mass deletion
- Mass bans & kicks
- Permission escalation on roles
- Webhook / integration creation
- External app monitoring

**Response:** Auto-bans the offender, strips roles, DMs the server owner.

---

## ⚙️ Commands

### Configuration
| Command | Permission |
|---------|------------|
| `/setup` — Quick wizard (logs, verified role, toggles) | Administrator |
| `/settings` — View current configuration | Manage Server |
| `/logs` — Configure log channels | Manage Server |
| `/bypassrole` — Set role that bypasses all protections | Administrator |

### Protection
| Command | Permission |
|---------|------------|
| `/antinuke <enabled>` | Administrator |
| `/antiraid <level>` — low / medium / high | Manage Server |
| `/antispam [...]` — thresholds, limits, invites, links | Manage Server |
| `/blockuserapps <enabled>` | Manage Server |
| `/botprotection <enabled>` | Manage Server |
| `/security dangerous_invites` — block dangerous invites | Manage Server |
| `/security safe_onboarding` — strict onboarding | Administrator |
| `/security scan` — dangerous permission scanner | Administrator |
| `/secure_everyone` — strip dangerous perms from @everyone | Administrator |

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
| `/voicemute / voiceunmute / voicedisconnect / voicemove / voicelock` | Moderate Members |

### Security
| Command | Permission |
|---------|------------|
| `/health` — security score & threat level | Manage Server |
| `/trust <user>` / `/untrust <user>` | Administrator |
| `/trustbots <enabled>` | Administrator |

### Verification & Utility
| Command | Permission |
|---------|------------|
| `/verify <method> <role>` — button or captcha | Manage Server |
| `/afk [reason]` — set AFK | Everyone |
| `/autorole <add/remove> <role>` | Manage Roles |
| `/welcome <channel> <message> <enabled>` | Manage Guild |
| `/leave <channel> <message> <enabled>` | Manage Guild |

### Infrastructure
| Command | Permission |
|---------|------------|
| `/new` — create a ticket | Everyone |
| `/close` — close current ticket | Everyone |
| `/giveaway <duration> <prize> [winners]` | Manage Guild |
| `/giveaway_end <message_id>` | Manage Guild |
| `/giveaway_reroll <message_id>` | Manage Guild |
| `/voicemaster <channel> <category>` | Administrator |
| `/reactionrole <message_id> <emoji> <role>` | Manage Roles |
| `/buttonrole <role> <label> [emoji]` | Manage Roles |
| `/dropdownrole <roles> [placeholder]` | Manage Roles |

### Ownership
| Command | Permission |
|---------|------------|
| `/owner add <user>` | Primary Owner |
| `/owner remove <user>` | Primary Owner |
| `/owner list` | Everyone |
| `/owner transfer <user>` | Primary Owner |
| `/rolefix scan` — check missing roles | Manage Roles |
| `/rolefix template <name>` — apply role template | Manage Roles |

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
│   ├── moderation.py    # Ban/kick/timeout/warn/purge/panic/voice
│   ├── verification.py  # Button & captcha verification
│   ├── logging_cog.py   # Message/member/role/channel event logs
│   ├── analytics.py     # Server stats, growth, voice activity
│   ├── infrastructure.py# Tickets, giveaways, VC, reaction/button/dropdown roles
│   ├── server_mgmt.py   # Ownership, rolefix, security, bypass, community
│   └── utility.py       # AFK, autorole, welcome messages, onboarding
├── utils/               # Embed builder, permission helpers
├── prodia/              # Prodia API constants
└── data/                # Runtime assets
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


</div>

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<p align="center">
  <sub>Built with ❤️ for Discord communities that demand security.</sub>
</p>
