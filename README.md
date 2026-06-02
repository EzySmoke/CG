# CG Discord Bot

## Railway Deployment

Add these variables in Railway → your project → Variables:

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GUILD_ID` | Yes | Server ID (right-click server → Copy Server ID) |
| `ROBLOX_COOKIE` | Yes | Your `.ROBLOSECURITY` Roblox cookie |
| `ROBLOX_MAIN_GROUP_ID` | Yes | Numeric ID of your main Roblox group |
| `ROBLOX_ALLIED_GROUP_IDS` | Recommended | Comma-separated allied group IDs |
| `ROBLOX_ENEMY_GROUP_IDS` | Recommended | Comma-separated enemy group IDs |
| `BLOXLINK_API_KEY` | Yes (for /update) | API key from blox.link/dashboard/developer |

Set the service type to **Worker** in Railway, then deploy.

## First-time Setup

Run `/setup` (Administrator) to configure welcome, log, and comms channels.

## `/update` Role Sync

- Users must be verified with **Bloxlink** in your server
- Their Roblox group rank name must exactly match a Discord role name
- Example: Roblox rank "Shock Company" → Discord role named "Shock Company"

## Background Check Requirements (HICOM only)

`/bgcheck` evaluates users silently. The verdict shows PASSED or FAILED only.
