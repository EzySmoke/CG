import discord
from discord import app_commands
from discord.ext import commands
from utils import storage
import datetime
import asyncio

ACCENT   = discord.Color.from_rgb(88, 101, 242)
SUCCESS  = discord.Color.from_rgb(40, 167, 69)
DANGER   = discord.Color.from_rgb(220, 53, 69)
WARNING  = discord.Color.from_rgb(255, 193, 7)

HICOM_ROLE_NAME = "HICOM"

# user_id → asyncio.Task
active_spam_tasks: dict[int, asyncio.Task] = {}


async def log_action(bot, action: str, moderator: discord.Member, target, reason: str, extra: str = ""):
    cfg = storage.get_setup()
    ch  = bot.get_channel(cfg.get("mod_log_channel", 0))
    if not ch:
        return
    embed = discord.Embed(title=action, color=WARNING, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Target",    value=str(target),                   inline=True)
    embed.add_field(name="Moderator", value=moderator.mention,             inline=True)
    embed.add_field(name="Reason",    value=reason or "No reason provided", inline=False)
    if extra:
        embed.add_field(name="Details", value=extra, inline=False)
    await ch.send(embed=embed)


class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── General ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Latency: **{round(self.bot.latency * 1000)}ms**", color=ACCENT
            )
        )

    @app_commands.command(name="help", description="View all available commands.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Command Reference", color=ACCENT)
        embed.add_field(name="Setup",
            value="`/setup`  `/editsetup`  `/medals`  `/assignmedal`", inline=False)
        embed.add_field(name="Events",
            value="`/host`  `/update`  `/rankcheck`  `/aos`  `/aose`", inline=False)
        embed.add_field(name="Roblox",
            value="`/bgcheck`", inline=False)
        embed.add_field(name="Moderation",
            value=("`/purge`  `/kick`  `/ban`  `/mute`  `/unmute`\n"
                   "`/slowmode`  `/role`  `/promote`  `/demote`\n"
                   "`/loa`  `/blacklist`  `/unblacklist`\n"
                   "`/announce`  `/lockdown`  `/unlockdown`  `/strike`\n"
                   "`/auto-role`  `/massdm`  `/stopdm`"), inline=False)
        embed.add_field(name="Fun",
            value="`/roll`  `/coinflip`  `/8ball`  `/rate`  `/ship`  `/roast`  `/compliment`  `/meme`  `/joke`  `/choose`",
            inline=False)
        embed.add_field(name="Star Wars",
            value="`/order66`  `/goodsoldiersfolloworders`  `/rogerroger`\n"
                  "`/watchthosewristrockets`  `/theattemptonmylife`  `/itsatreasonableprice`  `/hellothere`",
            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Moderation ───────────────────────────────────────────────────────────────

    @app_commands.command(name="purge", description="Delete a number of messages from this channel.")
    @app_commands.describe(amount="Number of messages to delete (1–100)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            embed=discord.Embed(description=f"Deleted **{len(deleted)}** messages.", color=SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(user="User to kick", reason="Reason for the kick")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        await user.kick(reason=reason)
        embed = discord.Embed(title="Kick", color=DANGER)
        embed.add_field(name="User",   value=str(user), inline=True)
        embed.add_field(name="Reason", value=reason,    inline=True)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Kick", interaction.user, user, reason)

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(user="User to ban", reason="Reason for the ban")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        await user.ban(reason=reason)
        embed = discord.Embed(title="Ban", color=DANGER)
        embed.add_field(name="User",   value=str(user), inline=True)
        embed.add_field(name="Reason", value=reason,    inline=True)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Ban", interaction.user, user, reason)

    @app_commands.command(name="mute", description="Timeout (mute) a member.")
    @app_commands.describe(user="User to mute", time="Duration in minutes")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, time: int = 10):
        until = discord.utils.utcnow() + datetime.timedelta(minutes=time)
        await user.timeout(until, reason=f"Muted by {interaction.user}")
        embed = discord.Embed(title="Mute", color=WARNING)
        embed.add_field(name="User",     value=str(user),        inline=True)
        embed.add_field(name="Duration", value=f"{time} minutes", inline=True)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Mute", interaction.user, user, f"Muted for {time} minutes")

    @app_commands.command(name="unmute", description="Remove timeout from a member.")
    @app_commands.describe(user="User to unmute")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        await user.timeout(None)
        embed = discord.Embed(
            title="Unmute", description=f"{user.mention} has been unmuted.", color=SUCCESS
        )
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Unmute", interaction.user, user, "Unmuted")

    @app_commands.command(name="slowmode", description="Set slowmode for the current channel.")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = "Slowmode disabled." if seconds == 0 else f"Slowmode set to **{seconds}** seconds."
        await interaction.response.send_message(embed=discord.Embed(description=msg, color=ACCENT))

    @app_commands.command(name="role", description="Add or remove a role from a user.")
    @app_commands.describe(user="Target user", role="Role to add or remove")
    @app_commands.default_permissions(manage_roles=True)
    async def role(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if role in user.roles:
            await user.remove_roles(role)
            action = "removed from"
        else:
            await user.add_roles(role)
            action = "added to"
        embed = discord.Embed(
            title="Role Update",
            description=f"**{role.name}** {action} {user.mention}.",
            color=ACCENT,
        )
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Role Update", interaction.user, user, f"Role: {role.name}")

    @app_commands.command(name="promote", description="Promote a user to a specific rank/role.")
    @app_commands.describe(user="User to promote", rank="Role to promote to")
    @app_commands.default_permissions(manage_roles=True)
    async def promote(self, interaction: discord.Interaction, user: discord.Member, rank: discord.Role):
        await user.add_roles(rank)
        embed = discord.Embed(title="Promotion", color=SUCCESS)
        embed.add_field(name="User",     value=user.mention, inline=True)
        embed.add_field(name="New Rank", value=rank.name,    inline=True)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Promotion", interaction.user, user, f"Promoted to {rank.name}")

    @app_commands.command(name="demote", description="Demote a user from a specific rank/role.")
    @app_commands.describe(user="User to demote", rank="Role to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def demote(self, interaction: discord.Interaction, user: discord.Member, rank: discord.Role):
        await user.remove_roles(rank)
        embed = discord.Embed(title="Demotion", color=DANGER)
        embed.add_field(name="User",         value=user.mention, inline=True)
        embed.add_field(name="Removed Rank", value=rank.name,    inline=True)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Demotion", interaction.user, user, f"Demoted from {rank.name}")

    @app_commands.command(name="loa", description="Put a user on Leave of Absence.")
    @app_commands.describe(user="User going on LOA", days="Number of days")
    @app_commands.default_permissions(manage_roles=True)
    async def loa(self, interaction: discord.Interaction, user: discord.Member, days: int):
        loa_data = storage.get_loa()
        uid      = str(user.id)
        end_date = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        loa_data[uid] = {"days": days, "end_date": end_date, "approved_by": interaction.user.id}
        storage.save_loa(loa_data)
        embed = discord.Embed(title="Leave of Absence", color=WARNING)
        embed.add_field(name="User",     value=user.mention,  inline=True)
        embed.add_field(name="Duration", value=f"{days} days", inline=True)
        embed.add_field(name="Returns",  value=end_date,      inline=True)
        embed.set_footer(text=f"Approved by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="blacklist", description="Blacklist a user.")
    @app_commands.describe(user="User to blacklist", reason="Reason for blacklist")
    @app_commands.default_permissions(administrator=True)
    async def blacklist(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        bl = storage.get_blacklist()
        bl[str(user.id)] = {"reason": reason, "by": interaction.user.id, "username": str(user)}
        storage.save_blacklist(bl)
        embed = discord.Embed(title="Blacklist", color=DANGER)
        embed.add_field(name="User",   value=user.mention, inline=True)
        embed.add_field(name="Reason", value=reason,       inline=False)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Blacklist", interaction.user, user, reason)

    @app_commands.command(name="unblacklist", description="Remove a user from the blacklist.")
    @app_commands.describe(user="User to unblacklist")
    @app_commands.default_permissions(administrator=True)
    async def unblacklist(self, interaction: discord.Interaction, user: discord.Member):
        bl = storage.get_blacklist()
        if str(user.id) not in bl:
            await interaction.response.send_message(f"**{user}** is not on the blacklist.", ephemeral=True)
            return
        bl.pop(str(user.id))
        storage.save_blacklist(bl)
        embed = discord.Embed(
            title="Unblacklist",
            description=f"{user.mention} has been removed from the blacklist.",
            color=SUCCESS,
        )
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Unblacklist", interaction.user, user, "Removed from blacklist")

    @app_commands.command(name="announce", description="Send an announcement embed.")
    @app_commands.describe(message="The announcement message")
    @app_commands.default_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, message: str):
        embed = discord.Embed(
            title="Announcement",
            description=message,
            color=ACCENT,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text=f"Posted by {interaction.user}")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Announcement sent.", ephemeral=True)

    @app_commands.command(name="lockdown", description="Lock the current channel.")
    @app_commands.describe(reason="Reason for the lockdown")
    @app_commands.default_permissions(manage_channels=True)
    async def lockdown(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="Channel Locked", description=f"Reason: {reason}", color=DANGER)
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, "Lockdown", interaction.user, interaction.channel, reason)

    @app_commands.command(name="unlockdown", description="Unlock the current channel.")
    @app_commands.default_permissions(manage_channels=True)
    async def unlockdown(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(
            title="Channel Unlocked", description="This channel has been unlocked.", color=SUCCESS
        )
        embed.set_footer(text=f"Actioned by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="strike", description="Issue a strike to a user.")
    @app_commands.describe(user="User to strike")
    @app_commands.default_permissions(manage_roles=True)
    async def strike(self, interaction: discord.Interaction, user: discord.Member):
        strikes = storage.get_strikes()
        uid     = str(user.id)
        count   = strikes.get(uid, {}).get("count", 0) + 1
        strikes[uid] = {"count": count, "username": str(user)}
        storage.save_strikes(strikes)
        color = DANGER if count >= 3 else WARNING
        embed = discord.Embed(title=f"Strike {count}", color=color)
        embed.add_field(name="User",          value=user.mention, inline=True)
        embed.add_field(name="Total Strikes", value=str(count),   inline=True)
        embed.set_footer(text=f"Issued by {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, f"Strike ({count})", interaction.user, user, f"Strike {count} issued")

    # ── Auto-Role ────────────────────────────────────────────────────────────────

    @app_commands.command(name="auto-role", description="Set roles to automatically assign when someone joins.")
    @app_commands.describe(
        role="Primary role to auto-assign on join",
        extra_roles="Additional roles — mention them (e.g. @Role1 @Role2) — optional",
    )
    @app_commands.default_permissions(manage_roles=True)
    async def auto_role(self, interaction: discord.Interaction, role: discord.Role, extra_roles: str = ""):
        cfg      = storage.get_setup()
        role_ids = [role.id]

        for mention in extra_roles.split():
            rid = mention.strip("<@&>")
            if rid.isdigit():
                role_ids.append(int(rid))

        cfg["auto_roles"] = role_ids
        storage.save_setup(cfg)

        names = []
        for rid in role_ids:
            r = interaction.guild.get_role(rid)
            names.append(r.name if r else str(rid))

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Auto-Role Configured",
                description=f"New members will automatically receive: **{', '.join(names)}**",
                color=ACCENT,
            )
        )

    # ── Mass DM ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="massdm", description="Privately spam DM a user until stopped by HICOM.")
    @app_commands.describe(user="User to spam DM")
    @app_commands.default_permissions(manage_messages=True)
    async def massdm(self, interaction: discord.Interaction, user: discord.Member):
        if user.id in active_spam_tasks:
            await interaction.response.send_message(
                f"**{user}** is already being spammed. Use `/stopdm` to stop.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Now spam DMing {user.mention} privately. Only a member with **{HICOM_ROLE_NAME}** can stop it with `/stopdm`.",
            ephemeral=True,
        )

        async def spam_loop():
            try:
                while True:
                    try:
                        await user.send("Getting spam pinged for crying out loud.")
                    except discord.Forbidden:
                        # User has DMs disabled — stop silently
                        active_spam_tasks.pop(user.id, None)
                        return
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(spam_loop())
        active_spam_tasks[user.id] = task

    @app_commands.command(name="stopdm", description="Stop spam DMing a user. Requires HICOM role.")
    @app_commands.describe(user="User to stop spamming")
    async def stopdm(self, interaction: discord.Interaction, user: discord.Member):
        hicom = discord.utils.get(interaction.guild.roles, name=HICOM_ROLE_NAME)
        if hicom and hicom not in interaction.user.roles:
            await interaction.response.send_message(
                f"Only members with the **{HICOM_ROLE_NAME}** role can stop spam DMs.", ephemeral=True
            )
            return

        task = active_spam_tasks.pop(user.id, None)
        if not task:
            await interaction.response.send_message(
                f"**{user}** is not currently being spammed.", ephemeral=True
            )
            return

        task.cancel()

        # Notify the target via DM
        try:
            await user.send(
                f"You're lucky that **{interaction.user.display_name}** made me stop spam DMing you."
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Stopped spam DMing {user.mention}.", color=SUCCESS
            )
        )


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
