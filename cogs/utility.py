"""Utility cog for ExeGuard.

Merged from Olympus-Bot. Provides utility features like AFK, 
AutoRole, Welcome messages, and Giveaways.
"""

from __future__ import annotations

import time
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.embed_builder import EmbedBuilder

class Utility(commands.Cog):
    """General utility and server management features."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _format_time(self, seconds: float) -> str:
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds: parts.append(f"{seconds}s")
        return ", ".join(parts) if parts else "0s"

    # ── AFK System ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        db = self.bot.db # type: ignore
        
        # Check if author is returning from AFK
        afk_data = await db.get_afk(message.author.id)
        if afk_data:
            elapsed = time.time() - afk_data['timestamp']
            await db.remove_afk(message.author.id)
            embed = EmbedBuilder.success(
                "Welcome Back!",
                f"You were AFK for **{self._format_time(elapsed)}**.\n"
                f"You received **{afk_data['mentions']}** mentions while you were away."
            )
            await message.channel.send(embed=embed, delete_after=10)

        # Check if anyone mentioned is AFK
        for mention in message.mentions:
            if mention.id == message.author.id:
                continue
            
            target_afk = await db.get_afk(mention.id)
            if target_afk:
                await db.increment_afk_mentions(mention.id)
                elapsed = time.time() - target_afk['timestamp']
                embed = EmbedBuilder.info(
                    "User is AFK",
                    f"**{mention.display_name}** is currently AFK.\n"
                    f"**Reason:** {target_afk['reason']}\n"
                    f"**Since:** {self._format_time(elapsed)} ago"
                )
                await message.channel.send(embed=embed, delete_after=10)

    @app_commands.command(name="afk", description="Set your AFK status")
    @app_commands.describe(reason="The reason for being AFK")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK") -> None:
        db = self.bot.db # type: ignore
        await db.set_afk(interaction.user.id, reason, time.time())
        embed = EmbedBuilder.success(
            "AFK Set",
            f"You are now AFK: **{reason}**\n"
            "Your status will be removed when you send a message."
        )
        await interaction.response.send_message(embed=embed)

    # ── AutoRole System ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        db = self.bot.db # type: ignore
        
        # AutoRole
        roles_ids = await db.get_auto_roles(member.guild.id)
        for role_id in roles_ids:
            role = member.guild.get_role(role_id)
            if role and member.guild.me.guild_permissions.manage_roles:
                try:
                    await member.add_roles(role, reason="ExeGuard: AutoRole")
                except discord.HTTPException:
                    pass

        # Welcome Message
        welcome = await db.get_welcome_settings(member.guild.id)
        if welcome and welcome['enabled'] and welcome['channel_id']:
            channel = member.guild.get_channel(welcome['channel_id'])
            if isinstance(channel, discord.TextChannel):
                msg = welcome['message'] or "Welcome {member.mention} to {guild.name}!"
                formatted_msg = msg.replace("{member.mention}", member.mention).replace("{guild.name}", member.guild.name).replace("{member.name}", member.name)
                
                embed = EmbedBuilder.info("Welcome!", formatted_msg)
                if member.guild.icon:
                    embed.set_thumbnail(url=member.guild.icon.url)
                
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    @app_commands.command(name="autorole", description="Manage roles given to new members automatically")
    @app_commands.describe(action="add or remove", role="The role to manage")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, action: str, role: discord.Role) -> None:
        if action.lower() not in ("add", "remove"):
            await interaction.response.send_message("Action must be `add` or `remove`.", ephemeral=True)
            return

        db = self.bot.db # type: ignore
        if action.lower() == "add":
            await db.add_auto_role(interaction.guild.id, role.id) # type: ignore
            await interaction.response.send_message(f"Added {role.mention} to AutoRoles.", ephemeral=True)
        else:
            await db.remove_auto_role(interaction.guild.id, role.id) # type: ignore
            await interaction.response.send_message(f"Removed {role.mention} from AutoRoles.", ephemeral=True)

    # ── Welcome System ──────────────────────────────────────────────

    @app_commands.command(name="welcome", description="Configure welcome messages")
    @app_commands.describe(channel="Channel for welcome messages", message="Message (use {member.mention}, {guild.name})", enabled="Toggle welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str, enabled: bool) -> None:
        db = self.bot.db # type: ignore
        await db.set_welcome_settings(interaction.guild.id, channel.id, message, int(enabled)) # type: ignore
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"Welcome messages {status} in {channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
