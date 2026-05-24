"""Anti-spam cog for ExeGuard.

Detects rapid messaging, duplicate messages, emoji spam, mention spam,
caps spam, and link spam.  Automatically deletes, warns, times out, kicks,
or bans offending users based on configurable thresholds.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    COLOR_PRIMARY,
    SPAM_CAPS_MIN_LENGTH,
    SPAM_CAPS_RATIO,
    SPAM_DUPLICATE_INTERVAL,
    SPAM_DUPLICATE_THRESHOLD,
    SPAM_EMOJI_LIMIT,
    SPAM_MENTION_LIMIT,
    SPAM_MESSAGE_INTERVAL,
    SPAM_MESSAGE_THRESHOLD,
    SPAM_TIMEOUT_DURATION,
)
from utils.embed_builder import EmbedBuilder

EMOJI_RE = re.compile(
    r"<a?:\w+:\d+>|[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff"
    r"\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\U00002702-\U000027b0"
    r"\U000024c2-\U0001f251]+"
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


@dataclass
class UserSpamData:
    """Tracks per-user spam metrics."""

    messages: list[float] = field(default_factory=list)
    contents: list[tuple[str, float]] = field(default_factory=list)
    infractions: int = 0


class AntiSpam(commands.Cog):
    """Real-time anti-spam protection."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._data: dict[int, dict[int, UserSpamData]] = defaultdict(
            lambda: defaultdict(UserSpamData)
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _guild_data(self, guild_id: int, user_id: int) -> UserSpamData:
        return self._data[guild_id][user_id]

    async def _is_exempt(self, message: discord.Message) -> bool:
        if message.author.bot or not message.guild:
            return True
        assert isinstance(message.author, discord.Member)
        if message.author.guild_permissions.manage_messages:
            return True
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)
        if not settings.get("antispam", True):
            return True
        if await db.is_channel_whitelisted(message.guild.id, message.channel.id):
            return True
        for role in message.author.roles:
            if await db.is_role_whitelisted(message.guild.id, role.id):
                return True
        return False

    async def _punish(
        self,
        message: discord.Message,
        reason: str,
    ) -> None:
        assert message.guild is not None
        assert isinstance(message.author, discord.Member)
        data = self._guild_data(message.guild.id, message.author.id)
        data.infractions += 1

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)
        timeout_secs = settings.get("timeout_duration", SPAM_TIMEOUT_DURATION)

        if data.infractions >= 5:
            try:
                await message.author.ban(reason=f"ExeGuard anti-spam: {reason}")
            except discord.HTTPException:
                pass
            action = "banned"
        elif data.infractions >= 3:
            try:
                await message.author.timeout(
                    timedelta(seconds=timeout_secs),
                    reason=f"ExeGuard anti-spam: {reason}",
                )
            except discord.HTTPException:
                pass
            action = f"timed out for {timeout_secs}s"
        else:
            action = "warned"

        embed = EmbedBuilder.security(
            "Spam Detected",
            f"**User:** {message.author.mention}\n"
            f"**Action:** {action}\n"
            f"**Reason:** {reason}",
        )
        try:
            await message.channel.send(embed=embed, delete_after=10)
        except discord.HTTPException:
            pass

        log_channel_id = settings.get("log_channel")
        if log_channel_id:
            channel = message.guild.get_channel(log_channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    # ── Checks ──────────────────────────────────────────────────────

    def _check_rapid(self, data: UserSpamData, now: float) -> bool:
        data.messages = [
            t for t in data.messages if now - t < SPAM_MESSAGE_INTERVAL
        ]
        data.messages.append(now)
        return len(data.messages) > SPAM_MESSAGE_THRESHOLD

    def _check_duplicate(self, data: UserSpamData, content: str, now: float) -> bool:
        data.contents = [
            (c, t) for c, t in data.contents if now - t < SPAM_DUPLICATE_INTERVAL
        ]
        data.contents.append((content, now))
        dups = sum(1 for c, _ in data.contents if c == content)
        return dups >= SPAM_DUPLICATE_THRESHOLD

    @staticmethod
    def _check_emoji(content: str) -> bool:
        return len(EMOJI_RE.findall(content)) > SPAM_EMOJI_LIMIT

    @staticmethod
    def _check_mentions(message: discord.Message) -> bool:
        return len(message.mentions) + len(message.role_mentions) > SPAM_MENTION_LIMIT

    @staticmethod
    def _check_caps(content: str) -> bool:
        if len(content) < SPAM_CAPS_MIN_LENGTH:
            return False
        alpha = [c for c in content if c.isalpha()]
        if not alpha:
            return False
        return sum(1 for c in alpha if c.isupper()) / len(alpha) > SPAM_CAPS_RATIO

    @staticmethod
    def _check_links(content: str) -> bool:
        return len(URL_RE.findall(content)) > 3

    # ── Listener ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if await self._is_exempt(message):
            return
        assert message.guild is not None
        data = self._guild_data(message.guild.id, message.author.id)
        now = time.time()
        content = message.content

        if self._check_rapid(data, now):
            await self._punish(message, "Rapid messaging")
        elif self._check_duplicate(data, content, now):
            await self._punish(message, "Duplicate messages")
        elif self._check_emoji(content):
            await self._punish(message, "Emoji spam")
        elif self._check_mentions(message):
            await self._punish(message, "Mention spam")
        elif self._check_caps(content):
            await self._punish(message, "Excessive caps")
        elif self._check_links(content):
            await self._punish(message, "Link spam")

    # ── Slash command ───────────────────────────────────────────────

    @app_commands.command(
        name="antispam", description="Configure the anti-spam system"
    )
    @app_commands.describe(
        enabled="Enable or disable anti-spam",
        threshold="Number of messages before triggering",
        timeout="Timeout duration in seconds",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antispam_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool | None = None,
        threshold: int | None = None,
        timeout: int | None = None,
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        if enabled is not None:
            await db.update_guild_setting(
                interaction.guild.id, "antispam", int(enabled)
            )
        if threshold is not None:
            await db.update_guild_setting(
                interaction.guild.id, "spam_threshold", threshold
            )
        if timeout is not None:
            await db.update_guild_setting(
                interaction.guild.id, "timeout_duration", timeout
            )
        settings = await db.get_guild_settings(interaction.guild.id)
        embed = EmbedBuilder.info(
            "Anti-Spam Settings",
            f"**Enabled:** {'Yes' if settings['antispam'] else 'No'}\n"
            f"**Threshold:** {settings['spam_threshold']} messages\n"
            f"**Timeout:** {settings['timeout_duration']}s",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiSpam(bot))
