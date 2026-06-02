import discord
from discord import app_commands
from discord.ext import commands
from utils import storage
import aiohttp
import os
import datetime
import asyncio

ACCENT = discord.Color.from_rgb(88, 101, 242)
DANGER = discord.Color.from_rgb(220, 53, 69)

RESTRICTED_EVENTS = ["Patrol", "Wide Patrol"]
RESTRICTED_ROLES  = ["Commander Fox", "Commander Thorn", "Lieutenant Thire"]
ALL_EVENTS = ["Patrol", "Wide Patrol", "Combat Training", "General Training", "Physical Training", "Tryout"]

BLOXLINK_API_KEY = os.getenv("BLOXLINK_API_KEY", "")
MAIN_GROUP_ID    = os.getenv("ROBLOX_MAIN_GROUP_ID", "")

ROBLOX_HEADERS = {
    "Cookie": f".ROBLOSECURITY={os.getenv('ROBLOX_COOKIE', '')}",
    "Content-Type": "application/json",
}

AOS_BANNER = "https://placehold.co/900x150/8B0000/FFFFFF?text=ARREST+ON+SIGHT&font=montserrat"

EVENT_BANNERS = {
    "Patrol":            "https://placehold.co/900x150/1B2A4A/FFFFFF?text=PATROL&font=montserrat",
    "Wide Patrol":       "https://placehold.co/900x150/1B2A4A/FFFFFF?text=WIDE+PATROL&font=montserrat",
    "Combat Training":   "https://placehold.co/900x150/3D0000/FFFFFF?text=COMBAT+TRAINING&font=montserrat",
    "General Training":  "https://placehold.co/900x150/003D0A/FFFFFF?text=GENERAL+TRAINING&font=montserrat",
    "Physical Training": "https://placehold.co/900x150/1A1A3E/FFFFFF?text=PHYSICAL+TRAINING&font=montserrat",
    "Tryout":            "https://placehold.co/900x150/3D2B00/FFFFFF?text=TRYOUT&font=montserrat",
}

AOS_DURATION_CHOICES = [
    app_commands.Choice(name="1 Day",     value="1d"),
    app_commands.Choice(name="3 Days",    value="3d"),
    app_commands.Choice(name="1 Week",    value="1w"),
    app_commands.Choice(name="2 Weeks",   value="2w"),
    app_commands.Choice(name="Permanent", value="perm"),
]
DURATION_LABELS = {"1d": "1 Day", "3d": "3 Days", "1w": "1 Week", "2w": "2 Weeks", "perm": "Permanent"}


def has_restricted_role(member: discord.Member) -> bool:
    return any(r.name in RESTRICTED_ROLES for r in member.roles)


class EventInfoModal(discord.ui.Modal):
    info = discord.ui.TextInput(
        label="Event Information",
        placeholder="Provide any additional details, requirements, or notes for this event…",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=800,
    )

    def __init__(self, event_name: str, link: str, host: discord.Member, channel: discord.TextChannel):
        super().__init__(title=f"Host — {event_name}")
        self.event_name = event_name
        self.link = link
        self.host = host
        self.post_channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Event Log",
            color=ACCENT,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.description = (
            f"Host: {self.host.mention}\n"
            f'Event: "{self.event_name}"'
        )
        embed.add_field(name="Link", value=self.link, inline=False)
        if self.info.value.strip():
            embed.add_field(name="Information", value=self.info.value.strip(), inline=False)
        banner = EVENT_BANNERS.get(self.event_name)
        if banner:
            embed.set_image(url=banner)
        embed.set_footer(text=f"Hosted by {self.host}")

        await self.post_channel.send(embed=embed)
        await interaction.response.send_message(
            f"Event **{self.event_name}** has been posted in {self.post_channel.mention}.",
            ephemeral=True,
        )


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="host", description="Host an event.")
    @app_commands.describe(event="The event to host", link="Link to the event")
    @app_commands.choices(event=[app_commands.Choice(name=e, value=e) for e in ALL_EVENTS])
    async def host(self, interaction: discord.Interaction, event: app_commands.Choice[str], link: str):
        if event.value in RESTRICTED_EVENTS and not has_restricted_role(interaction.user):
            roles_str = ", ".join(f"**{r}**" for r in RESTRICTED_ROLES)
            embed = discord.Embed(
                description=f"Only {roles_str} may host **{event.value}**.",
                color=DANGER,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        cfg = storage.get_setup()
        channel_id = cfg.get("event_log_channel")
        if not channel_id:
            await interaction.response.send_message(
                "No event log channel configured. Use `/setup` first.", ephemeral=True
            )
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Event log channel not found.", ephemeral=True)
            return

        modal = EventInfoModal(
            event_name=event.value,
            link=link,
            host=interaction.user,
            channel=channel,
        )
        await interaction.response.send_modal(modal)

    @app_commands.command(name="update", description="Sync your Roblox group rank to your Discord roles.")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not BLOXLINK_API_KEY:
            await interaction.followup.send(
                "Group sync is not configured. Ask an admin to add the `BLOXLINK_API_KEY` variable.", ephemeral=True
            )
            return

        if not MAIN_GROUP_ID:
            await interaction.followup.send(
                "No main Roblox group configured. Ask an admin to set `ROBLOX_MAIN_GROUP_ID`.", ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        user_id  = interaction.user.id

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.blox.link/v4/public/guilds/{guild_id}/discord-to-roblox/{user_id}",
                headers={"api-key": BLOXLINK_API_KEY},
            ) as r:
                data = await r.json()

            roblox_id = data.get("robloxID")
            if not roblox_id:
                await interaction.followup.send(
                    "Could not find your Roblox account. Make sure you are verified with Bloxlink.", ephemeral=True
                )
                return

            async with session.get(
                f"https://groups.roblox.com/v1/users/{roblox_id}/groups/roles",
                headers=ROBLOX_HEADERS,
            ) as r:
                group_data = await r.json()

        groups = group_data.get("data", [])
        user_group = next((g for g in groups if str(g["group"]["id"]) == MAIN_GROUP_ID), None)

        if not user_group:
            await interaction.followup.send(
                "You are not a member of the main Roblox group.", ephemeral=True
            )
            return

        rank_name = user_group["role"]["name"]

        discord_role = discord.utils.get(interaction.guild.roles, name=rank_name)
        if not discord_role:
            await interaction.followup.send(
                f"Your Roblox rank is **{rank_name}**, but no matching Discord role was found. "
                f"Ask an admin to create a role named **{rank_name}**.", ephemeral=True
            )
            return

        await interaction.user.add_roles(discord_role)

        embed = discord.Embed(
            title="Roles Updated",
            description=f"You have been assigned the **{rank_name}** role.",
            color=ACCENT,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="groupsync", description="Sync your Roblox group rank to Discord roles.")
    async def groupsync(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Use `/update` to sync your Roblox rank to your Discord roles.", ephemeral=True
        )

    @app_commands.command(name="rankcheck", description="Check your current Roblox group rank.")
    async def rankcheck(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Rank Check",
            description=(
                "Use `/bgcheck` with your Roblox username to see your full rank and statistics.\n"
                "Use `/update` to sync your roles if they are out of date."
            ),
            color=ACCENT,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="aos", description="Place a user on Arrest on Sight.")
    @app_commands.describe(roblox_user="Roblox username", reason="Reason for AOS", note="Any additional notes", time="Duration")
    @app_commands.choices(time=AOS_DURATION_CHOICES)
    @app_commands.default_permissions(manage_roles=True)
    async def aos(self, interaction: discord.Interaction, roblox_user: str, reason: str, note: str, time: app_commands.Choice[str]):
        cfg = storage.get_setup()
        channel_id = cfg.get("cg_comms_channel")
        if not channel_id:
            await interaction.response.send_message(
                "No CG Comms channel configured. Use `/setup` first.", ephemeral=True
            )
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("CG Comms channel not found.", ephemeral=True)
            return

        aos_data = storage.get_aos()
        aos_data[roblox_user.lower()] = {
            "reason": reason,
            "note": note,
            "duration": time.value,
            "issued_by": str(interaction.user),
            "issued_at": datetime.datetime.utcnow().isoformat(),
            "active": True,
        }
        storage.save_aos(aos_data)

        embed = discord.Embed(
            title="Arrest on Sight",
            color=DANGER,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_image(url=AOS_BANNER)
        embed.add_field(name="Roblox User", value=roblox_user, inline=True)
        embed.add_field(name="Duration",    value=DURATION_LABELS.get(time.value, time.value), inline=True)
        embed.add_field(name="Reason",      value=reason, inline=False)
        embed.add_field(name="Note",        value=note, inline=False)
        embed.set_footer(text=f"Issued by {interaction.user}")

        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"AOS placed on **{roblox_user}** and posted to {channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="aose", description="End (remove) an Arrest on Sight for a user.")
    @app_commands.describe(roblox_user="Roblox username to remove from AOS", reason="Reason for ending the AOS")
    @app_commands.default_permissions(manage_roles=True)
    async def aose(self, interaction: discord.Interaction, roblox_user: str, reason: str):
        aos_data = storage.get_aos()
        key = roblox_user.lower()

        if key not in aos_data or not aos_data[key].get("active", True):
            await interaction.response.send_message(
                f"**{roblox_user}** does not have an active AOS.", ephemeral=True
            )
            return

        aos_data[key]["active"] = False
        aos_data[key]["ended_by"] = str(interaction.user)
        aos_data[key]["ended_at"] = datetime.datetime.utcnow().isoformat()
        storage.save_aos(aos_data)

        cfg = storage.get_setup()
        channel_id = cfg.get("cg_comms_channel")
        channel = self.bot.get_channel(channel_id) if channel_id else None

        embed = discord.Embed(
            title="AOS Ended",
            description=f"The Arrest on Sight for **{roblox_user}** has been lifted.",
            color=discord.Color.from_rgb(40, 167, 69),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Ended by {interaction.user}")

        if channel:
            await channel.send(embed=embed)
        await interaction.response.send_message(
            f"AOS for **{roblox_user}** has been ended.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
