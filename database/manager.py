"""SQLite database manager for ExeGuard."""

from __future__ import annotations

import aiosqlite
import os
from typing import Any


class DatabaseManager:
    """Async SQLite wrapper for guild settings, warnings, and audit data."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # ── Schema ──────────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id     INTEGER PRIMARY KEY,
                antispam     INTEGER DEFAULT 1,
                antiraid     INTEGER DEFAULT 1,
                antinuke     INTEGER DEFAULT 1,
                verification INTEGER DEFAULT 0,
                log_channel  INTEGER,
                mod_log_channel INTEGER,
                join_log_channel INTEGER,
                verified_role INTEGER,
                raid_level   TEXT DEFAULT 'medium',
                spam_threshold INTEGER DEFAULT 5,
                spam_interval  REAL DEFAULT 5.0,
                timeout_duration INTEGER DEFAULT 300
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                mod_id    INTEGER NOT NULL,
                reason    TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mod_actions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                mod_id    INTEGER NOT NULL,
                action    TEXT NOT NULL,
                reason    TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS whitelisted_roles (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );

            CREATE TABLE IF NOT EXISTS whitelisted_channels (
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS trusted_admins (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """
        )
        # Dynamic Migration to add missing columns to guild_settings
        async with self.conn.execute("PRAGMA table_info(guild_settings)") as cursor:
            columns = [row["name"] for row in await cursor.fetchall()]

        new_cols = {
            "trust_all_bots": "INTEGER DEFAULT 1",
            "spam_emoji_limit": "INTEGER DEFAULT 10",
            "spam_mention_limit": "INTEGER DEFAULT 5",
            "spam_caps_ratio": "REAL DEFAULT 0.7",
            "spam_duplicate_threshold": "INTEGER DEFAULT 3",
            "spam_duplicate_interval": "REAL DEFAULT 10.0",
            "block_invites": "INTEGER DEFAULT 0",
            "block_links": "INTEGER DEFAULT 0",
            "bad_words": "TEXT DEFAULT ''",
            "block_user_apps": "INTEGER DEFAULT 1",
            "bot_protection": "INTEGER DEFAULT 1",
        }

        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                await self.conn.execute(f"ALTER TABLE guild_settings ADD COLUMN {col_name} {col_type}")

        # Create tempbans table
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tempbans (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                unban_timestamp TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """
        )

        # Create AFK table
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS afk (
                user_id    INTEGER PRIMARY KEY,
                reason     TEXT NOT NULL,
                timestamp  REAL NOT NULL,
                mentions   INTEGER DEFAULT 0
            );
            """
        )

        # Create auto_roles table
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_roles (
                guild_id INTEGER NOT NULL,
                role_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            """
        )

        # Create welcome_settings table
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS welcome_settings (
                guild_id   INTEGER PRIMARY KEY,
                channel_id INTEGER,
                message    TEXT,
                enabled    INTEGER DEFAULT 0
            );
            """
        )

        await self.conn.commit()

    # ── Guild settings helpers ──────────────────────────────────────

    async def get_guild_settings(self, guild_id: int) -> dict[str, Any]:
        async with self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                out = dict(row)
                for k, v in out.items():
                    if v is None:
                        out[k] = self._column_defaults.get(k)
                return out
        await self.conn.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        await self.conn.commit()
        async with self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {"guild_id": guild_id}

    _column_defaults = {
        "antispam": 1, "antiraid": 1, "antinuke": 1, "verification": 0,
        "log_channel": None, "mod_log_channel": None, "join_log_channel": None,
        "verified_role": None, "raid_level": "medium",
        "spam_threshold": 5, "spam_interval": 5.0, "timeout_duration": 300,
        "trust_all_bots": 1, "spam_emoji_limit": 10, "spam_mention_limit": 5,
        "spam_caps_ratio": 0.7, "spam_duplicate_threshold": 3,
        "spam_duplicate_interval": 10.0, "block_invites": 0, "block_links": 0,
        "bad_words": "", "block_user_apps": 1, "bot_protection": 1,
    }

    ALLOWED_COLUMNS = frozenset({
        "antispam", "antiraid", "antinuke", "verification",
        "log_channel", "mod_log_channel", "join_log_channel",
        "verified_role", "raid_level", "spam_threshold",
        "spam_interval", "timeout_duration", "trust_all_bots",
        "spam_emoji_limit", "spam_mention_limit", "spam_caps_ratio",
        "spam_duplicate_threshold", "spam_duplicate_interval",
        "block_invites", "block_links", "bad_words",
        "block_user_apps", "bot_protection",
    })

    async def update_guild_setting(
        self, guild_id: int, key: str, value: Any
    ) -> None:
        if key not in self.ALLOWED_COLUMNS:
            raise ValueError(f"Invalid column name: {key}")
        await self.get_guild_settings(guild_id)
        await self.conn.execute(
            f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?",
            (value, guild_id),
        )
        await self.conn.commit()

    # ── Warnings ────────────────────────────────────────────────────

    async def add_warning(
        self, guild_id: int, user_id: int, mod_id: int, reason: str
    ) -> int:
        async with self.conn.execute(
            "INSERT INTO warnings (guild_id, user_id, mod_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, mod_id, reason),
        ) as cursor:
            warn_id = cursor.lastrowid
        await self.conn.commit()
        return warn_id or 0

    async def get_warnings(
        self, guild_id: int, user_id: int
    ) -> list[dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (guild_id, user_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Mod actions ─────────────────────────────────────────────────

    async def log_mod_action(
        self,
        guild_id: int,
        user_id: int,
        mod_id: int,
        action: str,
        reason: str | None = None,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO mod_actions (guild_id, user_id, mod_id, action, reason) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, action, reason),
        )
        await self.conn.commit()

    # ── Whitelist helpers ───────────────────────────────────────────

    async def is_role_whitelisted(self, guild_id: int, role_id: int) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def add_whitelisted_role(self, guild_id: int, role_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO whitelisted_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await self.conn.commit()

    async def remove_whitelisted_role(self, guild_id: int, role_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await self.conn.commit()

    async def is_channel_whitelisted(self, guild_id: int, channel_id: int) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM whitelisted_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    # ── Trusted admins ──────────────────────────────────────────────

    async def is_trusted_admin(self, guild_id: int, user_id: int) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM trusted_admins WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def add_trusted_admin(self, guild_id: int, user_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO trusted_admins (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await self.conn.commit()

    async def remove_trusted_admin(self, guild_id: int, user_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM trusted_admins WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await self.conn.commit()

    # ── AFK System ───────────────────────────────────────────────────

    async def get_afk(self, user_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM afk WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_afk(self, user_id: int, reason: str, timestamp: float) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO afk (user_id, reason, timestamp, mentions) VALUES (?, ?, ?, 0)",
            (user_id, reason, timestamp),
        )
        await self.conn.commit()

    async def remove_afk(self, user_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM afk WHERE user_id = ?", (user_id,)
        )
        await self.conn.commit()

    async def increment_afk_mentions(self, user_id: int) -> None:
        await self.conn.execute(
            "UPDATE afk SET mentions = mentions + 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.conn.commit()

    # ── AutoRole System ──────────────────────────────────────────────

    async def get_auto_roles(self, guild_id: int) -> list[int]:
        async with self.conn.execute(
            "SELECT role_id FROM auto_roles WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r["role_id"] for r in rows]

    async def add_auto_role(self, guild_id: int, role_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO auto_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await self.conn.commit()

    async def remove_auto_role(self, guild_id: int, role_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM auto_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await self.conn.commit()

    # ── Welcome System ───────────────────────────────────────────────

    async def get_welcome_settings(self, guild_id: int) -> dict[str, Any] | None:
        async with self.conn.execute(
            "SELECT * FROM welcome_settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_welcome_settings(
        self, guild_id: int, channel_id: int, message: str, enabled: int
    ) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id, message, enabled) VALUES (?, ?, ?, ?)",
            (guild_id, channel_id, message, enabled),
        )
        await self.conn.commit()
