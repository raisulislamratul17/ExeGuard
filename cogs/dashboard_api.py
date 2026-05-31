"""Dashboard API Cog for ExeGuard.

Provides a secure REST API running alongside the bot to fetch stats,
read/write guild settings, view warnings, and execute moderator actions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import discord
from aiohttp import web
from discord.ext import commands

from config import COLOR_PRIMARY, EMBED_FOOTER

log = logging.getLogger("exeguard.api")


class DashboardAPI(commands.Cog):
    """Cog running a secure web server exposing REST endpoints for the Next.js dashboard."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        # Start the webserver as a background task
        self.port = int(os.getenv("PORT", 8080))
        self.api_key = os.getenv("DASHBOARD_API_KEY", "")
        if not self.api_key:
            log.warning("DASHBOARD_API_KEY is not set. The API is UNSECURED locally but will reject requests if no key is configured in production.")

        self.bot.loop.create_task(self._start_server())

    def cog_unload(self) -> None:
        """Cleanup webserver on cog unload."""
        if self.runner:
            asyncio.create_task(self._stop_server())

    async def _start_server(self) -> None:
        app = web.Application()

        # Routes setup
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_get("/api/stats", self._handle_stats)
        app.router.add_get("/api/guilds", self._handle_guilds)
        app.router.add_get("/api/guilds/{guild_id}/settings", self._handle_get_settings)
        app.router.add_post("/api/guilds/{guild_id}/settings", self._handle_post_settings)
        app.router.add_get("/api/guilds/{guild_id}/warnings", self._handle_get_warnings)
        app.router.add_post("/api/guilds/{guild_id}/action", self._handle_post_action)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await self.site.start()
        log.info("Dashboard API Server successfully started on port %d", self.port)

    async def _stop_server(self) -> None:
        log.info("Stopping Dashboard API Server...")
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        log.info("Dashboard API Server stopped.")

    # ── Security Middleware Helper ───────────────────────────────────

    def _is_authorized(self, request: web.Request) -> bool:
        if not self.api_key:
            log.error("DASHBOARD_API_KEY is not set — rejecting all API requests")
            return False
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        provided_key = auth_header.split(" ")[1].strip()
        return provided_key == self.api_key

    # ── Routes Handlers ──────────────────────────────────────────────

    async def _handle_index(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "online",
                "service": "ExeGuard Bot API",
                "version": "1.0.0",
                "docs": "/api/stats"
            }
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy"})

    async def _handle_stats(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        stats = {
            "guilds_count": len(self.bot.guilds),
            "members_count": sum(g.member_count for g in self.bot.guilds if g.member_count),
            "latency_ms": round(self.bot.latency * 1000, 1),
            "uptime_seconds": int(uptime_seconds),
            "loaded_cogs": list(self.bot.cogs.keys()),
            "status": "healthy"
        }
        return web.json_response(stats)

    async def _handle_guilds(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        guilds = []
        for guild in self.bot.guilds:
            icon_url = str(guild.icon.url) if guild.icon else None
            guilds.append({
                "id": str(guild.id),
                "name": guild.name,
                "icon_url": icon_url,
                "member_count": guild.member_count
            })
        return web.json_response(guilds)

    async def _handle_get_settings(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        guild_id_str = request.match_info.get("guild_id")
        if not guild_id_str or not guild_id_str.isdigit():
            return web.json_response({"error": "Invalid Guild ID"}, status=400)

        guild_id = int(guild_id_str)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found / Bot not in guild", "guild_in": False}, status=404)

        db = getattr(self.bot, "db", None)
        if not db:
            return web.json_response({"error": "Database not initialized"}, status=500)

        settings = await db.get_guild_settings(guild_id)
        # Convert sqlite row / dict values to friendly formats
        formatted_settings = {k: v for k, v in settings.items()}

        # Build active modules list
        formatted_settings["guild_in"] = True
        formatted_settings["guild_name"] = guild.name
        formatted_settings["guild_icon"] = str(guild.icon.url) if guild.icon else None
        formatted_settings["channels"] = [
            {"id": str(c.id), "name": c.name} for c in guild.text_channels
        ]
        formatted_settings["roles"] = [
            {"id": str(r.id), "name": r.name, "color": hex(r.color.value)} for r in guild.roles if not r.is_default()
        ]

        return web.json_response(formatted_settings)

    async def _handle_post_settings(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        guild_id_str = request.match_info.get("guild_id")
        if not guild_id_str or not guild_id_str.isdigit():
            return web.json_response({"error": "Invalid Guild ID"}, status=400)

        guild_id = int(guild_id_str)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Bot not in guild"}, status=404)

        db = getattr(self.bot, "db", None)
        if not db:
            return web.json_response({"error": "Database not initialized"}, status=500)

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Update specific settings in DB
        updated = []
        for key, value in payload.items():
            if key in db.ALLOWED_COLUMNS:
                # Handle typing conversions
                if key in (
                    "antispam", "antiraid", "antinuke", "verification",
                    "log_channel", "mod_log_channel", "join_log_channel",
                    "verified_role", "spam_threshold", "timeout_duration",
                    "trust_all_bots", "spam_emoji_limit", "spam_mention_limit",
                    "spam_duplicate_threshold", "block_invites", "block_links",
                    "block_user_apps", "bot_protection"
                ):
                    try:
                        value = int(value) if value is not None else None
                    except ValueError:
                        continue
                elif key in ("spam_interval", "spam_caps_ratio", "spam_duplicate_interval"):
                    try:
                        value = float(value) if value is not None else None
                    except ValueError:
                        continue

                await db.update_guild_setting(guild_id, key, value)
                updated.append(key)

        return web.json_response({"status": "success", "updated_keys": updated})

    async def _handle_get_warnings(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        guild_id_str = request.match_info.get("guild_id")
        if not guild_id_str or not guild_id_str.isdigit():
            return web.json_response({"error": "Invalid Guild ID"}, status=400)

        guild_id = int(guild_id_str)
        db = getattr(self.bot, "db", None)
        if not db:
            return web.json_response({"error": "Database not initialized"}, status=500)

        rows = await db.get_warnings(guild_id, 0)
        warnings = []
        for row in rows[:50]:
            member = self.bot.get_user(row["user_id"])
            moderator = self.bot.get_user(row["mod_id"])
            
            warnings.append({
                "id": row["id"],
                "user_id": str(row["user_id"]),
                "username": member.name if member else f"Unknown ({row['user_id']})",
                "mod_id": str(row["mod_id"]),
                "mod_name": moderator.name if moderator else f"Unknown ({row['mod_id']})",
                "reason": row["reason"],
                "timestamp": row["timestamp"]
            })

        return web.json_response(warnings)

    async def _handle_post_action(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "Unauthorized"}, status=401)

        guild_id_str = request.match_info.get("guild_id")
        if not guild_id_str or not guild_id_str.isdigit():
            return web.json_response({"error": "Invalid Guild ID"}, status=400)

        guild_id = int(guild_id_str)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Bot not in guild"}, status=404)

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        action = payload.get("action", "").lower()
        reason = payload.get("reason", "Action initiated from Web Dashboard")

        # ── Action 1: Panic Mode / Lockdown ─────────────────────────
        if action == "panic":
            enabled = bool(payload.get("enabled", True))
            mod_cog = self.bot.get_cog("Moderation")
            antiraid_cog = self.bot.get_cog("AntiRaid")

            if enabled:
                # Trigger lockdown on AntiRaid
                if antiraid_cog and hasattr(antiraid_cog, "_lockdown"):
                    asyncio.create_task(antiraid_cog._lockdown(guild, f"Web Panic: {reason}"))
                    return web.json_response({"status": "success", "message": "Panic lockdown activated across all channels."})
            else:
                # Lift lockdown
                if antiraid_cog and hasattr(antiraid_cog, "_unlockdown"):
                    asyncio.create_task(antiraid_cog._unlockdown(guild))
                    return web.json_response({"status": "success", "message": "Panic lockdown lifted."})
            
            return web.json_response({"error": "Anti-Raid system not loaded"}, status=501)

        # ── Action 2: Kick / Ban / Timeout ──────────────────────────
        user_id_str = payload.get("user_id")
        if not user_id_str or not user_id_str.isdigit():
            return web.json_response({"error": "Invalid User ID required for this action"}, status=400)
        
        user_id = int(user_id_str)
        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return web.json_response({"error": "Member not found in this guild"}, status=404)

        try:
            if action == "kick":
                await member.kick(reason=reason)
                await self.bot.db.log_mod_action(guild_id, user_id, self.bot.user.id, "Kick", reason) # type: ignore
                return web.json_response({"status": "success", "message": f"Successfully kicked {member.name}"})

            elif action == "ban":
                await member.ban(reason=reason)
                await self.bot.db.log_mod_action(guild_id, user_id, self.bot.user.id, "Ban", reason) # type: ignore
                return web.json_response({"status": "success", "message": f"Successfully banned {member.name}"})

            elif action == "timeout":
                duration_mins = int(payload.get("duration", 10))
                duration = discord.utils.utcnow() + timedelta(minutes=duration_mins)
                await member.timeout(duration, reason=reason)
                await self.bot.db.log_mod_action(guild_id, user_id, self.bot.user.id, "Timeout", f"{duration_mins}m: {reason}") # type: ignore
                return web.json_response({"status": "success", "message": f"Successfully timed out {member.name} for {duration_mins} minutes."})

            else:
                return web.json_response({"error": f"Unsupported action: {action}"}, status=400)
        except discord.Forbidden:
            return web.json_response({"error": "Bot lacks permissions to execute this action (role hierarchy or missing permissions)"}, status=403)
        except Exception:
            log.exception("Unhandled error in dashboard API action")
            return web.json_response({"error": "Internal server error"}, status=500)


async def setup(bot: commands.Bot) -> None:
    """Setup function to add DashboardAPI to bot."""
    await bot.add_cog(DashboardAPI(bot))
