"""Standardised embed builder for ExeGuard."""

from __future__ import annotations

import datetime

import discord

from config import (
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_SECONDARY,
    COLOR_TEXT,
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
        # Terminal-inspired: Minimalistic, often using monochrome or primary colors
        embed = discord.Embed(
            description=f"**{title}**\n\n{description}",
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=EMBED_FOOTER)
        return embed

    @classmethod
    def info(cls, title: str, description: str) -> discord.Embed:
        return cls._base(title, description, COLOR_INFO)

    @classmethod
    def success(cls, title: str, description: str) -> discord.Embed:
        return cls._base(title, description, COLOR_SUCCESS)

    @classmethod
    def warning(cls, title: str, description: str) -> discord.Embed:
        return cls._base(title, description, COLOR_PRIMARY)

    @classmethod
    def error(cls, title: str, description: str) -> discord.Embed:
        return cls._base(title, description, COLOR_DANGER)

    @classmethod
    def security(cls, title: str, description: str) -> discord.Embed:
        # "Thick red left-side indicator bar for security logs"
        # In Discord, this is the color strip on the left.
        return cls._base(title, description, COLOR_DANGER)

    @classmethod
    def log(cls, title: str, description: str) -> discord.Embed:
        return cls._base(title, description, COLOR_SECONDARY)
