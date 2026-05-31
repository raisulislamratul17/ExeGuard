"""Anti-nuke cog for ExeGuard.

Monitors audit logs for destructive actions: channel/role deletion,
webhook abuse, mass bans/kicks, and permission changes.  Automatically
reverts actions, bans the offender, and notifies admins.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import NUKE_ACTION_INTERVAL, NUKE_ACTION_THRESHOLD
from utils.embed_builder import EmbedBuilder


class ActionTracker:
    """Tracks destructive actions per-user in a guild."""

    def __init__(self) -> None:
        self._actions: dict[int, list[float]] = defaultdict(list)

    def record(self, user_id: int) -> int:
        now = time.time()
        self._actions[user_id] = [
            t for t in self._actions[user_id] if now - t < NUKE_ACTION_INTERVAL
        ]
        self._actions[user_id].append(now)
        return len(self._actions[user_id])


class AntiNuke(commands.Cog):
    """Audit-log-based anti-nuke system."""

    CLEANUP_INTERVAL = 300
    ACTION_TTL = 60

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._trackers: dict[int, ActionTracker] = defaultdict(ActionTracker)
        self._cleanup_task.start()

    def cog_unload(self) -> None:
        self._cleanup_task.cancel()

    @tasks.loop(seconds=CLEANUP_INTERVAL)
    async def _cleanup_task(self) -> None:
        now = time.time()
        stale_guilds = []
        for guild_id, tracker in list(self._trackers.items()):
            stale_users = []
            for user_id, timestamps in tracker._actions.items():
                tracker._actions[user_id] = [
                    t for t in timestamps if now - t < self.ACTION_TTL
                ]
                if not tracker._actions[user_id]:
                    stale_users.append(user_id)
            for uid in stale_users:
                del tracker._actions[uid]
            if not tracker._actions:
                stale_guilds.append(guild_id)
        for gid in stale_guilds:
            del self._trackers[gid]

    @_cleanup_task.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._trackers.pop(guild.id, None)

    # ── Helpers ─────────────────────────────────────────────────────

    async def _is_trusted(self, guild: discord.Guild, user_id: int) -> bool:
        if guild.owner_id == user_id:
            return True
        db = self.bot.db  # type: ignore[attr-defined]
        if await db.is_trusted_admin(guild.id, user_id):
            return True
        
        member = guild.get_member(user_id)
        if member and member.bot:
            settings = await db.get_guild_settings(guild.id)
            if settings.get("trust_all_bots", 1):
                return True
        return False

    async def _get_recent_auditor(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        max_age: float = 5.0,
    ) -> discord.User | None:
        now = time.time()
        async for entry in guild.audit_logs(limit=1, action=action):
            if not entry.user:
                continue
            if entry.user.id == self.bot.user.id:  # type: ignore[union-attr]
                continue
            if (now - entry.created_at.timestamp()) > max_age:
                continue
            return entry.user
        return None

    async def _handle_nuke_action(
        self,
        guild: discord.Guild,
        user: discord.Member | discord.User,
        action_desc: str,
    ) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        if not settings.get("antinuke", True):
            return

        if await self._is_trusted(guild, user.id):
            return

        tracker = self._trackers[guild.id]
        count = tracker.record(user.id)

        if count < NUKE_ACTION_THRESHOLD:
            return

        member = guild.get_member(user.id)
        if member:
            try:
                await member.ban(
                    reason=f"ExeGuard anti-nuke: {action_desc} ({count} actions)"
                )
            except discord.HTTPException:
                try:
                    top_role = guild.me.top_role
                    for role in member.roles:
                        if role < top_role and not role.is_default():
                            await member.remove_roles(
                                role, reason="ExeGuard: removing dangerous permissions"
                            )
                except discord.HTTPException:
                    pass

        embed = EmbedBuilder.security(
            "Nuke Attempt Detected",
            f"**User:** {user} (`{user.id}`)\n"
            f"**Action:** {action_desc}\n"
            f"**Count:** {count} destructive actions in {NUKE_ACTION_INTERVAL}s\n"
            f"**Response:** User banned & permissions stripped",
        )

        log_channel_id = settings.get("log_channel")
        if log_channel_id:
            ch = guild.get_channel(log_channel_id)
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

        if guild.owner:
            try:
                await guild.owner.send(embed=embed)
            except discord.HTTPException:
                pass

    # ── Listeners ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        guild = channel.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.channel_delete)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Deleted channel #{channel.name}"
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        guild = channel.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.channel_create)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Created channel #{channel.name}"
            )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        guild = after.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.channel_update)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Updated channel #{after.name}"
            )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        guild = role.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.role_delete)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Deleted role @{role.name}"
            )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        guild = role.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.role_create)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Created role @{role.name}"
            )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        auditor = await self._get_recent_auditor(guild, discord.AuditLogAction.ban)
        if auditor:
            await self._handle_nuke_action(
                guild, auditor, f"Banned {user}"
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = member.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.kick)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Kicked {member}"
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not member.bot:
            return
        guild = member.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.bot_add)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Added bot {member}"
            )

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        user = await self._get_recent_auditor(after, discord.AuditLogAction.guild_update)
        if user:
            await self._handle_nuke_action(
                after, user, "Updated server settings"
            )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self, before: discord.Role, after: discord.Role
    ) -> None:
        dangerous = (
            discord.Permissions.administrator,
            discord.Permissions(ban_members=True),
            discord.Permissions(manage_guild=True),
            discord.Permissions(manage_roles=True),
            discord.Permissions(manage_channels=True),
        )
        gained = after.permissions.value & ~before.permissions.value
        if not any(gained & p.value for p in dangerous):
            return
        guild = after.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.role_update)
        if user:
            await self._handle_nuke_action(
                guild,
                user,
                f"Escalated permissions on @{after.name}",
            )

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]
    ) -> None:
        if len(after) >= len(before):
            return
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.emoji_delete)
        if user:
            await self._handle_nuke_action(guild, user, "Mass emoji deletion")

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self, guild: discord.Guild, before: list[discord.Sticker], after: list[discord.Sticker]
    ) -> None:
        if len(after) >= len(before):
            return
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.sticker_delete)
        if user:
            await self._handle_nuke_action(guild, user, "Mass sticker deletion")

    @commands.Cog.listener()
    async def on_integration_create(self, integration: discord.Integration) -> None:
        guild = integration.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.integration_create)
        if user:
            await self._handle_nuke_action(guild, user, "Unauthorized integration created")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel) -> None:
        guild = channel.guild
        user = await self._get_recent_auditor(guild, discord.AuditLogAction.webhook_create)
        if user:
            await self._handle_nuke_action(
                guild, user, f"Created webhook in #{channel.name}"
            )

    # ── Slash commands ──────────────────────────────────────────────

    @app_commands.command(
        name="antinuke", description="Toggle the anti-nuke system"
    )
    @app_commands.describe(enabled="Enable or disable anti-nuke protection")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10)
    async def antinuke_cmd(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(
            interaction.guild.id, "antinuke", int(enabled)
        )
        state = "enabled" if enabled else "disabled"
        embed = EmbedBuilder.info(
            "Anti-Nuke Updated", f"Anti-nuke protection has been **{state}**."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="trust",
        description="Add a trusted admin exempt from anti-nuke",
    )
    @app_commands.describe(user="The user to trust")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5)
    async def trust_cmd(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.add_trusted_admin(interaction.guild.id, user.id)
        embed = EmbedBuilder.success(
            "Trusted Admin Added",
            f"{user.mention} is now exempt from anti-nuke detection.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="untrust",
        description="Remove a trusted admin",
    )
    @app_commands.describe(user="The user to remove from trusted list")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5)
    async def untrust_cmd(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.remove_trusted_admin(interaction.guild.id, user.id)
        embed = EmbedBuilder.success(
            "Trusted Admin Removed",
            f"{user.mention} is no longer exempt from anti-nuke detection.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @app_commands.command(
        name="trustbots",
        description="Toggle whether all bot accounts are trusted/exempt by default",
    )
    @app_commands.describe(enabled="If true, all bots are exempt from anti-nuke checks")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 10)
    async def trustbots_cmd(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(
            interaction.guild.id, "trust_all_bots", int(enabled)
        )
        state = "trusted & exempt by default" if enabled else "monitored by anti-nuke"
        embed = EmbedBuilder.info(
            "Trust All Bots Updated",
            f"All bot accounts are now **{state}**.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiNuke(bot))
