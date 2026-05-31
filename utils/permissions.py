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


DANGEROUS_PERMISSIONS = {
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "mention_everyone",
    "manage_nickname",
    "manage_emojis_and_stickers",
    "view_audit_log",
}

STAFF_PERMISSIONS = {
    "kick_members": True,
    "ban_members": True,
    "moderate_members": True,
    "manage_messages": True,
    "view_audit_log": True,
    "manage_threads": True,
    "create_public_threads": True,
    "create_private_threads": True,
    "send_messages": True,
    "read_message_history": True,
    "attach_files": True,
    "embed_links": True,
    "use_external_emojis": True,
    "add_reactions": True,
    "connect": True,
    "speak": True,
}

MEMBER_PERMISSIONS = {
    "send_messages": True,
    "read_message_history": True,
    "attach_files": True,
    "embed_links": True,
    "use_external_emojis": True,
    "add_reactions": True,
    "connect": True,
    "speak": True,
    "use_application_commands": True,
}
