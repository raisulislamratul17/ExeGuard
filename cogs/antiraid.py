"""Anti-raid cog for ExeGuard.

Detects mass joins, suspicious account ages, bot waves, and suspicious
usernames.  Automatically locks down the server, activates slowmode,
and kicks suspicious accounts.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    RAID_JOIN_INTERVAL,
    RAID_JOIN_THRESHOLD,
    RAID_LOCKDOWN_DURATION,
    RAID_MIN_ACCOUNT_AGE,
    RAID_SLOWMODE_DELAY,
)
from utils.embed_builder import EmbedBuilder

SUSPICIOUS_NAME_FRAGMENTS = [
    "raid",
    "nuke",
    "hack",
    "free nitro",
    "discord.gg/",
    "bit.ly/",
]


class AntiRaid(commands.Cog):
    """Real-time raid detection and automatic lockdown."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._join_log: dict[int, list[float]] = defaultdict(list)
        self._lockdowns: dict[int, bool] = {}

    # ── Helpers ─────────────────────────────────────────────────────

    def _is_suspicious_name(self, name: str) -> bool:
        lower = name.lower()
        return any(frag in lower for frag in SUSPICIOUS_NAME_FRAGMENTS)

    def _is_young_account(self, member: discord.Member) -> bool:
        age = datetime.now(timezone.utc) - member.created_at
        return age < timedelta(days=RAID_MIN_ACCOUNT_AGE)

    async def _detect_raid(self, guild_id: int) -> bool:
        now = time.time()
        self._join_log[guild_id] = [
            t for t in self._join_log[guild_id] if now - t < RAID_JOIN_INTERVAL
        ]
        self._join_log[guild_id].append(now)
        return len(self._join_log[guild_id]) >= RAID_JOIN_THRESHOLD

    async def _lockdown(self, guild: discord.Guild, reason: str) -> None:
        if self._lockdowns.get(guild.id):
            return
        self._lockdowns[guild.id] = True

        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)

        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=f"ExeGuard raid lockdown: {reason}",
                )
                if channel.slowmode_delay < RAID_SLOWMODE_DELAY:
                    await channel.edit(slowmode_delay=RAID_SLOWMODE_DELAY)
            except discord.HTTPException:
                continue

        embed = EmbedBuilder.security(
            "Raid Detected — Server Locked Down",
            f"**Reason:** {reason}\n"
            f"The server has been locked. Use `/unlockdown` to restore access.",
        )
        log_channel_id = settings.get("log_channel")
        if log_channel_id:
            ch = guild.get_channel(log_channel_id)
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

        await asyncio.sleep(RAID_LOCKDOWN_DURATION)
        await self._unlockdown(guild)

    async def _unlockdown(self, guild: discord.Guild) -> None:
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason="ExeGuard raid lockdown lifted",
                )
                await channel.edit(slowmode_delay=0)
            except discord.HTTPException:
                continue
        self._lockdowns[guild.id] = False

    # ── Listeners ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(member.guild.id)
        if not settings.get("antiraid", True):
            return

        raid_level = settings.get("raid_level", "medium")

        if self._is_suspicious_name(member.name):
            try:
                await member.kick(reason="ExeGuard: Suspicious username")
            except discord.HTTPException:
                pass
            return

        if raid_level in ("medium", "high") and self._is_young_account(member):
            try:
                await member.kick(
                    reason="ExeGuard: Account too young during raid protection"
                )
            except discord.HTTPException:
                pass
            return

        if await self._detect_raid(member.guild.id):
            asyncio.create_task(
                self._lockdown(member.guild, "Mass join detected")
            )

    # ── Slash commands ──────────────────────────────────────────────

    @app_commands.command(
        name="lockdown", description="Manually lock down the server"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def lockdown_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        asyncio.create_task(
            self._lockdown(interaction.guild, "Manual lockdown")
        )
        embed = EmbedBuilder.security(
            "Lockdown Activated",
            "All channels have been locked. Use `/unlockdown` to restore.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unlockdown", description="Lift the server lockdown"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unlockdown_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        await self._unlockdown(interaction.guild)
        embed = EmbedBuilder.success(
            "Lockdown Lifted", "All channels have been restored."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="antiraid",
        description="Configure the anti-raid protection level",
    )
    @app_commands.describe(level="Protection level: low, medium, or high")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def antiraid_cmd(
        self,
        interaction: discord.Interaction,
        level: str,
    ) -> None:
        assert interaction.guild is not None
        level = level.lower()
        if level not in ("low", "medium", "high"):
            await interaction.response.send_message(
                "Level must be `low`, `medium`, or `high`.", ephemeral=True
            )
            return
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(interaction.guild.id, "raid_level", level)
        embed = EmbedBuilder.info(
            "Anti-Raid Updated",
            f"Protection level set to **{level}**.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiRaid(bot))
