import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from utils import storage
import datetime

ACCENT  = discord.Color.from_rgb(88, 101, 242)
SUCCESS = discord.Color.from_rgb(40, 167, 69)
DANGER  = discord.Color.from_rgb(220, 53, 69)
WARNING = discord.Color.from_rgb(255, 193, 7)

GUARD_ROLE_ID   = 1493681227532730501
CLEAR_ROLE_ID   = 1511493440041652224
WARN_EXPIRY_HRS = 1


def _has_guard_role(interaction: discord.Interaction) -> bool:
    return any(r.id == GUARD_ROLE_ID for r in interaction.user.roles)


def _has_clear_role(interaction: discord.Interaction) -> bool:
    return any(r.id == CLEAR_ROLE_ID for r in interaction.user.roles)


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _expires_iso() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=WARN_EXPIRY_HRS)).isoformat()


def _parse_iso(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


def _is_active(warn: dict) -> bool:
    return datetime.datetime.utcnow() < _parse_iso(warn["expires_at"])


def _fmt_dt(iso: str) -> str:
    dt = _parse_iso(iso)
    return dt.strftime("%b %d, %Y at %H:%M UTC")


class GuardWarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gwarn", description="Issue a guard warning to a Roblox user (expires in 1 hour).")
    @app_commands.describe(
        roblox_user="Roblox username to warn",
        reason="Reason for the warning",
        warning="Warning level",
    )
    async def gwarn(
        self,
        interaction: discord.Interaction,
        roblox_user: str,
        reason: str,
        warning: Literal["1/3", "2/3", "3/3"],
    ):
        if not _has_guard_role(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="You do not have permission to use this command.",
                    color=DANGER,
                ),
                ephemeral=True,
            )
            return

        issued_at  = _now_iso()
        expires_at = _expires_iso()

        entry = {
            "roblox_user":  roblox_user,
            "reason":       reason,
            "warning":      warning,
            "issued_by":    str(interaction.user),
            "issued_by_id": interaction.user.id,
            "issued_at":    issued_at,
            "expires_at":   expires_at,
        }

        warns = storage.get_gwarns()
        key   = roblox_user.lower()
        warns.setdefault(key, []).append(entry)
        storage.save_gwarns(warns)

        color = DANGER if warning == "3/3" else WARNING

        embed = discord.Embed(
            title=f"Guard Warning Issued — {warning}",
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="Roblox User", value=roblox_user,  inline=True)
        embed.add_field(name="Warning",     value=warning,      inline=True)
        embed.add_field(name="Reason",      value=reason,       inline=False)
        embed.add_field(name="Issued By",   value=f"{interaction.user.mention} (`{interaction.user}`)", inline=True)
        embed.add_field(name="Issued At",   value=_fmt_dt(issued_at),  inline=True)
        embed.add_field(name="Expires At",  value=_fmt_dt(expires_at), inline=True)
        embed.set_footer(text="Warning expires in 1 hour")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gcheck", description="Check active warnings for a Roblox user.")
    @app_commands.describe(roblox_user="Roblox username to check")
    async def gcheck(self, interaction: discord.Interaction, roblox_user: str):
        warns     = storage.get_gwarns()
        key       = roblox_user.lower()
        all_warns = warns.get(key, [])
        active    = [w for w in all_warns if _is_active(w)]

        embed = discord.Embed(
            title=f"Guard Warnings — {roblox_user}",
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Checked by {interaction.user} on {datetime.datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
        )

        if not active:
            embed.description = f"**{roblox_user}** has no active warnings."
            embed.color = SUCCESS
        else:
            embed.color = DANGER if any(w["warning"] == "3/3" for w in active) else WARNING
            for i, w in enumerate(active, 1):
                embed.add_field(
                    name=f"Warning {i} — {w['warning']}",
                    value=(
                        f"**Reason:** {w['reason']}\n"
                        f"**Issued By:** {w['issued_by']}\n"
                        f"**Issued At:** {_fmt_dt(w['issued_at'])}\n"
                        f"**Expires At:** {_fmt_dt(w['expires_at'])}"
                    ),
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gwarns", description="Show all active guard warnings.")
    async def gwarns(self, interaction: discord.Interaction):
        warns = storage.get_gwarns()
        rows  = []

        for entries in warns.values():
            for w in entries:
                if _is_active(w):
                    rows.append(w)

        rows.sort(key=lambda w: w["issued_at"], reverse=True)

        embed = discord.Embed(
            title="Active Guard Warnings",
            color=DANGER if rows else SUCCESS,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Requested by {interaction.user} on {datetime.datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
        )

        if not rows:
            embed.description = "No active warnings at this time."
        else:
            for i, w in enumerate(rows, 1):
                embed.add_field(
                    name=f"#{i} — {w['roblox_user']} | {w['warning']}",
                    value=(
                        f"**Reason:** {w['reason']}\n"
                        f"**Issued By:** {w['issued_by']}\n"
                        f"**Issued At:** {_fmt_dt(w['issued_at'])}\n"
                        f"**Expires At:** {_fmt_dt(w['expires_at'])}"
                    ),
                    inline=False,
                )

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="gclear", description="Clear all active warnings for a Roblox user.")
    @app_commands.describe(roblox_user="Roblox username to clear warnings for")
    async def gclear(self, interaction: discord.Interaction, roblox_user: str):
        if not _has_clear_role(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="You do not have permission to use this command.",
                    color=DANGER,
                ),
                ephemeral=True,
            )
            return

        warns = storage.get_gwarns()
        key   = roblox_user.lower()
        active_before = [w for w in warns.get(key, []) if _is_active(w)]

        if not active_before:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"**{roblox_user}** has no active warnings to clear.",
                    color=WARNING,
                ),
                ephemeral=True,
            )
            return

        warns[key] = [w for w in warns.get(key, []) if not _is_active(w)]
        storage.save_gwarns(warns)

        embed = discord.Embed(
            title="Warnings Cleared",
            description=f"Cleared **{len(active_before)}** active warning(s) for **{roblox_user}**.",
            color=SUCCESS,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Cleared by {interaction.user} on {datetime.datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(GuardWarnCog(bot))
