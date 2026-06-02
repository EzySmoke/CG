import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils import storage
from utils.image_gen import make_banner
import aiohttp
import os
import datetime
import asyncio

ACCENT  = discord.Color.from_rgb(88, 101, 242)
DANGER  = discord.Color.from_rgb(220, 53, 69)
SUCCESS = discord.Color.from_rgb(40, 167, 69)

RESTRICTED_EVENTS = ["Patrol", "Wide Patrol"]
RESTRICTED_ROLES  = ["Commander Fox", "Commander Thorn", "Lieutenant Thire"]
ALL_EVENTS = ["Patrol", "Wide Patrol", "Combat Training", "General Training", "Physical Training", "Tryout"]

BLOXLINK_API_KEY = os.getenv("BLOXLINK_API_KEY", "")
MAIN_GROUP_ID    = os.getenv("ROBLOX_MAIN_GROUP_ID", "")
ROBLOX_HEADERS   = {
    "Cookie": f".ROBLOSECURITY={os.getenv('ROBLOX_COOKIE', '')}",
    "Content-Type": "application/json",
}

EVENT_COLORS = {
    "Patrol":            (27,  42,  74),
    "Wide Patrol":       (27,  42,  74),
    "Combat Training":   (61,   0,   0),
    "General Training":  (0,   61,  10),
    "Physical Training": (26,  26,  62),
    "Tryout":            (61,  43,   0),
}

AOS_DURATION_CHOICES = [
    app_commands.Choice(name="1 Day",     value="1d"),
    app_commands.Choice(name="3 Days",    value="3d"),
    app_commands.Choice(name="1 Week",    value="1w"),
    app_commands.Choice(name="2 Weeks",   value="2w"),
    app_commands.Choice(name="Permanent", value="perm"),
]
DURATION_LABELS = {"1d": "1 Day", "3d": "3 Days", "1w": "1 Week", "2w": "2 Weeks", "perm": "Permanent"}
DURATION_SECONDS = {"1d": 86400, "3d": 259200, "1w": 604800, "2w": 1209600, "perm": None}


def has_restricted_role(member: discord.Member) -> bool:
    return any(r.name in RESTRICTED_ROLES for r in member.roles)


class EventInfoModal(discord.ui.Modal):
    info = discord.ui.TextInput(
        label="Event Information",
        placeholder="Provide any additional details, requirements, or notes for attendees…",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=800,
    )

    def __init__(self, event_name: str, link: str, host: discord.Member, channel: discord.TextChannel):
        super().__init__(title=f"Host — {event_name}")
        self.event_name = event_name
        self.link       = link
        self.host       = host
        self.post_ch    = channel

    async def on_submit(self, interaction: discord.Interaction):
        bg = EVENT_COLORS.get(self.event_name, (30, 30, 50))
        buf  = make_banner(self.event_name.upper(), bg=bg, font_size=60)
        file = discord.File(buf, filename="event_banner.png")

        embed = discord.Embed(
            title="Event Hosted",
            color=ACCENT,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.description = (
            f"**Host:** {self.host.mention}\n"
            f"**Event:** {self.event_name}"
        )
        embed.add_field(name="Link", value=self.link, inline=False)
        if self.info.value.strip():
            embed.add_field(name="Information", value=self.info.value.strip(), inline=False)
        embed.set_image(url="attachment://event_banner.png")
        embed.set_footer(text=f"Hosted by {self.host}")

        await self.post_ch.send(embed=embed, file=file)
        await interaction.response.send_message(
            f"Event **{self.event_name}** posted to {self.post_ch.mention}.", ephemeral=True
        )


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.aos_expiry_task.start()

    def cog_unload(self):
        self.aos_expiry_task.cancel()

    # ── AOS expiry background task ──────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def aos_expiry_task(self):
        aos_data = storage.get_aos()
        changed  = False
        now      = datetime.datetime.utcnow()

        for key, entry in list(aos_data.items()):
            if not entry.get("active", True):
                continue
            duration = entry.get("duration", "perm")
            if duration == "perm":
                continue

            secs = DURATION_SECONDS.get(duration)
            if not secs:
                continue

            issued_at  = datetime.datetime.fromisoformat(entry["issued_at"])
            expires_at = issued_at + datetime.timedelta(seconds=secs)
            if now < expires_at:
                continue

            entry["active"]     = False
            entry["expired"]    = True
            entry["expired_at"] = now.isoformat()
            changed = True

            channel_id = entry.get("channel_id")
            message_id = entry.get("message_id")
            if channel_id and message_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        original = await channel.fetch_message(message_id)
                        buf  = make_banner("AOS EXPIRED")
                        file = discord.File(buf, filename="aos_expired.png")
                        embed = discord.Embed(
                            title="AOS Expired",
                            description="This Arrest on Sight has ended.",
                            color=DANGER,
                            timestamp=now,
                        )
                        embed.add_field(name="Subject", value=key.title(), inline=True)
                        embed.set_image(url="attachment://aos_expired.png")
                        await original.reply(embed=embed, file=file)
                    except Exception:
                        pass

        if changed:
            storage.save_aos(aos_data)

    @aos_expiry_task.before_loop
    async def before_expiry_task(self):
        await self.bot.wait_until_ready()

    # ── /host ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="host", description="Host an event.")
    @app_commands.describe(event="Event to host", link="Link to the event")
    @app_commands.choices(event=[app_commands.Choice(name=e, value=e) for e in ALL_EVENTS])
    async def host(self, interaction: discord.Interaction, event: app_commands.Choice[str], link: str):
        if event.value in RESTRICTED_EVENTS and not has_restricted_role(interaction.user):
            roles_str = ", ".join(f"**{r}**" for r in RESTRICTED_ROLES)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Only {roles_str} may host **{event.value}**.", color=DANGER
                ),
                ephemeral=True,
            )
            return

        cfg = storage.get_setup()
        ch_id = cfg.get("event_log_channel")
        if not ch_id:
            await interaction.response.send_message(
                "No event log channel configured. Use `/setup` first.", ephemeral=True
            )
            return

        channel = self.bot.get_channel(ch_id)
        if not channel:
            await interaction.response.send_message("Event log channel not found.", ephemeral=True)
            return

        await interaction.response.send_modal(
            EventInfoModal(event_name=event.value, link=link, host=interaction.user, channel=channel)
        )

    # ── /update ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="update", description="Sync your Roblox group rank to your Discord roles.")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not BLOXLINK_API_KEY:
            await interaction.followup.send(
                "Group sync is not configured. Ask an admin to add `BLOXLINK_API_KEY`.", ephemeral=True
            )
            return
        if not MAIN_GROUP_ID:
            await interaction.followup.send(
                "No main Roblox group configured. Ask an admin to set `ROBLOX_MAIN_GROUP_ID`.", ephemeral=True
            )
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.blox.link/v4/public/guilds/{interaction.guild_id}/discord-to-roblox/{interaction.user.id}",
                headers={"api-key": BLOXLINK_API_KEY},
            ) as r:
                bl_data = await r.json()

            roblox_id = bl_data.get("robloxID")
            if not roblox_id:
                await interaction.followup.send(
                    "Your Roblox account was not found. Verify with Bloxlink first.", ephemeral=True
                )
                return

            async with session.get(
                f"https://groups.roblox.com/v1/users/{roblox_id}/groups/roles",
                headers=ROBLOX_HEADERS,
            ) as r:
                group_data = await r.json()

        groups     = group_data.get("data", [])
        user_group = next((g for g in groups if str(g["group"]["id"]) == MAIN_GROUP_ID), None)

        if not user_group:
            await interaction.followup.send("You are not a member of the main Roblox group.", ephemeral=True)
            return

        rank_name    = user_group["role"]["name"]
        discord_role = discord.utils.get(interaction.guild.roles, name=rank_name)

        if not discord_role:
            await interaction.followup.send(
                f"Your Roblox rank is **{rank_name}** but no matching Discord role exists. "
                f"Ask an admin to create a role named **{rank_name}**.", ephemeral=True
            )
            return

        await interaction.user.add_roles(discord_role)
        await interaction.followup.send(
            embed=discord.Embed(
                title="Roles Updated",
                description=f"You have been assigned **{rank_name}**.",
                color=ACCENT,
            ),
            ephemeral=True,
        )

    # ── /aos ────────────────────────────────────────────────────────────────────

    @app_commands.command(name="aos", description="Place a user on Arrest on Sight.")
    @app_commands.describe(
        roblox_user="Roblox username",
        reason="Reason for AOS",
        note="Additional notes",
        time="Duration",
    )
    @app_commands.choices(time=AOS_DURATION_CHOICES)
    @app_commands.default_permissions(manage_roles=True)
    async def aos(
        self,
        interaction: discord.Interaction,
        roblox_user: str,
        reason: str,
        note: str,
        time: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)

        cfg = storage.get_setup()
        ch_id = cfg.get("cg_comms_channel")
        if not ch_id:
            await interaction.followup.send(
                "No CG Comms channel configured. Use `/setup` first.", ephemeral=True
            )
            return

        channel = self.bot.get_channel(ch_id)
        if not channel:
            await interaction.followup.send("CG Comms channel not found.", ephemeral=True)
            return

        buf  = make_banner("ARREST ON SIGHT", font_size=58)
        file = discord.File(buf, filename="aos_banner.png")

        embed = discord.Embed(
            title="Arrest on Sight",
            color=DANGER,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_image(url="attachment://aos_banner.png")
        embed.add_field(name="Roblox User", value=roblox_user, inline=True)
        embed.add_field(name="Duration",    value=DURATION_LABELS.get(time.value, time.value), inline=True)
        embed.add_field(name="Reason",      value=reason, inline=False)
        embed.add_field(name="Note",        value=note,   inline=False)
        embed.set_footer(text=f"Issued by {interaction.user}")

        msg = await channel.send(embed=embed, file=file)

        aos_data = storage.get_aos()
        aos_data[roblox_user.lower()] = {
            "reason":     reason,
            "note":       note,
            "duration":   time.value,
            "issued_by":  str(interaction.user),
            "issued_at":  datetime.datetime.utcnow().isoformat(),
            "active":     True,
            "message_id": msg.id,
            "channel_id": ch_id,
        }
        storage.save_aos(aos_data)

        await interaction.followup.send(
            f"AOS placed on **{roblox_user}** and posted to {channel.mention}.", ephemeral=True
        )

    # ── /aose ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="aose", description="End (remove) an Arrest on Sight.")
    @app_commands.describe(roblox_user="Roblox username to clear from AOS", reason="Reason for ending the AOS")
    @app_commands.default_permissions(manage_roles=True)
    async def aose(self, interaction: discord.Interaction, roblox_user: str, reason: str):
        await interaction.response.defer(ephemeral=True)

        aos_data = storage.get_aos()
        key      = roblox_user.lower()

        if key not in aos_data or not aos_data[key].get("active", True):
            await interaction.followup.send(
                f"**{roblox_user}** does not have an active AOS.", ephemeral=True
            )
            return

        entry = aos_data[key]
        entry["active"]   = False
        entry["ended_by"] = str(interaction.user)
        entry["ended_at"] = datetime.datetime.utcnow().isoformat()
        storage.save_aos(aos_data)

        buf  = make_banner("AOS ENDED", font_size=64)
        file = discord.File(buf, filename="aos_ended.png")

        embed = discord.Embed(
            title="AOS Ended",
            description=f"The Arrest on Sight for **{roblox_user}** has been lifted.",
            color=SUCCESS,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_image(url="attachment://aos_ended.png")
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Ended by {interaction.user}")

        channel_id = entry.get("channel_id")
        message_id = entry.get("message_id")

        if channel_id and message_id:
            ch = self.bot.get_channel(channel_id)
            if ch:
                try:
                    original = await ch.fetch_message(message_id)
                    await original.reply(embed=embed, file=file)
                    await interaction.followup.send(
                        f"AOS for **{roblox_user}** ended — replied to the original AOS.", ephemeral=True
                    )
                    return
                except discord.NotFound:
                    await ch.send(embed=embed, file=file)
                    await interaction.followup.send(
                        f"AOS for **{roblox_user}** ended (original message was deleted).", ephemeral=True
                    )
                    return

        cfg = storage.get_setup()
        fallback_id = cfg.get("cg_comms_channel")
        if fallback_id:
            fallback = self.bot.get_channel(fallback_id)
            if fallback:
                await fallback.send(embed=embed, file=file)

        await interaction.followup.send(f"AOS for **{roblox_user}** has been ended.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
