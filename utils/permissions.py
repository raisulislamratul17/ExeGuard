"""Permission helper utilities for ExeGuard."""

from __future__ import annotations

import discord


def is_admin(member: discord.Member) -> bool:
    """Return True if the member has Administrator permission."""
    return member.guild_permissions.administrator


def is_moderator(member: discord.Member) -> bool:
    """Return True if the member has moderation-level permissions."""
    perms = member.guild_permissions
    return (
        perms.administrator
        or perms.manage_guild
        or perms.ban_members
        or perms.kick_members
        or perms.manage_messages
    )


def check_permissions(
    member: discord.Member, **perms: bool
) -> list[str]:
    """Return a list of permission names the member is missing."""
    member_perms = member.guild_permissions
    missing: list[str] = []
    for perm, required in perms.items():
        if required and not getattr(member_perms, perm, False):
            missing.append(perm)
    return missing
