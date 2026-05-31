"""Fun cog for ExeGuard.

Provides entertainment commands like howgay, tharki, slap, hug, and more.
"""

from __future__ import annotations

import random
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands

from utils.embed_builder import EmbedBuilder

class Fun(commands.Cog):
    """Entertainment and social commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def fetch_action_image(self, action: str) -> str | None:
        url = f"https://api.waifu.pics/sfw/{action}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('url')
        except Exception:
            pass
        return None

    @app_commands.command(name="howgay", description="Check someone's gay percentage")
    @app_commands.describe(user="The user to check")
    async def howgay(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        percentage = random.randint(0, 100)
        embed = discord.Embed(
            title="\U0001f308 Gay Meter",
            description=f"**{user.display_name}** is **{percentage}%** gay! \U0001f308",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tharki", description="Check someone's tharki percentage")
    @app_commands.describe(user="The user to check")
    async def tharki(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        percentage = random.randint(0, 100)
        embed = discord.Embed(
            title="\U0001f60f Tharki Meter",
            description=f"**{user.display_name}** is **{percentage}%** tharki! \U0001f60f",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slap", description="Slap a user")
    @app_commands.describe(user="The user to slap")
    async def slap(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        image_url = await self.fetch_action_image("slap")
        embed = discord.Embed(
            description=f"**{interaction.user.display_name}** slapped **{user.display_name}**!",
            color=discord.Color.random()
        )
        if image_url:
            embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hug", description="Hug a user")
    @app_commands.describe(user="The user to hug")
    async def hug(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        image_url = await self.fetch_action_image("hug")
        embed = discord.Embed(
            description=f"**{interaction.user.display_name}** hugged **{user.display_name}**! \u2764\ufe0f",
            color=discord.Color.random()
        )
        if image_url:
            embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pat", description="Pat a user")
    @app_commands.describe(user="The user to pat")
    async def pat(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        image_url = await self.fetch_action_image("pat")
        embed = discord.Embed(
            description=f"**{interaction.user.display_name}** patted **{user.display_name}**!",
            color=discord.Color.random()
        )
        if image_url:
            embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="meme", description="Get a random meme")
    async def meme(self, interaction: discord.Interaction) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(title=data["title"], color=discord.Color.random())
                        embed.set_image(url=data["url"])
                        embed.set_footer(text=f"From r/{data['subreddit']}")
                        await interaction.response.send_message(embed=embed)
                    else:
                        await interaction.response.send_message("Failed to fetch meme.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("An error occurred while fetching the meme.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
