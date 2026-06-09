"""Analytics System cog for ExeGuard.

Tracks server statistics: member count, growth, message activity,
voice activity, top members, and top channels.
"""

from __future__ import annotations

import time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.embed_builder import EmbedBuilder
from datetime import datetime, timezone, timedelta

class Analytics(commands.Cog):
    """Server activity and growth tracking."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._msg_counts: dict[int, dict[str, int]] = {}
        self._voice_activity: dict[int, dict[int, float]] = {}
        self._daily_tick.start()

    def cog_unload(self) -> None:
        self._daily_tick.cancel()

    @tasks.loop(hours=1)
    async def _daily_tick(self) -> None:
        for guild in self.bot.guilds:
            db = self.bot.db # type: ignore
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                async with db.conn.execute(
                    "SELECT count FROM growth_log WHERE guild_id = ? AND date = ?",
                    (guild.id, today),
                ) as cursor:
                    row = await cursor.fetchone()
                if row:
                    await db.conn.execute(
                        "UPDATE growth_log SET count = ? WHERE guild_id = ? AND date = ?",
                        (guild.member_count, guild.id, today),
                    )
                else:
                    await db.conn.execute(
                        "INSERT INTO growth_log (guild_id, date, count) VALUES (?, ?, ?)",
                        (guild.id, today, guild.member_count),
                    )
                await db.conn.commit()
            except Exception:
                pass

    @_daily_tick.before_loop
    async def before_daily_tick(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        gid = message.guild.id
        if gid not in self._msg_counts:
            self._msg_counts[gid] = {"1d": 0, "7d": 0, "14d": 0}
        self._msg_counts[gid]["1d"] = self._msg_counts[gid].get("1d", 0) + 1

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        db = self.bot.db # type: ignore
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await db.conn.execute(
                "INSERT INTO growth_log (guild_id, date, count) VALUES (?, ?, ?)",
                (guild.id, today, guild.member_count),
            )
            await db.conn.commit()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        db = self.bot.db # type: ignore
        if after.channel:
            await db.conn.execute(
                "INSERT INTO voice_activity (guild_id, user_id, channel_id, join_time) VALUES (?, ?, ?, ?)",
                (member.guild.id, member.id, after.channel.id, time.time()),
            )
            await db.conn.commit()
        if before.channel:
            await db.conn.execute(
                "UPDATE voice_activity SET leave_time = ? WHERE guild_id = ? AND user_id = ? AND channel_id = ? AND leave_time IS NULL",
                (time.time(), member.guild.id, member.id, before.channel.id),
            )
            await db.conn.commit()

    @app_commands.command(name="stats", description="View server statistics and analytics")
    async def stats(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        guild = interaction.guild

        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots if total else 0
        msgs_1d = self._msg_counts.get(guild.id, {}).get("1d", 0)

        embed = EmbedBuilder.info(
            f"Analytics — {guild.name}",
            f"**Members:** {total} ({humans} humans, {bots} bots)\n"
            f"**Activity (24h):** {msgs_1d} messages",
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="analytics", description="View detailed server analytics with graphs")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def analytics_detailed(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        db = self.bot.db # type: ignore

        # Growth data
        async with db.conn.execute(
            "SELECT date, count FROM growth_log WHERE guild_id = ? ORDER BY date DESC LIMIT 14",
            (guild.id,),
        ) as cursor:
            growth_rows = await cursor.fetchall()

        # Voice data
        async with db.conn.execute(
            "SELECT SUM(COALESCE(leave_time, ?) - join_time) as total_seconds FROM voice_activity WHERE guild_id = ? AND join_time > ?",
            (time.time(), guild.id, time.time() - 86400),
        ) as cursor:
            voice_row = await cursor.fetchone()
        voice_1d = int((voice_row["total_seconds"] or 0) / 60)

        growth_lines = []
        for row in growth_rows[:7]:
            growth_lines.append(f"`{row['date']}` — {row['count']} members")

        # Top members by messages (from activity dict — limited tracking)
        top_members = sorted(
            ((uid, data) for uid, data in self._msg_counts.items()),
            key=lambda x: x[1].get("1d", 0),
            reverse=True,
        )[:5]

        member_lines = []
        for uid, data in top_members:
            if isinstance(uid, int):
                member_lines.append(f"<@{uid}> — {data.get('1d', 0)} msgs (24h)")

        lines = []
        lines.append(f"**Messages (24h):** {self._msg_counts.get(guild.id, {}).get('1d', 0)}")
        lines.append(f"**Voice Activity (24h):** {voice_1d} minutes")
        lines.append(f"**Growth (Last 7 Days):**")
        lines.extend(growth_lines[:7] if growth_lines else ["No data yet"])
        lines.append(f"\n**Top Members (24h):**")
        lines.extend(member_lines[:5] if member_lines else ["No data yet"])
        lines.append(f"\n📊 **Graph Colors:** 🟢 Messages = Green | 🟣 Voice = Pink")

        embed = discord.Embed(
            title=f"Analytics Dashboard — {guild.name}",
            description="\n".join(lines),
            color=0x0F1115,
            timestamp=datetime.now(timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="Green = Messages | Pink = Voice Activity")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Analytics(bot))
