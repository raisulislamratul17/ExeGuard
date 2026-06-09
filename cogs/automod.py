"""Automod cog for ExeGuard.

Handles webhook protection and mention protection (@everyone/@here/mass
mentions).  Automatically deletes offending webhooks and times out
abusive users.
"""

from __future__ import annotations

from datetime import timedelta

import discord
from discord.ext import commands

from config import SPAM_TIMEOUT_DURATION
from utils.embed_builder import EmbedBuilder


class AutoMod(commands.Cog):
    """Webhook and mention abuse protection."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Webhook protection ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(channel.guild.id)
        if not settings.get("antinuke", True):
            return

        try:
            webhooks = await channel.webhooks()
        except discord.HTTPException:
            return

        guild = channel.guild

        # Check bypass role
        bypass_role_id = settings.get("bypass_role")
        def _has_bypass(m: discord.Member | None) -> bool:
            return bool(bypass_role_id and m and any(r.id == bypass_role_id for r in m.roles))

        processed = []
        async for entry in guild.audit_logs(
            limit=5, action=discord.AuditLogAction.webhook_create
        ):
            if not entry.user:
                continue
            if entry.user.id == self.bot.user.id:  # type: ignore[union-attr]
                continue
            if entry.user.id in processed:
                continue
            if await db.is_trusted_admin(guild.id, entry.user.id):
                continue
            if guild.owner_id == entry.user.id:
                continue
            if entry.user.bot and settings.get("trust_all_bots", 1):
                continue
            bypass_member = guild.get_member(entry.user.id)
            if _has_bypass(bypass_member):
                continue
            processed.append(entry.user.id)

            for wh in webhooks:
                if wh.user and wh.user.id == entry.user.id:
                    try:
                        await wh.delete(
                            reason="ExeGuard: Unauthorized webhook detected"
                        )
                    except discord.HTTPException:
                        pass

            embed = EmbedBuilder.security(
                "Unauthorized Webhook Detected",
                f"**User:** {entry.user} (`{entry.user.id}`)\n"
                f"**Channel:** {channel.mention}\n"
                f"Webhook has been deleted.",
            )
            try:
                await db.conn.execute(
                    "INSERT INTO infractions (guild_id, user_id, rule, action) VALUES (?, ?, ?, ?)",
                    (channel.guild.id, entry.user.id, "Unauthorized webhook created", "webhook deleted"),
                )
                await db.conn.commit()
            except Exception:
                pass
            log_ch_id = settings.get("log_channel")
            if log_ch_id:
                log_ch = guild.get_channel(log_ch_id)
                if isinstance(log_ch, discord.TextChannel):
                    try:
                        await log_ch.send(embed=embed)
                    except discord.HTTPException:
                        pass

    # ── Mention protection ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        assert isinstance(message.author, discord.Member)
        if message.author.guild_permissions.manage_messages:
            return

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)
        if not settings.get("antispam", True):
            return

        # Bypass role check
        bypass_role_id = settings.get("bypass_role")
        if bypass_role_id and any(r.id == bypass_role_id for r in message.author.roles):
            return

        if not message.mention_everyone:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        timeout_secs = settings.get("timeout_duration", SPAM_TIMEOUT_DURATION)
        try:
            await message.author.timeout(
                timedelta(seconds=timeout_secs),
                reason="ExeGuard: @everyone/@here abuse",
            )
        except discord.HTTPException:
            pass

        try:
            await db.conn.execute(
                "INSERT INTO infractions (guild_id, user_id, rule, action) VALUES (?, ?, ?, ?)",
                (message.guild.id, message.author.id, "@everyone/@here abuse", "timeout"),
            )
            await db.conn.commit()
        except Exception:
            pass

        embed = EmbedBuilder.security(
            "Mention Abuse Detected",
            f"**User:** {message.author.mention}\n"
            f"**Reason:** @everyone/@here abuse\n"
            f"**Action:** Timed out for {timeout_secs}s",
        )
        try:
            await message.channel.send(embed=embed, delete_after=10)
        except discord.HTTPException:
            pass

        log_ch_id = settings.get("log_channel")
        if log_ch_id:
            ch = message.guild.get_channel(log_ch_id)
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
