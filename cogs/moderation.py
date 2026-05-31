"""Moderation cog for ExeGuard.

Provides standard slash-command moderation: ban, kick, timeout, warn,
purge, lock, unlock, settings viewer, warning manager, tempbans,
panic switch, and security-audit dashboards.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.embed_builder import EmbedBuilder
from utils.permissions import MEMBER_PERMISSIONS, STAFF_PERMISSIONS, DANGEROUS_PERMISSIONS


def parse_duration(duration_str: str) -> int | None:
    """Parse duration string like '1h', '30m', '7d', '10s' to seconds."""
    match = re.match(r"^(\d+)([smhd])$", duration_str.lower().strip())
    if not match:
        try:
            return int(duration_str)
        except ValueError:
            return None
    val, unit = match.groups()
    val = int(val)
    if unit == "s":
        return val
    elif unit == "m":
        return val * 60
    elif unit == "h":
        return val * 3600
    elif unit == "d":
        return val * 86400
    return None


class Moderation(commands.Cog):
    """Standard and advanced premium moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tempban_lock = asyncio.Lock()
        self._panic_locked: dict[int, set[int]] = {}
        self.check_tempbans.start()

    def cog_unload(self) -> None:
        self.check_tempbans.cancel()

    # ── Tempbans Background Worker ──────────────────────────────────

    @tasks.loop(seconds=10)
    async def check_tempbans(self) -> None:
        if not hasattr(self.bot, "db"):
            return
        db = self.bot.db
        now_str = datetime.now(timezone.utc).isoformat()
        async with self._tempban_lock:
            try:
                async with db.conn.execute(
                    "SELECT * FROM tempbans WHERE unban_timestamp <= ?", (now_str,)
                ) as cursor:
                    rows = await cursor.fetchall()

                for row in rows:
                    guild_id = row["guild_id"]
                    user_id = row["user_id"]
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        try:
                            user = await self.bot.fetch_user(user_id)
                            await guild.unban(user, reason="ExeGuard: Tempban expired")
                            
                            settings = await db.get_guild_settings(guild_id)
                            ch_id = settings.get("mod_log_channel") or settings.get("log_channel")
                            if ch_id:
                                ch = guild.get_channel(ch_id)
                                if isinstance(ch, discord.TextChannel):
                                    embed = EmbedBuilder.success(
                                        "Tempban Expired",
                                        f"**User:** {user.mention} (`{user.id}`)\n"
                                        f"**Action:** Automatically unbanned.",
                                    )
                                    await ch.send(embed=embed)
                        except Exception:
                            pass

                    await db.conn.execute(
                        "DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id),
                    )
                if rows:
                    await db.conn.commit()
            except Exception:
                pass

    @check_tempbans.before_loop
    async def before_check_tempbans(self) -> None:
        await self.bot.wait_until_ready()

    # ── Helpers ─────────────────────────────────────────────────────

    def _is_bot_owner(self, user_id: int) -> bool:
        return user_id in self.bot.owner_ids if self.bot.owner_ids else False

    async def _protect_owner(
        self, interaction: discord.Interaction, user_id: int
    ) -> bool:
        if self._is_bot_owner(user_id):
            await interaction.response.send_message(
                "Cannot perform this action on the bot owner.",
                ephemeral=True,
            )
            return True
        return False

    async def _protect_useful_bot(
        self, interaction: discord.Interaction, user: discord.User | discord.Member
    ) -> bool:
        if not user.bot:
            return False
        guild = interaction.guild
        assert guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        if not settings.get("bot_protection", 1):
            return False
        if guild.get_member(user.id):
            await interaction.response.send_message(
                f"⚠️ **{user.mention}** is an invited server bot. ExeGuard protects useful bots by default.\n"
                f"If you are sure this is malicious, run `/botprotection enabled:False` first.",
                ephemeral=True,
            )
            return True
        return False

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
    @app_commands.checks.cooldown(1, 5)
    async def ban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        if await self._protect_owner(interaction, user.id):
            return
        if await self._protect_useful_bot(interaction, user):
            return
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

    @app_commands.command(name="tempban", description="Temporarily ban a user")
    @app_commands.describe(
        user="User to tempban",
        duration="Duration of the ban (e.g. 30m, 12h, 7d)",
        reason="Reason for the ban",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def tempban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        duration: str,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        if await self._protect_owner(interaction, user.id):
            return
        if await self._protect_useful_bot(interaction, user):
            return
        db = self.bot.db  # type: ignore[attr-defined]
        
        seconds = parse_duration(duration)
        if seconds is None or seconds <= 0:
            await interaction.response.send_message(
                "Invalid duration format. Use e.g. `30m`, `12h`, `7d` or number of seconds.",
                ephemeral=True,
            )
            return

        unban_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        unban_timestamp = unban_time.isoformat()

        # Ban the user
        await interaction.guild.ban(user, reason=f"ExeGuard Tempban by {interaction.user} ({duration}): {reason}")
        
        # Save tempban details
        await db.conn.execute(
            "INSERT OR REPLACE INTO tempbans (guild_id, user_id, unban_timestamp) VALUES (?, ?, ?)",
            (interaction.guild.id, user.id, unban_timestamp),
        )
        await db.conn.commit()
        
        await db.log_mod_action(
            interaction.guild.id, user.id, interaction.user.id, "tempban", f"[{duration}] {reason}"
        )

        embed = EmbedBuilder.security(
            "User Temporarily Banned",
            f"**User:** {user.mention} (`{user.id}`)\n"
            f"**Duration:** {duration}\n"
            f"**Expires:** {discord.utils.format_dt(unban_time, 'F')}\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def kick_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        if await self._protect_owner(interaction, member.id):
            return
        if await self._protect_useful_bot(interaction, member):
            return
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
        duration="Duration in seconds (or specify e.g. 10m, 1h)",
        reason="Reason for the timeout",
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def timeout_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str = "300",
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        if await self._protect_owner(interaction, member.id):
            return
        if await self._protect_useful_bot(interaction, member):
            return
        seconds = parse_duration(duration)
        if seconds is None or seconds <= 0:
            await interaction.response.send_message(
                "Invalid duration. Use e.g. `10m`, `1h` or seconds count.", ephemeral=True
            )
            return

        await member.timeout(
            timedelta(seconds=seconds),
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
            f"**Duration:** {duration}\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 3)
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

    # ── Warnings Management ─────────────────────────────────────────

    @app_commands.command(name="warnings", description="View warnings of a user")
    @app_commands.describe(user="The user to inspect")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings_cmd(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        warns = await db.get_warnings(interaction.guild.id, user.id)

        if not warns:
            embed = EmbedBuilder.info("Warnings", f"{user.mention} has 0 warnings.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        lines = []
        for w in warns[:15]:  # Limit output to first 15 warnings
            lines.append(
                f"**ID:** {w['id']} | **Mod:** <@{w['mod_id']}>\n"
                f"**Reason:** {w['reason']}\n"
                f"**Time:** {w['timestamp']}\n"
            )

        embed = EmbedBuilder.info(
            f"Warnings for {user.name} ({len(warns)} total)",
            "\n".join(lines),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="delwarning", description="Delete a warning by ID")
    @app_commands.describe(id="Warning ID to delete")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delwarning_cmd(
        self, interaction: discord.Interaction, id: int
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        # Check if warning exists and matches guild
        async with db.conn.execute(
            "SELECT * FROM warnings WHERE id = ? AND guild_id = ?",
            (id, interaction.guild.id),
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message(
                "Warning ID not found in this server.", ephemeral=True
            )
            return

        await db.conn.execute("DELETE FROM warnings WHERE id = ?", (id,))
        await db.conn.commit()

        embed = EmbedBuilder.success(
            "Warning Deleted", f"Warning **#{id}** has been successfully removed."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a user")
    @app_commands.describe(user="User to clear warnings for")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clearwarnings_cmd(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        await db.conn.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, user.id),
        )
        await db.conn.commit()

        embed = EmbedBuilder.success(
            "Warnings Cleared", f"All warnings for {user.mention} have been cleared."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Channel / Server Locks ──────────────────────────────────────

    @app_commands.command(name="purge", description="Delete messages in bulk")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 10)
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
    @app_commands.checks.cooldown(1, 5)
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
    @app_commands.checks.cooldown(1, 5)
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

    # ── Emergency Panic Button ──────────────────────────────────────

    @app_commands.command(name="panic", description="Activate or deactivate Emergency Panic Lockdown mode")
    @app_commands.describe(enabled="Toggles server panic lockdown")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 30)
    async def panic_cmd(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        await interaction.response.defer(ephemeral=True)

        if enabled:
            await db.update_guild_setting(interaction.guild.id, "antispam", 1)
            await db.update_guild_setting(interaction.guild.id, "antiraid", 1)
            await db.update_guild_setting(interaction.guild.id, "raid_level", "high")
            await db.update_guild_setting(interaction.guild.id, "antinuke", 1)
            await db.update_guild_setting(interaction.guild.id, "verification", 1)
            
            locked_channels = set()
            for ch in interaction.guild.text_channels:
                try:
                    overwrite = ch.overwrites_for(interaction.guild.default_role)
                    if overwrite.send_messages is not False:
                        overwrite.send_messages = False
                        await ch.set_permissions(
                            interaction.guild.default_role,
                            overwrite=overwrite,
                            reason="ExeGuard: Emergency panic mode activated"
                        )
                        locked_channels.add(ch.id)
                except Exception:
                    pass

            self._panic_locked[interaction.guild.id] = locked_channels

            embed = EmbedBuilder.security(
                "Panic Mode Activated",
                "⚠️ **Emergency Server Lockdown Active** ⚠️\n\n"
                "- All protections (Anti-Nuke, Anti-Spam, High Anti-Raid, Verification) are set to maximum.\n"
                "- Every public channel has been locked down completely.\n"
                "- Use `/panic enabled:False` to disable lockdown.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            await self._log_action(interaction.guild, embed)

            if interaction.guild.owner:
                try:
                    await interaction.guild.owner.send(embed=embed)
                except Exception:
                    pass
        else:
            locked_channels = self._panic_locked.get(interaction.guild.id, set())
            for ch in interaction.guild.text_channels:
                if ch.id in locked_channels:
                    try:
                        overwrite = ch.overwrites_for(interaction.guild.default_role)
                        if overwrite.send_messages is False:
                            overwrite.send_messages = None
                            await ch.set_permissions(
                                interaction.guild.default_role,
                                overwrite=overwrite,
                                reason="ExeGuard: Panic mode deactivated"
                            )
                    except Exception:
                        pass

            self._panic_locked.pop(interaction.guild.id, None)

            embed = EmbedBuilder.success(
                "Panic Mode Deactivated",
                "Lockdown has been lifted. Public channel permissions have been restored to defaults.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            await self._log_action(interaction.guild, embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._panic_locked.pop(guild.id, None)

    # ── Security Audit Command ──────────────────────────────────────

    @app_commands.command(name="security-audit", description="Analyze the guild's security status")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 30)
    async def security_audit_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        await interaction.response.defer(ephemeral=True)
        s = await db.get_guild_settings(interaction.guild.id)
        
        score = 0
        vulnerabilities = []
        recommendations = []

        # Audit toggles
        if s.get("antispam"):
            score += 20
        else:
            vulnerabilities.append("🔴 Anti-Spam protection is disabled.")
            recommendations.append("Use `/antispam enabled:True` to shield against spammers.")

        if s.get("antiraid"):
            score += 20
        else:
            vulnerabilities.append("🔴 Anti-Raid protection is disabled.")
            recommendations.append("Use `/antiraid level:medium` to prevent bot storms.")

        if s.get("antinuke"):
            score += 20
        else:
            vulnerabilities.append("🔴 Anti-Nuke auditing is disabled.")
            recommendations.append("Use `/antinuke enabled:True` to block rogue staff members.")

        if s.get("verification"):
            score += 15
        else:
            vulnerabilities.append("🟡 Server Verification is disabled.")
            recommendations.append("Run `/verify method:captcha` to gate new members.")

        # Log configuration
        if s.get("log_channel") and s.get("mod_log_channel"):
            score += 10
        else:
            vulnerabilities.append("🟡 Logging channels are not fully set up.")
            recommendations.append("Configure security logs with `/setup` wizard.")

        # Admin Roles Audit
        admin_roles = []
        for r in interaction.guild.roles:
            if r.permissions.administrator and not r.is_default():
                admin_roles.append(r)

        role_count = len(admin_roles)
        if role_count <= 3:
            score += 15
        else:
            deduction = min((role_count - 3) * 5, 15)
            score += (15 - deduction)
            vulnerabilities.append(f"🟡 Massive Administrator Roles count ({role_count} roles).")
            recommendations.append("Review roles with administrative permissions to restrict scope.")

        # Check if @everyone has administrative permissions
        if interaction.guild.default_role.permissions.administrator:
            score = max(score - 30, 0)
            vulnerabilities.append("🚨 CRITICAL: The `@everyone` role has Administrator permissions!")
            recommendations.append("IMMEDIATELY remove administrative permissions from the `@everyone` role.")

        # Check if @everyone can use external apps
        if interaction.guild.default_role.permissions.use_external_apps:
            score = max(score - 15, 0)
            vulnerabilities.append("🚨 CRITICAL: The `@everyone` role is allowed to **Use External Apps**!")
            recommendations.append("Disable the 'Use External Apps' permission for `@everyone` in Server Settings -> Roles to block malicious spam apps entirely.")

        # Check channel safety
        unsafe_channels = 0
        for ch in interaction.guild.text_channels:
            perms = ch.permissions_for(interaction.guild.default_role)
            if perms.send_messages and (perms.manage_messages or perms.manage_channels):
                unsafe_channels += 1

        if unsafe_channels > 0:
            score = max(score - 10, 0)
            vulnerabilities.append(f"🟡 Unsafe default permissions in {unsafe_channels} channels.")
            recommendations.append("Ensure @everyone does not have permission to manage messages or channels.")

        # Color and Indicator bar
        if score >= 80:
            bar_color = "🟩"
            embed_color = 0x2ECC71  # Success Green
        elif score >= 50:
            bar_color = "🟨"
            embed_color = 0xF1C40F  # Orange/Yellow
        else:
            bar_color = "🟥"
            embed_color = 0xE74C3C  # Danger Red

        filled_bars = int(score / 10)
        indicator_bar = (bar_color * filled_bars) + ("⬜" * (10 - filled_bars))

        vuln_text = "\n".join(vulnerabilities) if vulnerabilities else "✅ No significant security flaws found."
        recom_text = "\n".join(recommendations) if recommendations else "✅ Server setup matches recommended best practices."

        embed = discord.Embed(
            title=f"🛡️ ExeGuard Security Audit — {interaction.guild.name}",
            color=embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Overall Security Score",
            value=f"**{score}/100**\n`{indicator_bar}`",
            inline=False
        )
        embed.add_field(name="Identified Vulnerabilities", value=vuln_text, inline=False)
        embed.add_field(name="Recommended Fixes", value=recom_text, inline=False)
        embed.set_footer(text="ExeGuard Security Systems")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="botprotection",
        description="Toggle protection for invited server bots",
    )
    @app_commands.describe(enabled="Enable to prevent accidental bans of useful bots")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 10)
    async def botprotection_cmd(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(interaction.guild.id, "bot_protection", int(enabled))
        embed = EmbedBuilder.info(
            "Bot Protection",
            f"Protection for invited bots is now **{'enabled' if enabled else 'disabled'}**.\n"
            f"Staff will be blocked from banning/kicking bots added to the server.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Configuration Settings ──────────────────────────────────────

    @app_commands.command(
        name="settings", description="View current ExeGuard settings"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 5)
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
            f"**Trust All Bots:** {'On' if s.get('trust_all_bots', 1) else 'Off'}",
            f"**Security Logs:** <#{log_ch}>" if log_ch else "**Security Logs:** Not set",
            f"**Mod Logs:** <#{mod_ch}>" if mod_ch else "**Mod Logs:** Not set",
            f"**Join Logs:** <#{join_ch}>" if join_ch else "**Join Logs:** Not set",
        ]
        embed = EmbedBuilder.info(
            f"ExeGuard Settings — {interaction.guild.name}", "\n".join(lines)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Role Security ───────────────────────────────────────────────

    @app_commands.command(name="sanitize_role", description="Clean a role by applying a safety template")
    @app_commands.describe(role="The role to clean", template="Safety template (staff, member, clear)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sanitize_role(self, interaction: discord.Interaction, role: discord.Role, template: str) -> None:
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I cannot manage roles higher than mine!", ephemeral=True)
            return
        
        template = template.lower()
        new_perms = discord.Permissions.none()
        
        if template == "staff":
            new_perms.update(**STAFF_PERMISSIONS)
        elif template == "member":
            new_perms.update(**MEMBER_PERMISSIONS)
        elif template == "clear":
            new_perms = discord.Permissions.none()
        else:
            await interaction.response.send_message("Invalid template! Use `staff`, `member`, or `clear`.", ephemeral=True)
            return

        try:
            await role.edit(permissions=new_perms, reason=f"ExeGuard: Role Sanitization ({template})")
            embed = EmbedBuilder.success("Role Sanitized", f"Applied `{template}` template to {role.mention}.\nDangerous permissions have been removed.")
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to edit this role!", ephemeral=True)

    @app_commands.command(name="secure_everyone", description="Harden the @everyone role permissions")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def secure_everyone(self, interaction: discord.Interaction) -> None:
        role = interaction.guild.default_role
        perms = role.permissions
        
        # Strip dangerous perms from @everyone
        to_strip = {
            "mention_everyone": False,
            "manage_messages": False,
            "manage_roles": False,
            "manage_channels": False,
            "manage_webhooks": False,
            "administrator": False,
            "manage_guild": False,
            "create_public_threads": False,
            "create_private_threads": False,
        }
        perms.update(**to_strip)
        
        try:
            await role.edit(permissions=perms, reason="ExeGuard: @everyone hardening")
            embed = EmbedBuilder.success("@everyone Hardened", "Dangerous permissions (Mention Everyone, Manage Messages, Administrator, etc.) have been stripped from @everyone.")
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to edit @everyone!", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
