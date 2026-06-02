# CG Discord Bot

## Railway Deployment

Add these variables in Railway → your project → Variables:

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GUILD_ID` | Yes | Server ID (right-click server icon → Copy Server ID) |
| `ROBLOX_COOKIE` | Yes | Your `.ROBLOSECURITY` Roblox cookie |
| `ROBLOX_MAIN_GROUP_ID` | Yes | Numeric ID of your main Roblox group |
| `ROBLOX_ALLIED_GROUP_IDS` | Recommended | Comma-separated allied group IDs |
| `ROBLOX_ENEMY_GROUP_IDS` | Recommended | Comma-separated enemy group IDs |
| `BLOXLINK_API_KEY` | Yes (for /update) | API key from blox.link/dashboard/developer |

Set the service type to **Worker** in Railway, then deploy.

## First-time Setup

Run `/setup` (Administrator only) to configure welcome, log, and comms channels.

## AOS System

- `/aos <roblox_user> <reason> <note> <time>` — posts a red **Arrest on Sight** banner (generated image) to your CG Comms channel
- `/aose <roblox_user> <reason>` — **replies directly to the original AOS message** with a red AOS ENDED banner
- When an AOS duration expires, the bot automatically **replies to the original AOS message** with a red AOS EXPIRED banner

## /update Role Sync

- Users must be verified with **Bloxlink** in your server
- Their Roblox group rank name must exactly match a Discord role name
- Example: Roblox rank "Shock Company" → Discord role named "Shock Company"

## /massdm and /stopdm

- `/massdm <user>` — privately spam DMs the target user
- `/stopdm <user>` — HICOM role required; stops the spam and sends the user a final DM naming who stopped it
