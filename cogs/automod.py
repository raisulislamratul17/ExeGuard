"""Automod cog for ExeGuard.

Handles webhook protection, mention protection (@everyone/@here/mass
mentions), and Discord invite-link filtering.  Automatically deletes
offending messages/webhooks and times out abusive users.
"""

from __future__ import annotations

import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from config import SPAM_MENTION_LIMIT, SPAM_TIMEOUT_DURATION
from utils.embed_builder import EmbedBuilder

INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:discord\.gg|discord(?:app)?\.com/invite)"
    r"/[A-Za-z0-9\-]+",
    re.IGNORECASE,
)


class AutoMod(commands.Cog):
    """Webhook, mention-abuse, and invite-link protection."""

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
        async for entry in guild.audit_logs(
            limit=5, action=discord.AuditLogAction.webhook_create
        ):
            if not entry.user:
                continue
            if entry.user.id == self.bot.user.id:  # type: ignore[union-attr]
                continue
            if await db.is_trusted_admin(guild.id, entry.user.id):
                continue
            if guild.owner_id == entry.user.id:
                continue

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
            log_ch_id = settings.get("log_channel")
            if log_ch_id:
                log_ch = guild.get_channel(log_ch_id)
                if isinstance(log_ch, discord.TextChannel):
                    try:
                        await log_ch.send(embed=embed)
                    except discord.HTTPException:
                        pass
            break

    # ── Mention protection & invite-link filter ───────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return
        # Never act on our own messages
        if message.author.id == self.bot.user.id:  # type: ignore[union-attr]
            return

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(message.guild.id)

        # ── Invite-link filter (applies to bots AND users) ───────
        if settings.get("anti_invite", True) and INVITE_RE.search(message.content):
            is_member = isinstance(message.author, discord.Member)
            exempt = (
                is_member
                and message.author.guild_permissions.manage_messages
            )
            if not exempt:
                await self._handle_invite(message, settings)
                return  # already handled, skip mention check

        # ── Mention abuse (users only) ───────────────────────────
        if message.author.bot:
            return
        assert isinstance(message.author, discord.Member)
        if message.author.guild_permissions.manage_messages:
            return
        if not settings.get("antispam", True):
            return

        triggered = False
        reason = ""

        if message.mention_everyone:
            triggered = True
            reason = "@everyone/@here mention"
        elif len(message.mentions) + len(message.role_mentions) > SPAM_MENTION_LIMIT:
            triggered = True
            reason = f"Mass mentions ({len(message.mentions) + len(message.role_mentions)})"

        if not triggered:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        timeout_secs = settings.get("timeout_duration", SPAM_TIMEOUT_DURATION)
        try:
            await message.author.timeout(
                timedelta(seconds=timeout_secs),
                reason=f"ExeGuard: {reason}",
            )
        except discord.HTTPException:
            pass

        embed = EmbedBuilder.security(
            "Mention Abuse Detected",
            f"**User:** {message.author.mention}\n"
            f"**Reason:** {reason}\n"
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

    # ── Invite-link handler ──────────────────────────────────────

    async def _handle_invite(
        self,
        message: discord.Message,
        settings: dict,
    ) -> None:
        assert message.guild is not None

        # Allow invites that point to the current server
        invite_codes = INVITE_RE.findall(message.content)
        try:
            guild_invites = await message.guild.invites()
            guild_codes = {inv.code for inv in guild_invites}
            vanity = message.guild.vanity_url_code
            if vanity:
                guild_codes.add(vanity)
        except discord.HTTPException:
            guild_codes = set()

        all_own = True
        for raw_url in invite_codes:
            code = raw_url.rstrip("/").split("/")[-1]
            if code not in guild_codes:
                all_own = False
                break
        if all_own:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        action = "Message deleted"
        # Timeout the author if they are a regular member (not a bot)
        if isinstance(message.author, discord.Member) and not message.author.bot:
            timeout_secs = settings.get("timeout_duration", SPAM_TIMEOUT_DURATION)
            try:
                await message.author.timeout(
                    timedelta(seconds=timeout_secs),
                    reason="ExeGuard: Discord invite link",
                )
                action = f"Timed out for {timeout_secs}s"
            except discord.HTTPException:
                pass

        embed = EmbedBuilder.security(
            "Invite Link Blocked",
            f"**User:** {message.author.mention}\n"
            f"**Reason:** Unauthorized Discord invite link\n"
            f"**Action:** {action}",
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

    # ── Slash command ────────────────────────────────────────────

    @app_commands.command(
        name="antiinvite",
        description="Toggle Discord invite-link filtering",
    )
    @app_commands.describe(
        enabled="Enable or disable invite-link blocking",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiinvite_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(
            interaction.guild.id, "anti_invite", int(enabled)
        )
        state = "enabled" if enabled else "disabled"
        embed = EmbedBuilder.info(
            "Anti-Invite Settings",
            f"Invite-link filtering has been **{state}**.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
