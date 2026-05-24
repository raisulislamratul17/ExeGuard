"""Moderation cog for ExeGuard.

Provides standard slash-command moderation: ban, kick, timeout, warn,
purge, lock, unlock, and a settings viewer.
"""

from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_builder import EmbedBuilder


class Moderation(commands.Cog):
    """Standard moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Helpers ─────────────────────────────────────────────────────

    async def _log_action(
        self,
        guild: discord.Guild,
        embed: discord.Embed,
    ) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        ch_id = settings.get("mod_log_channel") or settings.get("log_channel")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

    # ── Commands ────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(user="User to ban", reason="Reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        await interaction.guild.ban(user, reason=f"{interaction.user}: {reason}")
        db = self.bot.db  # type: ignore[attr-defined]
        await db.log_mod_action(
            interaction.guild.id, user.id, interaction.user.id, "ban", reason
        )
        embed = EmbedBuilder.security(
            "User Banned",
            f"**User:** {user.mention} (`{user.id}`)\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        await member.kick(reason=f"{interaction.user}: {reason}")
        db = self.bot.db  # type: ignore[attr-defined]
        await db.log_mod_action(
            interaction.guild.id, member.id, interaction.user.id, "kick", reason
        )
        embed = EmbedBuilder.security(
            "Member Kicked",
            f"**Member:** {member.mention} (`{member.id}`)\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(
        member="Member to timeout",
        duration="Duration in seconds",
        reason="Reason for the timeout",
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: int = 300,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        await member.timeout(
            timedelta(seconds=duration),
            reason=f"{interaction.user}: {reason}",
        )
        db = self.bot.db  # type: ignore[attr-defined]
        await db.log_mod_action(
            interaction.guild.id,
            member.id,
            interaction.user.id,
            "timeout",
            reason,
        )
        embed = EmbedBuilder.warning(
            "Member Timed Out",
            f"**Member:** {member.mention}\n"
            f"**Duration:** {duration}s\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        warn_id = await db.add_warning(
            interaction.guild.id, member.id, interaction.user.id, reason
        )
        warnings = await db.get_warnings(interaction.guild.id, member.id)
        await db.log_mod_action(
            interaction.guild.id,
            member.id,
            interaction.user.id,
            "warn",
            reason,
        )
        embed = EmbedBuilder.warning(
            "Member Warned",
            f"**Member:** {member.mention}\n"
            f"**Warning #{warn_id}** (total: {len(warnings)})\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

        try:
            dm_embed = EmbedBuilder.warning(
                f"Warning in {interaction.guild.name}",
                f"**Reason:** {reason}\n"
                f"**Total warnings:** {len(warnings)}",
            )
            await member.send(embed=dm_embed)
        except discord.HTTPException:
            pass

    @app_commands.command(name="purge", description="Delete messages in bulk")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_cmd(
        self,
        interaction: discord.Interaction,
        amount: int,
    ) -> None:
        assert isinstance(interaction.channel, discord.TextChannel)
        amount = min(amount, 100)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        embed = EmbedBuilder.success(
            "Messages Purged",
            f"Deleted **{len(deleted)}** messages.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.describe(channel="Channel to lock (defaults to current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        assert interaction.guild is not None
        target = channel or interaction.channel
        assert isinstance(target, discord.TextChannel)
        overwrite = target.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await target.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Channel locked by {interaction.user}",
        )
        embed = EmbedBuilder.security(
            "Channel Locked",
            f"{target.mention} has been locked.",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (defaults to current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        assert interaction.guild is not None
        target = channel or interaction.channel
        assert isinstance(target, discord.TextChannel)
        overwrite = target.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await target.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite,
            reason=f"Channel unlocked by {interaction.user}",
        )
        embed = EmbedBuilder.success(
            "Channel Unlocked",
            f"{target.mention} has been unlocked.",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="settings", description="View current ExeGuard settings"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        s = await db.get_guild_settings(interaction.guild.id)
        log_ch = s.get("log_channel")
        mod_ch = s.get("mod_log_channel")
        join_ch = s.get("join_log_channel")
        lines = [
            f"**Anti-Spam:** {'On' if s.get('antispam') else 'Off'} (threshold: {s.get('spam_threshold', 5)})",
            f"**Anti-Raid:** {'On' if s.get('antiraid') else 'Off'} (level: {s.get('raid_level', 'medium')})",
            f"**Anti-Nuke:** {'On' if s.get('antinuke') else 'Off'}",
            f"**Verification:** {'On' if s.get('verification') else 'Off'}",
            f"**Security Logs:** <#{log_ch}>" if log_ch else "**Security Logs:** Not set",
            f"**Mod Logs:** <#{mod_ch}>" if mod_ch else "**Mod Logs:** Not set",
            f"**Join Logs:** <#{join_ch}>" if join_ch else "**Join Logs:** Not set",
        ]
        embed = EmbedBuilder.info(
            f"ExeGuard Settings — {interaction.guild.name}", "\n".join(lines)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
