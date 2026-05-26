"""Standardised embed builder for ExeGuard."""

from __future__ import annotations

import datetime

import discord

from config import (
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    EMBED_FOOTER,
)


class EmbedBuilder:
    """Factory for consistent, branded Discord embeds."""

    @staticmethod
    def _base(
        title: str,
        description: str,
        color: int,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=EMBED_FOOTER)
        return embed

    @classmethod
    def info(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\U0001f6e1\ufe0f {title}", description, COLOR_INFO)

    @classmethod
    def success(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\u2705 {title}", description, COLOR_SUCCESS)

    @classmethod
    def warning(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\u26a0\ufe0f {title}", description, COLOR_PRIMARY)

    @classmethod
    def error(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\u274c {title}", description, COLOR_DANGER)

    @classmethod
    def security(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\U0001f6a8 {title}", description, COLOR_DANGER)

    @classmethod
    def log(cls, title: str, description: str) -> discord.Embed:
        return cls._base(f"\U0001f4cb {title}", description, COLOR_PRIMARY)
