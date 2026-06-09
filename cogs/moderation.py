"""Moderation cog for ExeGuard.

Provides standard slash-command moderation: ban, kick, timeout, warn,
purge, lock, unlock, settings viewer, warning manager, tempbans,
panic switch, and security-audit dashboards.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time as time_module
from datetime import datetime, timedelta, timezone

log = logging.getLogger("exeguard.moderation")

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.embed_builder import EmbedBuilder
from config import COLOR_PRIMARY, COLOR_SUCCESS, COLOR_DANGER


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
        self._snipes: dict[int, discord.Message] = {}
        self._edit_snipes: dict[int, tuple[discord.Message, discord.Message]] = {}
        self.check_tempbans.start()

    def cog_unload(self) -> None:
        self.check_tempbans.cancel()

    # ── Snipe Listeners ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        self._snipes[message.channel.id] = message

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.author.bot:
            return
        self._edit_snipes[before.channel.id] = (before, after)

    @app_commands.command(name="snipe", description="View the last deleted message in this channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def snipe_cmd(self, interaction: discord.Interaction) -> None:
        message = self._snipes.get(interaction.channel_id)
        if not message:
            await interaction.response.send_message("There is nothing to snipe!", ephemeral=True)
            return
        
        embed = discord.Embed(description=message.content, color=COLOR_PRIMARY, timestamp=message.created_at)
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="editsnipe", description="View the last edited message in this channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def editsnipe_cmd(self, interaction: discord.Interaction) -> None:
        data = self._edit_snipes.get(interaction.channel_id)
        if not data:
            await interaction.response.send_message("There is nothing to edit-snipe!", ephemeral=True)
            return
        
        before, after = data
        embed = discord.Embed(color=COLOR_PRIMARY, timestamp=after.edited_at or datetime.now(timezone.utc))
        embed.set_author(name=before.author.display_name, icon_url=before.author.display_avatar.url)
        embed.add_field(name="Before", value=before.content or "*(No content)*", inline=False)
        embed.add_field(name="After", value=after.content or "*(No content)*", inline=False)
        await interaction.response.send_message(embed=embed)

    # ── Tempbans Background Worker ──────────────────────────────────

    @tasks.loop(seconds=10)
    async def check_tempbans(self) -> None:
        if not hasattr(self.bot, "db"):
            return
        db = self.bot.db
        now_ts = int(time_module.time())
        try:
            async with self._tempban_lock:
                async with db.conn.execute(
                    "SELECT * FROM tempbans WHERE unban_timestamp <= ?", (now_ts,)
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
            log.exception("Tempban check loop failed")
        finally:
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
        unban_timestamp = int(unban_time.timestamp())

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
    @app_commands.describe(warning_id="Warning ID to delete")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delwarning_cmd(
        self, interaction: discord.Interaction, warning_id: int
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        async with db.conn.execute(
            "SELECT * FROM warnings WHERE id = ? AND guild_id = ?",
            (warning_id, interaction.guild.id),
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message(
                "Warning ID not found in this server.", ephemeral=True
            )
            return

        await db.conn.execute("DELETE FROM warnings WHERE id = ?", (warning_id,))
        await db.conn.commit()

        embed = EmbedBuilder.success(
            "Warning Deleted", f"Warning **#{warning_id}** has been successfully removed."
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
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("This command only works in text channels.", ephemeral=True)
            return
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
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("This command only works in text channels.", ephemeral=True)
            return
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
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message("This command only works in text channels.", ephemeral=True)
            return
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

    @app_commands.command(name="unban", description="Unban a user from the server")
    @app_commands.describe(user_id="ID of the user to unban", reason="Reason for the unban")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def unban_cmd(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
            embed = EmbedBuilder.success(
                "User Unbanned",
                f"**User:** {user.mention} (`{user.id}`)\n"
                f"**Moderator:** {interaction.user.mention}\n"
                f"**Reason:** {reason}",
            )
            await interaction.response.send_message(embed=embed)
            await self._log_action(interaction.guild, embed)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("Invalid user ID or user not banned.", ephemeral=True)

    @app_commands.command(name="softban", description="Ban and immediately unban a user to clear messages")
    @app_commands.describe(user="User to softban", reason="Reason for the softban")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def softban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        assert interaction.guild is not None
        if await self._protect_owner(interaction, user.id):
            return
        await interaction.guild.ban(user, reason=f"Softban by {interaction.user}: {reason}", delete_message_days=7)
        await interaction.guild.unban(user, reason="Softban cleanup")
        
        embed = EmbedBuilder.security(
            "User Softbanned",
            f"**User:** {user.mention} (`{user.id}`)\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Action:** Banned and unbanned (messages cleared)\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="nickname", description="Change a member's nickname")
    @app_commands.describe(member="Member to change nickname", nickname="New nickname (leave empty to reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str | None = None,
    ) -> None:
        old_nick = member.display_name
        await member.edit(nick=nickname, reason=f"Changed by {interaction.user}")
        embed = EmbedBuilder.info(
            "Nickname Updated",
            f"**Member:** {member.mention}\n"
            f"**Old:** {old_nick}\n"
            f"**New:** {nickname or member.name}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="userinfo", description="Get detailed information about a user")
    @app_commands.describe(user="User to get info for")
    async def userinfo_cmd(
        self, interaction: discord.Interaction, user: discord.Member | discord.User | None = None
    ) -> None:
        user = user or interaction.user
        member = user if isinstance(user, discord.Member) else None
        
        embed = discord.Embed(title=f"User Info - {user.name}", color=COLOR_PRIMARY)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Bot?", value="Yes" if user.bot else "No", inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(user.created_at, 'R'), inline=True)
        
        if member:
            embed.add_field(name="Joined At", value=discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Unknown", inline=True)
            roles = [r.mention for r in reversed(member.roles) if not r.is_default()]
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else "") or "None", inline=False)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(user="User to get avatar for")
    async def avatar_cmd(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        user = user or interaction.user
        embed = discord.Embed(title=f"Avatar - {user.name}", color=COLOR_PRIMARY)
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Get a user's banner")
    @app_commands.describe(user="User to get banner for")
    async def banner_cmd(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        user = user or interaction.user
        user = await self.bot.fetch_user(user.id)
        if not user.banner:
            await interaction.response.send_message("This user has no banner.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Banner - {user.name}", color=COLOR_PRIMARY)
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="infractions", description="View AutoMod infractions for a user")
    @app_commands.describe(user="User to check infractions for")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def infractions_cmd(self, interaction: discord.Interaction, user: discord.User) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT rule, action, timestamp FROM infractions WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 15",
            (interaction.guild.id, user.id),
        ) as cursor:
            rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message(f"No infractions for {user.mention}.", ephemeral=True)
            return
        lines = [f"**{r['rule']}** → {r['action']} ({r['timestamp']})" for r in rows]
        embed = EmbedBuilder.warning(f"AutoMod Infractions — {user.name} ({len(rows)})", "\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="history", description="View moderation history for a user")
    @app_commands.describe(user="User to check history for")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def history_cmd(self, interaction: discord.Interaction, user: discord.User) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT * FROM mod_actions WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 10",
            (interaction.guild.id, user.id)
        ) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await interaction.response.send_message(f"No history found for {user.mention}.", ephemeral=True)
            return
            
        lines = []
        for r in rows:
            lines.append(f"**{r['action'].upper()}** - <@{r['mod_id']}>: {r['reason']} ({r['timestamp']})")
            
        embed = EmbedBuilder.info(f"Mod History - {user.name}", "\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="health", description="Analyze the guild's security status")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(1, 30)
    async def health_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]
        
        await interaction.response.defer(ephemeral=True)
        s = await db.get_guild_settings(interaction.guild.id)
        
        score = 0
        vulnerabilities = []

        # Audit toggles
        if s.get("antispam"): score += 20
        else: vulnerabilities.append("🔴 Anti-Spam disabled")

        if s.get("antinuke"): score += 20
        else: vulnerabilities.append("🔴 Anti-Nuke disabled")

        if s.get("verification"): score += 20
        else: vulnerabilities.append("🟡 Verification disabled")

        if s.get("log_channel"): score += 20
        else: vulnerabilities.append("🟡 Logging not configured")

        if s.get("antiraid"): score += 20
        else: vulnerabilities.append("🟡 Anti-Raid disabled")

        # Threat Level
        if score >= 90: threat = "LOW"
        elif score >= 70: threat = "MEDIUM"
        elif score >= 40: threat = "HIGH"
        else: threat = "CRITICAL"

        embed = discord.Embed(
            title=f"Security Health - {interaction.guild.name}",
            color=COLOR_SUCCESS if score > 70 else (COLOR_DANGER if score < 40 else 0xF1C40F),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Security Score", value=f"**{score}/100**", inline=True)
        embed.add_field(name="Threat Level", value=f"**{threat}**", inline=True)
        
        if vulnerabilities:
            embed.add_field(name="Issues Found", value="\n".join(vulnerabilities), inline=False)
        else:
            embed.add_field(name="Status", value="✅ All systems operational", inline=False)

        embed.set_footer(text=EMBED_FOOTER)
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

    # ── Voice Moderation ───────────────────────────────────────────

    @app_commands.command(name="voicemute", description="Mute a member in voice channels")
    @app_commands.describe(member="Member to mute", reason="Reason for the mute")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def voicemute_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message(f"{member.mention} is not in a voice channel.", ephemeral=True)
            return
        await member.edit(mute=True, reason=f"{interaction.user}: {reason}")
        embed = EmbedBuilder.security(
            "Member Voice Muted",
            f"**Member:** {member.mention}\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="voiceunmute", description="Unmute a member in voice channels")
    @app_commands.describe(member="Member to unmute")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def voiceunmute_cmd(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await member.edit(mute=False, reason=f"Unmuted by {interaction.user}")
        embed = EmbedBuilder.success(
            "Member Voice Unmuted",
            f"**Member:** {member.mention}\n"
            f"**Moderator:** {interaction.user.mention}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="voicedisconnect", description="Disconnect a member from voice")
    @app_commands.describe(member="Member to disconnect", reason="Reason for disconnect")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def voicedisconnect_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message(f"{member.mention} is not in a voice channel.", ephemeral=True)
            return
        await member.move_to(None, reason=f"{interaction.user}: {reason}")
        embed = EmbedBuilder.security(
            "Member Disconnected",
            f"**Member:** {member.mention}\n"
            f"**Moderator:** {interaction.user.mention}\n"
            f"**Reason:** {reason}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="voicemove", description="Move a member to another voice channel")
    @app_commands.describe(member="Member to move", channel="Target voice channel")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 5)
    async def voicemove_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        channel: discord.VoiceChannel,
    ) -> None:
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message(f"{member.mention} is not in a voice channel.", ephemeral=True)
            return
        await member.move_to(channel, reason=f"Moved by {interaction.user}")
        embed = EmbedBuilder.info(
            "Member Moved",
            f"**Member:** {member.mention}\n"
            f"**Channel:** {channel.mention}\n"
            f"**Moderator:** {interaction.user.mention}",
        )
        await interaction.response.send_message(embed=embed)
        await self._log_action(interaction.guild, embed)

    @app_commands.command(name="voicelock", description="Lock a voice channel (disallow connect)")
    @app_commands.describe(channel="Voice channel to lock (defaults to your current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 5)
    async def voicelock_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel | None = None,
    ) -> None:
        target = channel
        if not target:
            if isinstance(interaction.user, discord.Member) and interaction.user.voice:
                target = interaction.user.voice.channel
            if not target:
                await interaction.response.send_message("Specify a channel or join one first.", ephemeral=True)
                return
        overwrite = target.overwrites_for(target.guild.default_role)
        overwrite.connect = False
        await target.set_permissions(
            target.guild.default_role,
            overwrite=overwrite,
            reason=f"Voice channel locked by {interaction.user}",
        )
        embed = EmbedBuilder.security(
            "Voice Channel Locked",
            f"{target.mention} has been locked.",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="voiceunlock", description="Unlock a voice channel")
    @app_commands.describe(channel="Voice channel to unlock")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 5)
    async def voiceunlock_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel | None = None,
    ) -> None:
        target = channel
        if not target:
            if isinstance(interaction.user, discord.Member) and interaction.user.voice:
                target = interaction.user.voice.channel
            if not target:
                await interaction.response.send_message("Specify a channel or join one first.", ephemeral=True)
                return
        overwrite = target.overwrites_for(target.guild.default_role)
        overwrite.connect = None
        await target.set_permissions(
            target.guild.default_role,
            overwrite=overwrite,
            reason=f"Voice channel unlocked by {interaction.user}",
        )
        embed = EmbedBuilder.success(
            "Voice Channel Unlocked",
            f"{target.mention} has been unlocked.",
        )
        await interaction.response.send_message(embed=embed)

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
