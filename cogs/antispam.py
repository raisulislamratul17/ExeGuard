"""Anti-spam cog for ExeGuard.

Detects rapid messaging, duplicate messages, emoji spam, mention spam,
caps spam, and link spam. Automatically deletes, warns, times out, kicks,
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
from discord.ext import commands, tasks

from config import SPAM_TIMEOUT_DURATION
from utils.embed_builder import EmbedBuilder

EMOJI_RE = re.compile(
    r"<a?:\w+:\d+>|[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff"
    r"\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\U00002702-\U000027b0"
    r"\U000024c2-\U0001f251]+"
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
INVITE_RE = re.compile(
    r"(?:discord\.gg/|discord(?:app)?\.com/invite/)[\w-]+", re.IGNORECASE
)


@dataclass
class UserSpamData:
    """Tracks per-user spam metrics."""

    messages: list[float] = field(default_factory=list)
    contents: list[tuple[str, float]] = field(default_factory=list)
    infractions: int = 0


class AntiSpam(commands.Cog):
    """Real-time anti-spam protection."""

    CLEANUP_INTERVAL = 300  # 5 minutes
    MESSAGE_TTL = 1800  # 30 minutes retention (covers 15m timeout)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._data: dict[int, dict[int, UserSpamData]] = defaultdict(
            lambda: defaultdict(UserSpamData)
        )
        self._cleanup_task.start()

    def cog_unload(self) -> None:
        self._cleanup_task.cancel()

    @tasks.loop(seconds=CLEANUP_INTERVAL)
    async def _cleanup_task(self) -> None:
        now = time.time()
        stale_guilds = []
        for guild_id, users in list(self._data.items()):
            stale_users = []
            for user_id, data in users.items():
                data.messages = [
                    t for t in data.messages if now - t < self.MESSAGE_TTL
                ]
                data.contents = [
                    (c, t) for c, t in data.contents if now - t < self.MESSAGE_TTL
                ]
                if not data.messages and not data.contents:
                    data.infractions = 0
                if (
                    not data.messages
                    and not data.contents
                    and data.infractions == 0
                ):
                    stale_users.append(user_id)
            for uid in stale_users:
                del users[uid]
            if not users:
                stale_guilds.append(guild_id)
        for gid in stale_guilds:
            del self._data[gid]

    @_cleanup_task.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._data.pop(guild.id, None)

    # ── Helpers ─────────────────────────────────────────────────────

    def _guild_data(self, guild_id: int, user_id: int) -> UserSpamData:
        return self._data[guild_id][user_id]

    async def _is_exempt(self, message: discord.Message) -> bool:
        if not message.guild:
            return True

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)

        # If the author is a bot, check if all bots are trusted
        if message.author.bot:
            if settings.get("trust_all_bots", 1):
                return True
            if await db.is_trusted_admin(message.guild.id, message.author.id):
                return True
            # Untrusted bot is subject to anti-spam checks below
        else:
            assert isinstance(message.author, discord.Member)
            if message.author.guild_permissions.manage_messages:
                return True

        if not settings.get("antispam", True):
            return True
        if await db.is_channel_whitelisted(message.guild.id, message.channel.id):
            return True
        if isinstance(message.author, discord.Member):
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

    def _check_rapid(self, data: UserSpamData, now: float, threshold: int, interval: float) -> bool:
        data.messages = [
            t for t in data.messages if now - t < interval
        ]
        data.messages.append(now)
        return len(data.messages) > threshold

    def _check_duplicate(self, data: UserSpamData, content: str, now: float, threshold: int, interval: float) -> bool:
        data.contents = [
            (c, t) for c, t in data.contents if now - t < interval
        ]
        data.contents.append((content, now))
        dups = sum(1 for c, _ in data.contents if c == content)
        return dups >= threshold

    @staticmethod
    def _check_emoji(content: str, limit: int) -> bool:
        return len(EMOJI_RE.findall(content)) > limit

    @staticmethod
    def _check_mentions(message: discord.Message, limit: int) -> bool:
        return len(message.mentions) + len(message.role_mentions) > limit

    @staticmethod
    def _check_caps(content: str, ratio: float) -> bool:
        if len(content) < 10:
            return False
        alpha = [c for c in content if c.isalpha()]
        if not alpha:
            return False
        return sum(1 for c in alpha if c.isupper()) / len(alpha) > ratio

    @staticmethod
    def _check_links(content: str) -> bool:
        return len(URL_RE.findall(content)) > 3

    @staticmethod
    def _check_bad_words(content: str, bad_words_str: str) -> bool:
        if not bad_words_str:
            return False
        words = [w.strip().lower() for w in bad_words_str.split(",") if w.strip()]
        lower_content = content.lower()
        for word in words:
            if word in lower_content:
                return True
        return False

    # ── Listener ────────────────────────────────────────────────────

    def _is_external_app(self, message: discord.Message) -> tuple[bool, discord.User | discord.Member | None]:
        # 1. Ignore normal users and verified webhooks
        if not message.author.bot or message.webhook_id is not None:
            return False, None

        # 2. Check if it's a "User App" (External Integration)
        # Using interaction_metadata (preferred for new Discord API)
        if hasattr(message, "interaction_metadata") and message.interaction_metadata:
            metadata = message.interaction_metadata
            # If it's explicitly a user-installed integration, it is an external app
            if metadata.is_user_integration():
                return True, metadata.user

        # 3. Check if the bot is NOT in the server (External Bot)
        # If get_member returns None, it means the bot is not in the guild member list
        if message.guild.get_member(message.author.id) is None:
            trigger_user = None
            if message.interaction:
                trigger_user = message.interaction.user
            elif hasattr(message, "interaction_metadata") and message.interaction_metadata:
                trigger_user = message.interaction_metadata.user
            
            # This covers "External bots that are not added in server but still can spam"
            return True, trigger_user

        return False, None

    async def _handle_external_app_spam(
        self, message: discord.Message, trigger_user: discord.User | discord.Member | None
    ) -> None:
        assert message.guild is not None
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)
        
        action = "none"
        guild_member = None

        if trigger_user:
            guild_member = message.guild.get_member(trigger_user.id)
            if not guild_member:
                try:
                    guild_member = await message.guild.fetch_member(trigger_user.id)
                except discord.HTTPException:
                    pass

        if guild_member and not guild_member.guild_permissions.manage_messages:
            data = self._guild_data(message.guild.id, guild_member.id)
            data.infractions += 1

            if data.infractions >= 2:
                try:
                    await guild_member.ban(reason="ExeGuard: Repeated external app/bot abuse")
                except discord.HTTPException:
                    pass
                action = "banned"
            else:
                try:
                    # 15 minutes timeout = 900 seconds
                    await guild_member.timeout(
                        timedelta(minutes=15),
                        reason="ExeGuard: Unauthorized external app usage (15m timeout)",
                    )
                except discord.HTTPException:
                    pass
                action = "timed out (15m)"
        elif not guild_member:
            action = "blocked (user not in server)"

        user_mention = guild_member.mention if guild_member else (trigger_user.mention if trigger_user else "Unknown User")
        app_mention = message.author.mention if message.author else "Unknown App"

        embed = EmbedBuilder.security(
            "External App Spam Blocked",
            f"**Triggering User:** {user_mention}\n"
            f"**App:** {app_mention}\n"
            f"**Action:** User **{action}**.\n"
            f"**Reason:** Unauthorized app spam / promo.",
        )
        try:
            await message.channel.send(embed=embed, delete_after=15)
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return

        is_external_app, trigger_user = self._is_external_app(message)
        if is_external_app:
            db = self.bot.db  # type: ignore[attr-defined]
            settings = await db.get_guild_settings(message.guild.id)
            if settings.get("block_user_apps", 1):
                await self._handle_external_app_spam(message, trigger_user)
                return

        if await self._is_exempt(message):
            return
        assert message.guild is not None
        data = self._guild_data(message.guild.id, message.author.id)
        now = time.time()
        content = message.content

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)

        # Retrieve dynamic settings
        spam_threshold = settings.get("spam_threshold", 5)
        spam_interval = settings.get("spam_interval", 5.0)
        dup_threshold = settings.get("spam_duplicate_threshold", 3)
        dup_interval = settings.get("spam_duplicate_interval", 10.0)
        emoji_limit = settings.get("spam_emoji_limit", 10)
        mention_limit = settings.get("spam_mention_limit", 5)
        caps_ratio = settings.get("spam_caps_ratio", 0.7)
        block_invites = settings.get("block_invites", 0)
        block_links = settings.get("block_links", 0)
        bad_words = settings.get("bad_words", "")

        # 1. Bad Words Filter
        if self._check_bad_words(content, bad_words):
            await self._punish(message, "Using blacklisted words")
            return

        # 2. Invite Link Blocker
        if block_invites and INVITE_RE.search(content):
            await self._punish(message, "Sending Discord invite links")
            return

        # 3. External Link Blocker
        if block_links and URL_RE.search(content):
            await self._punish(message, "Sending external links")
            return

        # 4. Standard Anti-Spam checks
        if self._check_rapid(data, now, spam_threshold, spam_interval):
            await self._punish(message, "Rapid messaging")
        elif self._check_duplicate(data, content, now, dup_threshold, dup_interval):
            await self._punish(message, "Duplicate messages")
        elif self._check_emoji(content, emoji_limit):
            await self._punish(message, "Emoji spam")
        elif self._check_mentions(message, mention_limit):
            await self._punish(message, "Mention spam")
        elif self._check_caps(content, caps_ratio):
            await self._punish(message, "Excessive caps")
        elif self._check_links(content):
            await self._punish(message, "Link spam")

    # ── Slash command ───────────────────────────────────────────────

    @app_commands.command(
        name="antispam", description="Configure the anti-spam system settings"
    )
    @app_commands.describe(
        enabled="Enable or disable anti-spam",
        threshold="Number of messages before triggering rapid spam",
        interval="Spam tracking interval in seconds (rapid spam)",
        timeout="Timeout duration in seconds on infraction",
        emoji_limit="Maximum number of emojis allowed per message",
        mention_limit="Maximum number of mentions allowed per message",
        caps_ratio="Caps ratio trigger (0.0 to 1.0)",
        dup_threshold="Number of identical messages to trigger duplicate spam",
        dup_interval="Duplicate messages tracking interval",
        block_invites="Enable/disable blocking discord invite links",
        block_links="Enable/disable blocking all external links",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 10)
    async def antispam_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool | None = None,
        threshold: int | None = None,
        interval: float | None = None,
        timeout: int | None = None,
        emoji_limit: int | None = None,
        mention_limit: int | None = None,
        caps_ratio: float | None = None,
        dup_threshold: int | None = None,
        dup_interval: float | None = None,
        block_invites: bool | None = None,
        block_links: bool | None = None,
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]

        if enabled is not None:
            await db.update_guild_setting(interaction.guild.id, "antispam", int(enabled))
        if threshold is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_threshold", threshold)
        if interval is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_interval", interval)
        if timeout is not None:
            await db.update_guild_setting(interaction.guild.id, "timeout_duration", timeout)
        if emoji_limit is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_emoji_limit", emoji_limit)
        if mention_limit is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_mention_limit", mention_limit)
        if caps_ratio is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_caps_ratio", caps_ratio)
        if dup_threshold is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_duplicate_threshold", dup_threshold)
        if dup_interval is not None:
            await db.update_guild_setting(interaction.guild.id, "spam_duplicate_interval", dup_interval)
        if block_invites is not None:
            await db.update_guild_setting(interaction.guild.id, "block_invites", int(block_invites))
        if block_links is not None:
            await db.update_guild_setting(interaction.guild.id, "block_links", int(block_links))

        s = await db.get_guild_settings(interaction.guild.id)
        lines = [
            f"**Enabled:** {'Yes' if s['antispam'] else 'No'}",
            f"**Rapid Spam Threshold:** {s['spam_threshold']} msgs in {s['spam_interval']}s",
            f"**Duplicate Spam Threshold:** {s['spam_duplicate_threshold']} msgs in {s['spam_duplicate_interval']}s",
            f"**Emoji Limit:** {s['spam_emoji_limit']} emojis",
            f"**Mention Limit:** {s['spam_mention_limit']} mentions",
            f"**Caps Limit:** {int(s['spam_caps_ratio'] * 100)}%",
            f"**Block Invite Links:** {'Yes' if s['block_invites'] else 'No'}",
            f"**Block External Links:** {'Yes' if s['block_links'] else 'No'}",
            f"**Timeout Duration:** {s['timeout_duration']}s",
        ]
        embed = EmbedBuilder.info("Anti-Spam Configuration Updated", "\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="blockuserapps",
        description="Toggle blocking messages from unauthorized User-Installed Apps",
    )
    @app_commands.describe(enabled="Enable to block external app spam")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 10)
    async def blockuserapps_cmd(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(interaction.guild.id, "block_user_apps", int(enabled))
        embed = EmbedBuilder.info(
            "External App Blocking",
            f"User-Installed App messages are now **{'blocked' if enabled else 'allowed'}**.\n"
            f"Blocked apps will be deleted instantly and the triggering user punished.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Badwords Group ──────────────────────────────────────────────

    badwords_group = app_commands.Group(
        name="badwords", description="Manage blacklisted words in this server"
    )

    @badwords_group.command(name="add", description="Add a word to the blacklist")
    @app_commands.describe(word="The word to blacklist")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 5)
    async def badwords_add(self, interaction: discord.Interaction, word: str) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(interaction.guild.id)
        current = settings.get("bad_words", "")
        words = [w.strip().lower() for w in current.split(",") if w.strip()]

        target = word.strip().lower()
        if not target:
            await interaction.response.send_message("Invalid word.", ephemeral=True)
            return

        if target in words:
            await interaction.response.send_message(
                f"`{target}` is already blacklisted.", ephemeral=True
            )
            return

        words.append(target)
        new_val = ",".join(words)
        await db.update_guild_setting(interaction.guild.id, "bad_words", new_val)
        embed = EmbedBuilder.success(
            "Word Blacklisted", f"Added `{target}` to the server blacklist."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @badwords_group.command(name="remove", description="Remove a word from the blacklist")
    @app_commands.describe(word="The word to remove")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 5)
    async def badwords_remove(self, interaction: discord.Interaction, word: str) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(interaction.guild.id)
        current = settings.get("bad_words", "")
        words = [w.strip().lower() for w in current.split(",") if w.strip()]

        target = word.strip().lower()
        if target not in words:
            await interaction.response.send_message(
                f"`{target}` is not in the blacklist.", ephemeral=True
            )
            return

        words.remove(target)
        new_val = ",".join(words)
        await db.update_guild_setting(interaction.guild.id, "bad_words", new_val)
        embed = EmbedBuilder.success(
            "Word Whitelisted", f"Removed `{target}` from the server blacklist."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @badwords_group.command(name="list", description="List all blacklisted words")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 5)
    async def badwords_list(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(interaction.guild.id)
        current = settings.get("bad_words", "")
        words = [w.strip() for w in current.split(",") if w.strip()]

        if not words:
            embed = EmbedBuilder.info(
                "Blacklisted Words", "No words have been blacklisted yet."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        word_list = ", ".join(f"`{w}`" for w in words)
        embed = EmbedBuilder.info(
            "Server Word Blacklist",
            f"Messages containing any of these words will be deleted:\n\n{word_list}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiSpam(bot))
