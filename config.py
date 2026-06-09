"""ExeGuard configuration module."""

import logging
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

log = logging.getLogger("exeguard.config")

load_dotenv()


@dataclass
class BotConfig:
    """Core bot configuration loaded from environment variables."""

    token: str = field(default_factory=lambda: os.getenv("DISCORD_TOKEN", ""))
    prefix: str = field(default_factory=lambda: os.getenv("BOT_PREFIX", "!"))
    owner_ids: list[int] = field(default_factory=list)
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "data/exeguard.db")
    )
    def __post_init__(self) -> None:
        raw = os.getenv("OWNER_IDS", "")
        if raw:
            for x in raw.split(","):
                x = x.strip()
                if x:
                    try:
                        self.owner_ids.append(int(x))
                    except ValueError:
                        log.warning("Invalid owner ID in OWNER_IDS: %s", x)


# ── Anti-Spam defaults ──────────────────────────────────────────────
SPAM_MESSAGE_THRESHOLD = 5
SPAM_MESSAGE_INTERVAL = 5.0  # seconds
SPAM_DUPLICATE_THRESHOLD = 3
SPAM_DUPLICATE_INTERVAL = 10.0
SPAM_EMOJI_LIMIT = 10
SPAM_MENTION_LIMIT = 5
SPAM_CAPS_RATIO = 0.7
SPAM_CAPS_MIN_LENGTH = 10
SPAM_TIMEOUT_DURATION = 300  # seconds

# ── Anti-Raid defaults ──────────────────────────────────────────────
RAID_JOIN_THRESHOLD = 10
RAID_JOIN_INTERVAL = 10.0  # seconds
RAID_MIN_ACCOUNT_AGE = 7  # days
RAID_SLOWMODE_DELAY = 10  # seconds
RAID_LOCKDOWN_DURATION = 300  # seconds

# ── Anti-Nuke defaults ──────────────────────────────────────────────
NUKE_ACTION_THRESHOLD = 3
NUKE_ACTION_INTERVAL = 10.0  # seconds

# ── Verification defaults ───────────────────────────────────────────
VERIFICATION_TIMEOUT = 300  # seconds

# ── Colors ──────────────────────────────────────────────────────────
COLOR_PRIMARY = 0x0F1115  # Dark Charcoal
COLOR_SECONDARY = 0x181B22  # Gray Panels
COLOR_TEXT = 0xFFFFFF  # White Typography
COLOR_MUTE = 0xA9ADB7  # Muted Gray
COLOR_SUCCESS = 0x00D26A  # Security Green
COLOR_DANGER = 0xFF3B3B  # Alert Red
COLOR_INFO = 0xA9ADB7  # Using Mute for info

# ── Embed footer ────────────────────────────────────────────────────
EMBED_FOOTER = "EXEGUARD v1.0 | Security • Moderation • Analytics • Infrastructure"
