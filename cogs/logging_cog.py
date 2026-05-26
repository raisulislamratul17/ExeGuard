"""Logging cog for ExeGuard.

Logs message edits, deletions, role/channel updates, punishments,
member joins/leaves, and webhook activity to dedicated log channels.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_builder import EmbedBuilder


class Logging(commands.Cog):
    """Event logging to dedicated channels."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Helpers ─────────────────────────────────────────────────────

    async def _send_log(
        self,
        guild: discord.Guild,
        embed: discord.Embed,
        channel_key: str = "log_channel",
    ) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        ch_id = settings.get(channel_key)
        if not ch_id:
            return
        ch = guild.get_channel(ch_id)
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=embed)
            except discord.HTTPException:
                pass

    # ── Message events ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        embed = EmbedBuilder.log(
            "Message Edited",
            f"**Author:** {before.author.mention}\n"
            f"**Channel:** {before.channel.mention}\n"
            f"**Before:** {before.content[:500]}\n"
            f"**After:** {after.content[:500]}",
        )
        await self._send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        embed = EmbedBuilder.log(
            "Message Deleted",
            f"**Author:** {message.author.mention}\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Content:** {message.content[:1000] or '*No text content*'}",
        )
        await self._send_log(message.guild, embed)

    # ── Member events ───────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        embed = EmbedBuilder.info(
            "Member Joined",
            f"**User:** {member.mention} (`{member.id}`)\n"
            f"**Account Created:** {discord.utils.format_dt(member.created_at, 'R')}\n"
            f"**Member Count:** {member.guild.member_count}",
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, embed, "join_log_channel")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = ", ".join(r.mention for r in member.roles if not r.is_default())
        embed = EmbedBuilder.log(
            "Member Left",
            f"**User:** {member.mention} (`{member.id}`)\n"
            f"**Roles:** {roles or 'None'}\n"
            f"**Member Count:** {member.guild.member_count}",
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, embed, "join_log_channel")

    # ── Role events ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        embed = EmbedBuilder.log(
            "Role Created",
            f"**Role:** {role.mention} (`{role.id}`)",
        )
        await self._send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        embed = EmbedBuilder.log(
            "Role Deleted",
            f"**Role:** @{role.name} (`{role.id}`)",
        )
        await self._send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(
        self, before: discord.Role, after: discord.Role
    ) -> None:
        changes: list[str] = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if before.permissions != after.permissions:
            changes.append("Permissions changed")
        if before.color != after.color:
            changes.append(f"Color: `{before.color}` → `{after.color}`")
        if not changes:
            return
        embed = EmbedBuilder.log(
            "Role Updated",
            f"**Role:** {after.mention}\n" + "\n".join(changes),
        )
        await self._send_log(after.guild, embed)

    # ── Channel events ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self, channel: discord.abc.GuildChannel
    ) -> None:
        embed = EmbedBuilder.log(
            "Channel Created",
            f"**Channel:** {channel.mention} (`{channel.id}`)",
        )
        await self._send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self, channel: discord.abc.GuildChannel
    ) -> None:
        embed = EmbedBuilder.log(
            "Channel Deleted",
            f"**Channel:** #{channel.name} (`{channel.id}`)",
        )
        await self._send_log(channel.guild, embed)

    # ── Webhook events ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel) -> None:
        embed = EmbedBuilder.security(
            "Webhook Updated",
            f"Webhooks changed in {channel.mention}.",
        )
        await self._send_log(channel.guild, embed)

    # ── Log channel management ──────────────────────────────────────

    @app_commands.command(name="logs", description="Configure log channels")
    @app_commands.describe(
        security="Channel for security logs",
        moderation="Channel for moderation logs",
        joins="Channel for join/leave logs",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 10)
    async def logs_cmd(
        self,
        interaction: discord.Interaction,
        security: discord.TextChannel | None = None,
        moderation: discord.TextChannel | None = None,
        joins: discord.TextChannel | None = None,
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        if security:
            await db.update_guild_setting(
                interaction.guild.id, "log_channel", security.id
            )
        if moderation:
            await db.update_guild_setting(
                interaction.guild.id, "mod_log_channel", moderation.id
            )
        if joins:
            await db.update_guild_setting(
                interaction.guild.id, "join_log_channel", joins.id
            )
        settings = await db.get_guild_settings(interaction.guild.id)
        log_ch = settings.get("log_channel")
        mod_ch = settings.get("mod_log_channel")
        join_ch = settings.get("join_log_channel")
        lines = [
            f"**Security:** <#{log_ch}>" if log_ch else "**Security:** Not set",
            f"**Moderation:** <#{mod_ch}>" if mod_ch else "**Moderation:** Not set",
            f"**Joins:** <#{join_ch}>" if join_ch else "**Joins:** Not set",
        ]
        embed = EmbedBuilder.success(
            "Log Channels Updated", "\n".join(lines)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logging(bot))
