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
            "bad_words": "TEXT DEFAULT ''"
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
        await self.conn.commit()

    # ── Guild settings helpers ──────────────────────────────────────

    async def get_guild_settings(self, guild_id: int) -> dict[str, Any]:
        async with self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        defaults = {"guild_id": guild_id}
        await self.conn.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        await self.conn.commit()
        return await self.get_guild_settings(guild_id)

    async def update_guild_setting(
        self, guild_id: int, key: str, value: Any
    ) -> None:
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
