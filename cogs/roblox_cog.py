import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import datetime

ROBLOX_COOKIE = os.getenv("ROBLOX_COOKIE", "")
MAIN_GROUP_ID = os.getenv("ROBLOX_MAIN_GROUP_ID", "")
ALLIED_GROUP_IDS = [g.strip() for g in os.getenv("ROBLOX_ALLIED_GROUP_IDS", "").split(",") if g.strip()]
ENEMY_GROUP_IDS  = [g.strip() for g in os.getenv("ROBLOX_ENEMY_GROUP_IDS",  "").split(",") if g.strip()]

HEADERS = {
    "Cookie": f".ROBLOSECURITY={ROBLOX_COOKIE}",
    "Content-Type": "application/json",
}

MIN_BADGES    = 175
MIN_FRIENDS   = 20
MIN_FOLLOWING = 10
MIN_AGE_DAYS  = 365


async def roblox_get(session, url):
    async with session.get(url, headers=HEADERS) as r:
        return await r.json()


async def get_user_by_name(session, username):
    async with session.post(
        "https://users.roblox.com/v1/usernames/users",
        json={"usernames": [username], "excludeBannedUsers": False},
        headers=HEADERS,
    ) as r:
        data = await r.json()
        return data["data"][0] if data.get("data") else None


async def get_badge_count(session, user_id):
    total, cursor = 0, ""
    for _ in range(10):
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges?limit=100&sortOrder=Asc"
        if cursor:
            url += f"&cursor={cursor}"
        data = await roblox_get(session, url)
        total += len(data.get("data", []))
        cursor = data.get("nextPageCursor")
        if not cursor:
            break
    return total


async def get_gamepass_count(session, user_id):
    total, cursor = 0, ""
    for _ in range(20):
        url = f"https://inventory.roblox.com/v1/users/{user_id}/assets/gamepasses?limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        data = await roblox_get(session, url)
        total += len(data.get("data", []))
        cursor = data.get("nextPageCursor")
        if not cursor:
            break
    return total


async def get_group_name(session, group_id):
    try:
        data = await roblox_get(session, f"https://groups.roblox.com/v1/groups/{group_id}")
        return data.get("name", f"Group {group_id}")
    except Exception:
        return f"Group {group_id}"


class RobloxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bgcheck", description="Background check a Roblox user.")
    @app_commands.describe(roblox_user="Roblox username to check")
    async def bgcheck(self, interaction: discord.Interaction, roblox_user: str):
        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            user_data = await get_user_by_name(session, roblox_user)
            if not user_data:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Background Check",
                        description=f"No Roblox account found for **{roblox_user}**.",
                        color=discord.Color.from_rgb(220, 53, 69),
                    )
                )
                return

            user_id = user_data["id"]
            info       = await roblox_get(session, f"https://users.roblox.com/v1/users/{user_id}")
            groups_raw = await roblox_get(session, f"https://groups.roblox.com/v1/users/{user_id}/groups/roles")
            friends    = (await roblox_get(session, f"https://friends.roblox.com/v1/users/{user_id}/friends/count")).get("count", 0)
            followers  = (await roblox_get(session, f"https://friends.roblox.com/v1/users/{user_id}/followers/count")).get("count", 0)
            following  = (await roblox_get(session, f"https://friends.roblox.com/v1/users/{user_id}/followings/count")).get("count", 0)
            badges     = await get_badge_count(session, user_id)
            gamepasses = await get_gamepass_count(session, user_id)

            groups = groups_raw.get("data", [])
            user_group_map = {str(g["group"]["id"]): g for g in groups}

            created_raw = info.get("created", "")
            if created_raw:
                created_dt  = datetime.datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                age_days    = (datetime.datetime.now(datetime.timezone.utc) - created_dt).days
                created_str = created_dt.strftime("%B %d, %Y")
                age_str     = f"{age_days} days"
            else:
                age_days, created_str, age_str = 0, "Unknown", "Unknown"

            banned       = info.get("isBanned", False)
            username     = info.get("name", roblox_user)
            display_name = info.get("displayName", roblox_user)
            description  = info.get("description", "").strip() or "None"

            pass_badges    = badges    >= MIN_BADGES
            pass_friends   = friends   >= MIN_FRIENDS
            pass_following = following >= MIN_FOLLOWING
            pass_age       = age_days  >= MIN_AGE_DAYS
            overall_pass   = all([pass_badges, pass_friends, pass_following, pass_age, not banned])

            color = discord.Color.from_rgb(40, 167, 69) if overall_pass else discord.Color.from_rgb(220, 53, 69)

            embed = discord.Embed(
                title=f"Background Check — {username}",
                url=f"https://www.roblox.com/users/{user_id}/profile",
                color=color,
                timestamp=datetime.datetime.utcnow(),
            )

            embed.add_field(
                name="Profile",
                value=(
                    f"**Username:** {username}\n"
                    f"**Display Name:** {display_name}\n"
                    f"**User ID:** {user_id}\n"
                    f"**Banned:** {'Yes' if banned else 'No'}\n"
                    f"**Description:** {description[:200]}"
                ),
                inline=False,
            )

            embed.add_field(
                name="Statistics",
                value="\n".join([
                    f"Badges: **{badges}**",
                    f"Friends: **{friends}**",
                    f"Followers: **{followers}**",
                    f"Following: **{following}**",
                    f"Gamepasses Owned: **{gamepasses}**",
                    f"Account Age: **{age_str}**",
                    f"Account Created: **{created_str}**",
                    f"Total Groups: **{len(groups)}**",
                ]),
                inline=False,
            )

            # Main group
            if MAIN_GROUP_ID and MAIN_GROUP_ID in user_group_map:
                g = user_group_map[MAIN_GROUP_ID]
                main_value = f"**{g['group']['name']}** — {g['role']['name']}"
            else:
                main_value = "-"
            embed.add_field(name="Main Group", value=main_value, inline=False)

            # Allied (divisional) groups — only show ones the user is in
            if ALLIED_GROUP_IDS:
                ally_lines = [
                    f"**{user_group_map[gid]['group']['name']}** — {user_group_map[gid]['role']['name']}"
                    for gid in ALLIED_GROUP_IDS if gid in user_group_map
                ]
                embed.add_field(name="Divisional Groups", value="\n".join(ally_lines) if ally_lines else "-", inline=False)

            # Enemy groups — only show ones the user is actually in
            if ENEMY_GROUP_IDS:
                enemy_lines = [
                    f"**{user_group_map[gid]['group']['name']}** — {user_group_map[gid]['role']['name']}"
                    for gid in ENEMY_GROUP_IDS if gid in user_group_map
                ]
                if enemy_lines:
                    embed.add_field(name="Enemy Groups Detected", value="\n".join(enemy_lines), inline=False)

            embed.add_field(name="Verdict", value="PASSED" if overall_pass else "FAILED", inline=False)
            embed.set_footer(text=f"Requested by {interaction.user}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RobloxCog(bot))
