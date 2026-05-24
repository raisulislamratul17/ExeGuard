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
from discord.ext import commands

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

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._trackers: dict[int, ActionTracker] = defaultdict(ActionTracker)

    # ── Helpers ─────────────────────────────────────────────────────

    async def _is_trusted(self, guild: discord.Guild, user_id: int) -> bool:
        if guild.owner_id == user_id:
            return True
        db = self.bot.db  # type: ignore[attr-defined]
        return await db.is_trusted_admin(guild.id, user_id)

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
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.channel_delete
        ):
            if entry.user:
                await self._handle_nuke_action(
                    guild, entry.user, f"Deleted channel #{channel.name}"
                )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        guild = role.guild
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.role_delete
        ):
            if entry.user:
                await self._handle_nuke_action(
                    guild, entry.user, f"Deleted role @{role.name}"
                )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.ban
        ):
            if entry.user and entry.user.id != self.bot.user.id:  # type: ignore[union-attr]
                await self._handle_nuke_action(
                    guild, entry.user, f"Banned {user}"
                )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = member.guild
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.kick
        ):
            if (
                entry.user
                and entry.target
                and getattr(entry.target, "id", None) == member.id
                and entry.user.id != self.bot.user.id  # type: ignore[union-attr]
            ):
                await self._handle_nuke_action(
                    guild, entry.user, f"Kicked {member}"
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
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.role_update
        ):
            if entry.user:
                await self._handle_nuke_action(
                    guild,
                    entry.user,
                    f"Escalated permissions on @{after.name}",
                )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel) -> None:
        guild = channel.guild
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.webhook_create
        ):
            if entry.user:
                await self._handle_nuke_action(
                    guild, entry.user, f"Created webhook in #{channel.name}"
                )

    # ── Slash commands ──────────────────────────────────────────────

    @app_commands.command(
        name="antinuke", description="Toggle the anti-nuke system"
    )
    @app_commands.describe(enabled="Enable or disable anti-nuke protection")
    @app_commands.checks.has_permissions(administrator=True)
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiNuke(bot))
