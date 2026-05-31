# ExeGuard Commands Reference

This document provides a comprehensive list of all commands available in ExeGuard, categorized by their functionality.

## 🛡️ Protection & Security

### Anti-Spam (`/antispam`)
*   **Description:** Configures the real-time anti-spam protection system.
*   **Parameters:**
    *   `enabled`: Toggle anti-spam (True/False).
    *   `threshold`: Number of messages before triggering rapid spam.
    *   `interval`: Tracking interval in seconds.
    *   `timeout`: Timeout duration in seconds on infraction.
    *   `emoji_limit`: Max emojis allowed per message.
    *   `mention_limit`: Max mentions allowed per message.
    *   `caps_ratio`: Caps ratio trigger (0.0 to 1.0).
    *   `block_invites`: Block Discord invite links.
    *   `block_links`: Block all external links.

### Anti-Raid (`/antiraid`)
*   **Description:** Configures the join-flood and raid protection system.
*   **Parameters:**
    *   `enabled`: Toggle anti-raid.
    *   `level`: Protection level (`low`, `medium`, `high`).
    *   `min_age`: Minimum account age in days.

### Anti-Nuke (`/antinuke`)
*   **Description:** Configures protection against destructive staff actions.
*   **Parameters:**
    *   `enabled`: Toggle anti-nuke.
    *   `threshold`: Max actions before being flagged as a nuke attempt.
    *   `trust_all_bots`: Whether to trust all bots in the server.

### External App Blocking (`/blockuserapps`)
*   **Description:** Prevents spam from unauthorized User-Installed Apps and external bots.
*   **Logic:**
    *   1st Offense: 15-minute timeout.
    *   2nd Offense: Permanent ban.

### Role Sanitizer (`/sanitize_role`)
*   **Description:** Instantly cleans a role by applying a safety template and removing malicious permissions.
*   **Templates:**
    *   `staff`: Standard moderation perms (Kick, Ban, Mute). Strips Administrator/Manage Server.
    *   `member`: Basic interaction perms only. Strips all dangerous permissions.
    *   `clear`: Removes all permissions from the role.

### @everyone Hardening (`/secure_everyone`)
*   **Description:** Automatically strips all dangerous permissions (Administrator, Mention Everyone, Manage Server, etc.) from the server's default `@everyone` role.

---

## 🛡️ Anti-Nuke & Role Protection
*   **Protected Roles:** Any modification to roles named `SENTINELS` or `Founder` is blocked unless performed by the **Server Owner**. Unauthorized editors are automatically banned.
*   **Permission Escalation:** Automatically detects and reverts unauthorized permission grants (e.g., someone trying to give themselves Administrator).

## ⚖️ Moderation

### Basic Actions
*   `/ban`: Bans a user from the server.
*   `/unban`: Unbans a user.
*   `/tempban`: Bans a user for a specific duration (e.g., `1h`, `1d`).
*   `/kick`: Kicks a user from the server.
*   `/timeout`: Mutes a user for a specific duration.
*   `/warn`: Issues a formal warning to a user.
*   `/purge`: Deletes a specific number of messages.

### Management
*   `/warnings`: View or manage a user's warning history.
*   `/lock`: Locks the current channel.
*   `/unlock`: Unlocks the current channel.
*   `/panic`: Instantly locks down the entire server.

---

## 🎮 Fun & Games

### Interactive Games
*   `/rps`: Play Rock Paper Scissors (vs AI or user).
*   `/tictactoe`: Play Tic-Tac-Toe with another user.
*   `/wordle`: Play the Wordle word-guessing game.
*   `/twenty48`: Play the 2048 puzzle game.
*   `/chess`: Play Chess with another user.
*   `/connectfour`: Play Connect Four with another user.
*   `/blackjack`: Play a hand of Blackjack.
*   `/slots`: Spin the slot machine (animated GIF).

### Social & Fun
*   `/slap`: Slap a user.
*   `/hug`: Hug a user.
*   `/pat`: Pat a user.
*   `/meme`: Fetch a random meme from Reddit.
*   `/howgay`: Check someone's "gay percentage".
*   `/tharki`: Check someone's "tharki percentage".

---

## 🛠️ Utility & Automation

### Server Management
*   `/setup`: Interactive guide to set up core bot features.
*   `/settings`: View the current server configuration.
*   `/logs`: Set the channel for security and action logs.
*   `/afk`: Set your status as AFK (notifies on mention).
*   `/autorole`: Manage roles given to members automatically upon joining.
*   `/welcome`: Configure automated welcome messages.

### Verification
*   `/verification`: Set up the server entry verification system (Button or Captcha).
