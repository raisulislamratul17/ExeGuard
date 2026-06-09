"""Server Management cog for ExeGuard.

Provides Ownership System, RoleFix System, Security Commands,
and Community System.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from utils.embed_builder import EmbedBuilder
from config import EMBED_FOOTER

class ServerManagement(commands.Cog):
    """Ownership, Role Repair, Security, and Community systems."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Ownership System ────────────────────────────────────────────

    owner_group = app_commands.Group(name="owner", description="Manage extra server owners")

    @owner_group.command(name="add", description="Add an extra owner")
    @app_commands.describe(user="The user to add as extra owner")
    @app_commands.checks.has_permissions(administrator=True)
    async def owner_add(self, interaction: discord.Interaction, user: discord.User) -> None:
        assert interaction.guild is not None
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Only the primary owner can add extra owners.", ephemeral=True)
            return
        
        db = self.bot.db # type: ignore
        await db.conn.execute("INSERT OR IGNORE INTO extra_owners (guild_id, user_id) VALUES (?, ?)", (interaction.guild.id, user.id))
        await db.conn.commit()
        
        embed = EmbedBuilder.success("Extra Owner Added", f"{user.mention} is now an extra owner.")
        await interaction.response.send_message(embed=embed)

    @owner_group.command(name="remove", description="Remove an extra owner")
    @app_commands.describe(user="The user to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def owner_remove(self, interaction: discord.Interaction, user: discord.User) -> None:
        assert interaction.guild is not None
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Only the primary owner can remove extra owners.", ephemeral=True)
            return
        
        db = self.bot.db # type: ignore
        await db.conn.execute("DELETE FROM extra_owners WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, user.id))
        await db.conn.commit()
        
        embed = EmbedBuilder.success("Extra Owner Removed", f"{user.mention} is no longer an extra owner.")
        await interaction.response.send_message(embed=embed)

    @owner_group.command(name="list", description="List all extra owners")
    async def owner_list(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute("SELECT user_id FROM extra_owners WHERE guild_id = ?", (interaction.guild.id,)) as cursor:
            rows = await cursor.fetchall()
        
        owners = [f"<@{row['user_id']}>" for row in rows]
        primary = f"<@{interaction.guild.owner_id}> (Primary)"
        
        embed = EmbedBuilder.info("Server Owners", f"**Primary:** {primary}\n**Extra:** {', '.join(owners) if owners else 'None'}")
        await interaction.response.send_message(embed=embed)

    @owner_group.command(name="transfer", description="Transfer server ownership")
    @app_commands.describe(user="The new owner")
    @app_commands.checks.has_permissions(administrator=True)
    async def owner_transfer(self, interaction: discord.Interaction, user: discord.User) -> None:
        assert interaction.guild is not None
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Only the primary owner can transfer ownership.", ephemeral=True)
            return
        if user.id == interaction.guild.owner_id:
            await interaction.response.send_message("You already own this server.", ephemeral=True)
            return
        member = interaction.guild.get_member(user.id)
        if not member:
            await interaction.response.send_message("That user is not in this server.", ephemeral=True)
            return
        await interaction.guild.edit(owner=member, reason=f"Ownership transferred by {interaction.user}")
        embed = EmbedBuilder.success(
            "Ownership Transferred",
            f"Server ownership has been transferred to {user.mention}.",
        )
        await interaction.response.send_message(embed=embed)

    # ── RoleFix System ──────────────────────────────────────────────

    rolefix_group = app_commands.Group(name="rolefix", description="Scan and repair missing essential roles")

    ROLES_BY_TEMPLATE = {
        "community": ["Verified", "Moderator", "Muted", "Bot", "Staff", "Member"],
        "security": ["Verified", "Moderator", "Muted", "Bot", "Admin", "Security"],
        "gaming": ["Verified", "Moderator", "Muted", "Bot", "Gamer", "VIP"],
        "business": ["Verified", "Moderator", "Muted", "Bot", "Employee", "Manager"],
        "development": ["Verified", "Moderator", "Muted", "Bot", "Dev", "Contributor"],
    }

    @rolefix_group.command(name="scan", description="Scan for missing essential roles")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolefix_scan(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await interaction.response.defer()
        
        missing = []
        found = []
        
        roles_to_check = ["Verified", "Moderator", "Muted", "Bot", "Staff"]
        for r_name in roles_to_check:
            role = discord.utils.get(interaction.guild.roles, name=r_name)
            if not role:
                missing.append(r_name)
            else:
                found.append(r_name)
        
        if not missing:
            await interaction.followup.send(embed=EmbedBuilder.success("RoleFix Scan", "All essential roles are present."))
            return
            
        embed = EmbedBuilder.warning("RoleFix Scan", f"**Found:** {', '.join(found) if found else 'None'}\n**Missing:** {', '.join(missing)}")
        await interaction.followup.send(embed=embed)

    @rolefix_group.command(name="template", description="Apply a role template to the server")
    @app_commands.describe(template="Template name: community, security, gaming, business, development")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolefix_template(self, interaction: discord.Interaction, template: str) -> None:
        assert interaction.guild is not None
        template = template.lower()
        if template not in self.ROLES_BY_TEMPLATE:
            names = ", ".join(f"`{t}`" for t in self.ROLES_BY_TEMPLATE)
            await interaction.response.send_message(f"Invalid template. Choose: {names}", ephemeral=True)
            return
        
        await interaction.response.defer()
        created = []
        existed = []
        for r_name in self.ROLES_BY_TEMPLATE[template]:
            role = discord.utils.get(interaction.guild.roles, name=r_name)
            if not role:
                try:
                    role = await interaction.guild.create_role(name=r_name, reason=f"ExeGuard: {template} template")
                    created.append(r_name)
                except discord.HTTPException:
                    pass
            else:
                existed.append(r_name)
        
        embed = EmbedBuilder.success(
            f"RoleFix Template Applied — {template.title()}",
            f"**Created ({len(created)}):** {', '.join(created) if created else 'None'}\n"
            f"**Already existed ({len(existed)}):** {', '.join(existed) if existed else 'None'}",
        )
        await interaction.followup.send(embed=embed)

    # ── Security Commands ───────────────────────────────────────────

    security_group = app_commands.Group(name="security", description="Advanced security settings")

    @security_group.command(name="dangerous_invites", description="Toggle blocking of dangerous invite links")
    @app_commands.describe(enabled="Enable/disable dangerous invite blocking")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def security_dangerous_invites(self, interaction: discord.Interaction, enabled: bool) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        await db.update_guild_setting(interaction.guild.id, "block_dangerous_invites", int(enabled))
        embed = EmbedBuilder.info(
            "Dangerous Invite Protection",
            f"Blocking of dangerous invite links is now **{'enabled' if enabled else 'disabled'}**.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @security_group.command(name="safe_onboarding", description="Toggle safe onboarding mode")
    @app_commands.describe(enabled="Enable/disable safe onboarding")
    @app_commands.checks.has_permissions(administrator=True)
    async def security_safe_onboarding(self, interaction: discord.Interaction, enabled: bool) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        await db.update_guild_setting(interaction.guild.id, "safe_onboarding", int(enabled))
        embed = EmbedBuilder.info(
            "Safe Onboarding",
            f"Safe onboarding is now **{'enabled' if enabled else 'disabled'}**.\n"
            "New members will be protected by strict defaults.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @security_group.command(name="scan", description="Scan for dangerous permissions across all roles")
    @app_commands.checks.has_permissions(administrator=True)
    async def security_scan(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        
        dangerous_perms = {
            "administrator": "Administrator",
            "manage_guild": "Manage Server",
            "manage_roles": "Manage Roles",
            "manage_channels": "Manage Channels",
            "manage_webhooks": "Manage Webhooks",
            "mention_everyone": "Mention @everyone",
            "manage_emojis_and_stickers": "Manage Emojis",
            "view_audit_log": "View Audit Log",
        }
        
        issues = []
        for role in interaction.guild.roles:
            if role.is_default() or role.is_premium_subscriber():
                continue
            for perm_key, perm_name in dangerous_perms.items():
                if getattr(role.permissions, perm_key, False):
                    issues.append(f"@{role.name} — {perm_name}")
        
        if not issues:
            embed = EmbedBuilder.success(
                "Permission Scan Complete",
                "No dangerous permissions found outside of default/integration roles.",
            )
        else:
            limit = 20
            desc = "\n".join(issues[:limit])
            if len(issues) > limit:
                desc += f"\n... and {len(issues) - limit} more"
            embed = EmbedBuilder.warning(
                f"Dangerous Permissions Found ({len(issues)})",
                desc,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="secure_everyone", description="Strip dangerous permissions from @everyone role")
    @app_commands.checks.has_permissions(administrator=True)
    async def secure_everyone(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        everyone = interaction.guild.default_role
        dangerous = ["administrator", "manage_guild", "mention_everyone", "manage_roles", "manage_channels", "manage_webhooks"]
        perms = everyone.permissions
        changed = []
        for perm in dangerous:
            if getattr(perms, perm, False):
                setattr(perms, perm, False)
                changed.append(perm)
        if changed:
            await everyone.edit(permissions=perms, reason="ExeGuard: @everyone hardening")
            embed = EmbedBuilder.success(
                "@everyone Hardened",
                f"Stripped {len(changed)} dangerous permissions:\n" + "\n".join(f"`{p}`" for p in changed),
            )
        else:
            embed = EmbedBuilder.info("@everyone Hardened", "@everyone role is already safe.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Bypass Role System ─────────────────────────────────────────

    @app_commands.command(name="bypassrole", description="Set a role that bypasses all protections")
    @app_commands.describe(role="Role to bypass protections (leave empty to disable)")
    @app_commands.checks.has_permissions(administrator=True)
    async def bypassrole(self, interaction: discord.Interaction, role: discord.Role | None = None) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        role_id = role.id if role else None
        await db.update_guild_setting(interaction.guild.id, "bypass_role", role_id)
        if role:
            embed = EmbedBuilder.success(
                "Bypass Role Set",
                f"{role.mention} now bypasses all ExeGuard protections.\n"
                "Members with this role can send invites, links, NSFW content, and are exempt from anti-spam, anti-raid, and anti-nuke.",
            )
        else:
            embed = EmbedBuilder.info("Bypass Role Disabled", "No role bypasses protections anymore.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Community System ────────────────────────────────────────────

    @app_commands.command(name="community", description="View server community features and boost level benefits")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def community_info(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        guild = interaction.guild
        boost = guild.premium_tier

        features = {
            "Vanity URL": guild.vanity_url_code is not None or boost >= 3,
            "Invite Splash": guild.splash is not None or boost >= 1,
            "Animated Banner": guild.banner is not None or boost >= 2,
            "Role Icons": boost >= 2,
            "Community Mode": "COMMUNITY" in guild.features,
            "Stage Channels": "COMMUNITY" in guild.features,
        }
        media = {
            "720p 60FPS": boost >= 1,
            "1080p 60FPS": boost >= 2,
            "128kbps Audio": boost >= 1,
            "256kbps Audio": boost >= 2,
            "384kbps Audio": boost >= 3,
        }
        stage = {
            "50 Viewer Support": boost >= 1,
            "150 Viewer Support": boost >= 2,
            "300 Viewer Support": boost >= 3,
        }

        lines = [f"**Boost Tier:** {boost}"]

        lines.append("\n**Server Features:**")
        for name, available in features.items():
            lines.append(f"{'✅' if available else '❌'} {name}")

        lines.append("\n**Media Features:**")
        for name, available in media.items():
            lines.append(f"{'✅' if available else '❌'} {name}")

        lines.append("\n**Stage Channels:**")
        for name, available in stage.items():
            lines.append(f"{'✅' if available else '❌'} {name}")

        if guild.vanity_url_code:
            lines.append(f"\n**Vanity URL:** https://discord.gg/{guild.vanity_url_code}")

        embed = discord.Embed(
            title=f"Community Features — {guild.name}",
            description="\n".join(lines),
            color=0x0F1115,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=EMBED_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerManagement(bot))
