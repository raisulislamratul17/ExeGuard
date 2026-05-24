"""Verification cog for ExeGuard.

Provides button, captcha, and reaction-based verification to gate
new members before they gain full server access.
"""

from __future__ import annotations

import random
import string

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from utils.embed_builder import EmbedBuilder


def _generate_captcha(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Views ───────────────────────────────────────────────────────────


class VerifyButton(View):
    """Simple button verification."""

    def __init__(self, role_id: int) -> None:
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        custom_id="exeguard:verify",
        emoji="\U0001f6e1\ufe0f",
    )
    async def verify(
        self, interaction: discord.Interaction, button: Button[VerifyButton]
    ) -> None:
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message(
                "Verified role not found. Ask an admin to reconfigure.",
                ephemeral=True,
            )
            return
        if role in interaction.user.roles:
            await interaction.response.send_message(
                "You are already verified!", ephemeral=True
            )
            return
        await interaction.user.add_roles(role, reason="ExeGuard verification")
        await interaction.response.send_message(
            "You have been verified! Welcome to the server.", ephemeral=True
        )


class CaptchaModal(discord.ui.Modal, title="Captcha Verification"):
    """Modal that asks users to type a captcha code."""

    answer = discord.ui.TextInput(
        label="Enter the code shown above",
        placeholder="ABC123",
        max_length=10,
    )

    def __init__(self, code: str, role_id: int) -> None:
        super().__init__()
        self.code = code
        self.role_id = role_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        if self.answer.value.upper() != self.code:
            await interaction.response.send_message(
                "Incorrect captcha. Please try again.", ephemeral=True
            )
            return
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message(
                "Verified role not found.", ephemeral=True
            )
            return
        await interaction.user.add_roles(role, reason="ExeGuard captcha passed")
        await interaction.response.send_message(
            "Captcha passed! You are now verified.", ephemeral=True
        )


class CaptchaButton(View):
    """Button that opens a captcha modal."""

    def __init__(self, role_id: int) -> None:
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(
        label="Start Captcha",
        style=discord.ButtonStyle.primary,
        custom_id="exeguard:captcha",
        emoji="\U0001f512",
    )
    async def captcha(
        self, interaction: discord.Interaction, button: Button[CaptchaButton]
    ) -> None:
        code = _generate_captcha()
        await interaction.response.send_modal(CaptchaModal(code, self.role_id))
        await interaction.followup.send(
            f"Your captcha code is: **`{code}`**\nEnter it in the modal.",
            ephemeral=True,
        )


# ── Cog ─────────────────────────────────────────────────────────────


class Verification(commands.Cog):
    """Member verification system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        # Re-register persistent views for every guild with verification on
        for guild in self.bot.guilds:
            settings = await db.get_guild_settings(guild.id)
            role_id = settings.get("verified_role")
            if settings.get("verification") and role_id:
                self.bot.add_view(VerifyButton(role_id))
                self.bot.add_view(CaptchaButton(role_id))

    # ── Slash commands ──────────────────────────────────────────────

    @app_commands.command(
        name="verify",
        description="Send the verification panel to this channel",
    )
    @app_commands.describe(
        method="Verification method: button or captcha",
        role="The role granted on verification",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verify_cmd(
        self,
        interaction: discord.Interaction,
        method: str,
        role: discord.Role,
    ) -> None:
        assert interaction.guild is not None
        method = method.lower()
        if method not in ("button", "captcha"):
            await interaction.response.send_message(
                "Method must be `button` or `captcha`.", ephemeral=True
            )
            return

        db = self.bot.db  # type: ignore[attr-defined]
        await db.update_guild_setting(interaction.guild.id, "verification", 1)
        await db.update_guild_setting(
            interaction.guild.id, "verified_role", role.id
        )

        embed = EmbedBuilder.info(
            "Server Verification",
            "Click the button below to verify yourself and gain access to the server.\n\n"
            "\U0001f6e1\ufe0f **ExeGuard** protects this community.",
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else "")

        view: View
        if method == "captcha":
            view = CaptchaButton(role.id)
        else:
            view = VerifyButton(role.id)

        await interaction.channel.send(embed=embed, view=view)  # type: ignore[union-attr]
        await interaction.response.send_message(
            f"Verification panel sent ({method}).", ephemeral=True
        )

    @app_commands.command(
        name="setup",
        description="Quick setup wizard for ExeGuard",
    )
    @app_commands.describe(
        log_channel="Channel for security logs",
        mod_log_channel="Channel for moderation logs",
        join_log_channel="Channel for join/leave logs",
        verified_role="Role to assign on verification",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_cmd(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        mod_log_channel: discord.TextChannel | None = None,
        join_log_channel: discord.TextChannel | None = None,
        verified_role: discord.Role | None = None,
    ) -> None:
        assert interaction.guild is not None
        db = self.bot.db  # type: ignore[attr-defined]

        if log_channel:
            await db.update_guild_setting(
                interaction.guild.id, "log_channel", log_channel.id
            )
        if mod_log_channel:
            await db.update_guild_setting(
                interaction.guild.id, "mod_log_channel", mod_log_channel.id
            )
        if join_log_channel:
            await db.update_guild_setting(
                interaction.guild.id, "join_log_channel", join_log_channel.id
            )
        if verified_role:
            await db.update_guild_setting(
                interaction.guild.id, "verified_role", verified_role.id
            )
            await db.update_guild_setting(
                interaction.guild.id, "verification", 1
            )

        settings = await db.get_guild_settings(interaction.guild.id)
        log_ch = settings.get("log_channel")
        mod_ch = settings.get("mod_log_channel")
        join_ch = settings.get("join_log_channel")
        v_role = settings.get("verified_role")
        lines = [
            f"**Security Logs:** <#{log_ch}>" if log_ch else "**Security Logs:** Not set",
            f"**Mod Logs:** <#{mod_ch}>" if mod_ch else "**Mod Logs:** Not set",
            f"**Join Logs:** <#{join_ch}>" if join_ch else "**Join Logs:** Not set",
            f"**Verified Role:** <@&{v_role}>" if v_role else "**Verified Role:** Not set",
            f"**Anti-Spam:** {'On' if settings.get('antispam') else 'Off'}",
            f"**Anti-Raid:** {'On' if settings.get('antiraid') else 'Off'}",
            f"**Anti-Nuke:** {'On' if settings.get('antinuke') else 'Off'}",
        ]
        embed = EmbedBuilder.success(
            "ExeGuard Setup Complete", "\n".join(lines)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))
