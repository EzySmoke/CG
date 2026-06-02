import discord
from discord.ext import commands
from utils import storage

CORUSCANT_GUARD_GIF = "https://media.tenor.com/w4Z0YGKF-9MAAAAC/coruscant-guard-star-wars.gif"
ACCENT = discord.Color.from_rgb(88, 101, 242)


def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = storage.get_setup()

        # Welcome message
        channel_id = cfg.get("welcome_channel")
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"Welcome to {member.guild.name}",
                    description=(
                        f"Hello, {member.mention}! Welcome to **{member.guild.name}**.\n"
                        f"You are our **{ordinal(member.guild.member_count)}** member to join."
                    ),
                    color=ACCENT,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_image(url=CORUSCANT_GUARD_GIF)
                embed.set_footer(text="Coruscant Guard — Protecting the Republic")
                await channel.send(embed=embed)

        # Auto-role assignment
        auto_role_ids = cfg.get("auto_roles", [])
        if auto_role_ids:
            roles_to_add = []
            for rid in auto_role_ids:
                role = member.guild.get_role(rid)
                if role:
                    roles_to_add.append(role)
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="Auto-role on join")
                except discord.Forbidden:
                    pass


async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
