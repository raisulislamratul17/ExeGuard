"""Infrastructure Module cog for ExeGuard.

Provides Tickets, Giveaways, VoiceMaster (Dynamic VC),
Reaction Roles, Button Roles, Dropdown Roles, and Leave Messages.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from utils.embed_builder import EmbedBuilder

class Infrastructure(commands.Cog):
    """Tickets, Giveaways, and Dynamic VC systems."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Ticket System ───────────────────────────────────────────────

    ticket_group = app_commands.Group(name="ticket", description="Manage the ticket system")

    @ticket_group.command(name="setup", description="Setup the ticket system")
    @app_commands.describe(category="Category to create tickets in", logs="Channel for ticket logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, category: discord.CategoryChannel, logs: discord.TextChannel) -> None:
        db = self.bot.db # type: ignore
        await db.conn.execute(
            "INSERT OR REPLACE INTO ticket_settings (guild_id, category_id, log_channel, enabled) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, category.id, logs.id, 1)
        )
        await db.conn.commit()
        await interaction.response.send_message("Ticket system setup complete.", ephemeral=True)

    @app_commands.command(name="new", description="Create a new ticket")
    async def ticket_create(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute("SELECT * FROM ticket_settings WHERE guild_id = ?", (interaction.guild_id,)) as cursor:
            settings = await cursor.fetchone()
        
        if not settings or not settings['enabled']:
            await interaction.response.send_message("Ticket system is not enabled.", ephemeral=True)
            return
            
        category = interaction.guild.get_channel(settings['category_id'])
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("Ticket category not found.", ephemeral=True)
            return
            
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )
        
        await db.conn.execute(
            "INSERT INTO tickets (guild_id, user_id, channel_id) VALUES (?, ?, ?)",
            (interaction.guild_id, interaction.user.id, channel.id)
        )
        await db.conn.commit()
        
        embed = EmbedBuilder.info("Ticket Created", f"Hello {interaction.user.mention}, staff will be with you shortly.\nUse `/close` to close this ticket.")
        await channel.send(embed=embed)
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

    @app_commands.command(name="close", description="Close the current ticket channel")
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND guild_id = ? AND status = 'open'",
            (interaction.channel_id, interaction.guild_id),
        ) as cursor:
            ticket = await cursor.fetchone()
        
        if not ticket:
            await interaction.response.send_message("This is not an open ticket channel.", ephemeral=True)
            return

        await db.conn.execute(
            "UPDATE tickets SET status = 'closed' WHERE channel_id = ?",
            (interaction.channel_id,),
        )
        await db.conn.commit()

        embed = EmbedBuilder.info("Ticket Closed", "This ticket will be deleted shortly.")
        await interaction.response.send_message(embed=embed)

        # Send transcript to log channel
        async with db.conn.execute("SELECT * FROM ticket_settings WHERE guild_id = ?", (interaction.guild_id,)) as cursor:
            settings = await cursor.fetchone()
        if settings and settings['log_channel']:
            log_ch = interaction.guild.get_channel(settings['log_channel'])
            if isinstance(log_ch, discord.TextChannel):
                messages = []
                async for msg in interaction.channel.history(limit=100):
                    messages.append(f"[{msg.created_at}] {msg.author.name}: {msg.content}")
                transcript = "\n".join(reversed(messages))[:1900]
                transcript_embed = EmbedBuilder.log(
                    "Ticket Transcript",
                    f"**Ticket by:** <@{ticket['user_id']}>\n"
                    f"**Channel:** {interaction.channel.mention}\n"
                    f"**Closed by:** {interaction.user.mention}\n\n"
                    f"**Messages:**\n{transcript or '*No messages*'}",
                )
                try:
                    await log_ch.send(embed=transcript_embed)
                except discord.HTTPException:
                    pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Ticket closed")
        except discord.HTTPException:
            pass

    # ── VoiceMaster (Dynamic VC) ────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if after.channel:
            db = self.bot.db # type: ignore
            async with db.conn.execute("SELECT * FROM voicemaster_settings WHERE guild_id = ?", (member.guild.id,)) as cursor:
                settings = await cursor.fetchone()
            
            if settings and settings['enabled'] and after.channel.id == settings['channel_id']:
                category = member.guild.get_channel(settings['category_id'])
                if isinstance(category, discord.CategoryChannel):
                    new_channel = await member.guild.create_voice_channel(
                        name=f"{member.name}'s VC",
                        category=category,
                        reason="VoiceMaster: Dynamic VC"
                    )
                    await member.move_to(new_channel)
                    await db.conn.execute(
                        "INSERT INTO voicemaster_channels (channel_id, owner_id, guild_id) VALUES (?, ?, ?)",
                        (new_channel.id, member.id, member.guild.id)
                    )
                    await db.conn.commit()

        if before.channel:
            db = self.bot.db # type: ignore
            async with db.conn.execute("SELECT * FROM voicemaster_channels WHERE channel_id = ?", (before.channel.id,)) as cursor:
                vm_channel = await cursor.fetchone()
            
            if vm_channel and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="VoiceMaster: VC empty")
                except discord.HTTPException:
                    pass
                await db.conn.execute("DELETE FROM voicemaster_channels WHERE channel_id = ?", (before.channel.id,))
                await db.conn.commit()

    @app_commands.command(name="voicemaster", description="Setup VoiceMaster dynamic channels")
    @app_commands.describe(channel="The 'Join to Create' channel", category="Category for dynamic channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def voicemaster_setup(self, interaction: discord.Interaction, channel: discord.VoiceChannel, category: discord.CategoryChannel) -> None:
        db = self.bot.db # type: ignore
        await db.conn.execute(
            "INSERT OR REPLACE INTO voicemaster_settings (guild_id, channel_id, category_id, enabled) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, channel.id, category.id, 1)
        )
        await db.conn.commit()
        await interaction.response.send_message("VoiceMaster setup complete.", ephemeral=True)

    # ── Giveaways ───────────────────────────────────────────────────

    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.describe(duration="Duration (e.g. 1h, 1d)", prize="The prize", winners="Number of winners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_start(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1) -> None:
        from cogs.moderation import parse_duration
        seconds = parse_duration(duration)
        if not seconds:
            await interaction.response.send_message("Invalid duration.", ephemeral=True)
            return
            
        end_time = time.time() + seconds
        embed = EmbedBuilder.info("Giveaway Started!", f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** {discord.utils.format_dt(datetime.fromtimestamp(end_time, timezone.utc), 'R')}\n\nReact with 🎉 to enter!")
        
        await interaction.response.send_message("Giveaway starting...", ephemeral=True)
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎉")
        
        db = self.bot.db # type: ignore
        await db.conn.execute(
            "INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            (message.id, interaction.guild_id, interaction.channel_id, prize, winners, end_time)
        )
        await db.conn.commit()

    @app_commands.command(name="giveaway_end", description="End a giveaway early")
    @app_commands.describe(message_id="Message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND status = 'active'",
            (int(message_id), interaction.guild_id),
        ) as cursor:
            giveaway = await cursor.fetchone()
        
        if not giveaway:
            await interaction.response.send_message("Giveaway not found or already ended.", ephemeral=True)
            return
        
        await db.conn.execute(
            "UPDATE giveaways SET status = 'ended', end_time = ? WHERE message_id = ?",
            (int(time.time()), int(message_id)),
        )
        await db.conn.commit()
        
        await self._pick_giveaway_winners(interaction.guild, giveaway)
        await interaction.response.send_message("Giveaway ended manually.", ephemeral=True)

    @app_commands.command(name="giveaway_reroll", description="Reroll a giveaway winner")
    @app_commands.describe(message_id="Message ID of the ended giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, message_id: str) -> None:
        assert interaction.guild is not None
        channel = interaction.channel
        try:
            msg = await channel.fetch_message(int(message_id))
        except (discord.HTTPException, ValueError):
            await interaction.response.send_message("Message not found.", ephemeral=True)
            return
        
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            await interaction.response.send_message("No reactions found on that message.", ephemeral=True)
            return
        
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            await interaction.response.send_message("No eligible users to reroll.", ephemeral=True)
            return
        
        winner = random.choice(users)
        await interaction.response.send_message(f"🎉 **Reroll!** New winner: {winner.mention}!", ephemeral=False)

    async def _pick_giveaway_winners(self, guild: discord.Guild, giveaway) -> None:
        channel = guild.get_channel(giveaway['channel_id'])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            msg = await channel.fetch_message(giveaway['message_id'])
        except discord.HTTPException:
            return
        
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            return
        
        users = [u async for u in reaction.users() if not u.bot]
        winners_count = min(giveaway['winners'], len(users))
        if not users:
            embed = EmbedBuilder.info("Giveaway Ended", f"**Prize:** {giveaway['prize']}\nNo eligible winners.")
            await channel.send(embed=embed)
            return
        
        import random
        winners = random.sample(users, winners_count)
        mentions = ", ".join(w.mention for w in winners)
        embed = EmbedBuilder.success(
            "Giveaway Ended!",
            f"**Prize:** {giveaway['prize']}\n**Winners:** {mentions}\n\nCongratulations!",
        )
        await channel.send(embed=embed)

    # ── Reaction Roles ──────────────────────────────────────────────

    @app_commands.command(name="reactionrole", description="Add a reaction role to a message")
    @app_commands.describe(message_id="ID of the message", emoji="The emoji to use", role="The role to give")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_add(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role) -> None:
        db = self.bot.db # type: ignore
        await db.conn.execute(
            "INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?, ?, ?, ?)",
            (int(message_id), emoji, role.id, interaction.guild_id)
        )
        await db.conn.commit()
        
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
        except Exception:
            pass
            
        await interaction.response.send_message(f"Reaction role added: {emoji} -> {role.name}", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
            
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (payload.message_id, str(payload.emoji))
        ) as cursor:
            row = await cursor.fetchone()
            
        if row:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild: return
            role = guild.get_role(row['role_id'])
            member = guild.get_member(payload.user_id)
            if role and member:
                try:
                    await member.add_roles(role, reason="Reaction Role")
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
            
        db = self.bot.db # type: ignore
        async with db.conn.execute(
            "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (payload.message_id, str(payload.emoji))
        ) as cursor:
            row = await cursor.fetchone()
            
        if row:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild: return
            role = guild.get_role(row['role_id'])
            member = guild.get_member(payload.user_id)
            if role and member:
                try:
                    await member.remove_roles(role, reason="Reaction Role")
                except discord.HTTPException:
                    pass

    # ── Button Roles ────────────────────────────────────────────────

    @app_commands.command(name="buttonrole", description="Add a button role")
    @app_commands.describe(role="The role to assign", label="Button label", emoji="Optional emoji")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def buttonrole_add(self, interaction: discord.Interaction, role: discord.Role, label: str, emoji: str | None = None) -> None:
        embed = EmbedBuilder.info("Role Buttons", "Click a button to receive the corresponding role.")
        view = discord.ui.View(timeout=None)
        
        style = discord.ButtonStyle.primary
        button = discord.ui.Button(label=label, style=style, emoji=emoji, custom_id=f"br:{role.id}")
        view.add_item(button)
        
        msg = await interaction.channel.send(embed=embed, view=view)
        
        db = self.bot.db # type: ignore
        await db.conn.execute(
            "INSERT OR REPLACE INTO button_roles (guild_id, message_id, role_id, label, emoji, style) VALUES (?, ?, ?, ?, ?, ?)",
            (interaction.guild_id, msg.id, role.id, label, emoji or "", 1),
        )
        await db.conn.commit()
        await interaction.response.send_message(f"Button role created for {role.name}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        if not interaction.data or not interaction.data.get("custom_id", "").startswith("br:"):
            return
        
        role_id = int(interaction.data["custom_id"].split(":")[1])
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Button role removed")
            await interaction.response.send_message(f"Removed {role.name}.", ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason="Button role added")
            await interaction.response.send_message(f"Given {role.name}.", ephemeral=True)

    # ── Dropdown Roles ──────────────────────────────────────────────

    @app_commands.command(name="dropdownrole", description="Create a dropdown role selection")
    @app_commands.describe(roles="Comma-separated role names or IDs", placeholder="Dropdown placeholder text")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def dropdownrole_create(self, interaction: discord.Interaction, roles: str, placeholder: str = "Select a role") -> None:
        assert interaction.guild is not None
        role_names = [r.strip() for r in roles.split(",") if r.strip()]
        role_objects = []
        for name in role_names:
            role = discord.utils.get(interaction.guild.roles, name=name)
            if role and role < interaction.guild.me.top_role:
                role_objects.append(role)
        
        if not role_objects:
            await interaction.response.send_message("No valid roles found. Ensure I have role hierarchy access.", ephemeral=True)
            return

        select = discord.ui.Select(
            placeholder=placeholder,
            options=[
                discord.SelectOption(label=r.name, value=str(r.id), description=f"Get the {r.name} role")
                for r in role_objects[:25]
            ],
        )

        async def select_callback(sel_interaction: discord.Interaction) -> None:
            assert isinstance(sel_interaction.user, discord.Member)
            selected_role_id = int(select.values[0])
            role = sel_interaction.guild.get_role(selected_role_id) if sel_interaction.guild else None
            if not role:
                await sel_interaction.response.send_message("Role not found.", ephemeral=True)
                return
            if role in sel_interaction.user.roles:
                await sel_interaction.user.remove_roles(role, reason="Dropdown role removed")
                await sel_interaction.response.send_message(f"Removed {role.name}.", ephemeral=True)
            else:
                await sel_interaction.user.add_roles(role, reason="Dropdown role added")
                await sel_interaction.response.send_message(f"Given {role.name}.", ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View(timeout=None)
        view.add_item(select)

        embed = EmbedBuilder.info("Role Selection", f"Use the dropdown below to select your roles.\n{placeholder}")
        msg = await interaction.channel.send(embed=embed, view=view)

        db = self.bot.db # type: ignore
        for role in role_objects:
            await db.conn.execute(
                "INSERT OR REPLACE INTO dropdown_roles (guild_id, message_id, role_id, label, description) VALUES (?, ?, ?, ?, ?)",
                (interaction.guild_id, msg.id, role.id, role.name, f"Get the {role.name} role"),
            )
        await db.conn.commit()
        await interaction.response.send_message(f"Dropdown role created with {len(role_objects)} roles.", ephemeral=True)

    # ── Leave Messages ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        db = self.bot.db # type: ignore
        settings = await db.get_guild_settings(member.guild.id)
        leave_ch_id = settings.get("leave_channel")
        leave_enabled = settings.get("leave_enabled", 0)
        leave_msg = settings.get("leave_message", "Goodbye {member.name}! We will miss you.")
        
        if not leave_enabled or not leave_ch_id:
            return
        
        channel = member.guild.get_channel(leave_ch_id)
        if not isinstance(channel, discord.TextChannel):
            return
        
        formatted = leave_msg.replace("{member.name}", member.name).replace("{member.mention}", member.mention).replace("{guild.name}", member.guild.name)
        embed = EmbedBuilder.log("Member Left", formatted)
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @app_commands.command(name="leave", description="Configure leave messages")
    @app_commands.describe(channel="Channel for leave messages", message="Message (use {member.name}, {guild.name})", enabled="Toggle leave messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def leave_config(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str, enabled: bool) -> None:
        assert interaction.guild is not None
        db = self.bot.db # type: ignore
        await db.update_guild_setting(interaction.guild.id, "leave_channel", channel.id)
        await db.update_guild_setting(interaction.guild.id, "leave_message", message)
        await db.update_guild_setting(interaction.guild.id, "leave_enabled", int(enabled))
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"Leave messages {status} in {channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Infrastructure(bot))
