"""ExeGuard — Futuristic Discord Protection Bot.

Entry point.  Initialises the bot, connects to the database, loads all
cogs, and syncs slash commands on startup.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

from config import BotConfig, COLOR_PRIMARY, EMBED_FOOTER
from database import DatabaseManager

log = logging.getLogger("exeguard")

COGS: list[str] = [
    "cogs.antispam",
    "cogs.antiraid",
    "cogs.antinuke",
    "cogs.moderation",
    "cogs.verification",
    "cogs.logging_cog",
    "cogs.automod",
]


class ExeGuard(commands.Bot):
    """Custom bot subclass that bundles a database handle."""

    def __init__(self, cfg: BotConfig) -> None:
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=cfg.prefix,
            intents=intents,
            owner_ids=set(cfg.owner_ids) if cfg.owner_ids else set(),
        )
        self.cfg = cfg
        self.db = DatabaseManager(cfg.database_path)

    async def setup_hook(self) -> None:
        await self.db.connect()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Loaded cog: %s", cog)
            except Exception:
                log.exception("Failed to load cog: %s", cog)

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        log.info("Connected to %d guilds", len(self.guilds))

        synced = await self.tree.sync()
        log.info("Synced %d slash commands", len(synced))

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | /setup",
        )
        await self.change_presence(
            status=discord.Status.online, activity=activity
        )

        embed = discord.Embed(
            title="\U0001f6e1\ufe0f ExeGuard Online",
            description=(
                "All protection systems active.\n"
                "Use `/setup` to configure your server."
            ),
            color=COLOR_PRIMARY,
        )
        embed.set_footer(text=EMBED_FOOTER)
        for guild in self.guilds:
            settings = await self.db.get_guild_settings(guild.id)
            ch_id = settings.get("log_channel")
            if ch_id:
                ch = guild.get_channel(ch_id)
                if isinstance(ch, discord.TextChannel):
                    try:
                        await ch.send(embed=embed)
                    except discord.HTTPException:
                        pass

    async def close(self) -> None:
        await self.db.close()
        await super().close()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


async def main() -> None:
    _setup_logging()
    cfg = BotConfig()
    if not cfg.token:
        log.critical("DISCORD_TOKEN not set. Create a .env file — see .env.example")
        sys.exit(1)
    bot = ExeGuard(cfg)
    async with bot:
        await bot.start(cfg.token)


if __name__ == "__main__":
    asyncio.run(main())
