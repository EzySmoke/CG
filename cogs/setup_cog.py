import discord
from discord import app_commands
from discord.ext import commands
from utils import storage

ACCENT = discord.Color.from_rgb(88, 101, 242)


class AddMedalModal(discord.ui.Modal, title="Add Medal"):
    medal_name = discord.ui.TextInput(label="Medal Name", placeholder="e.g. Medal of Valor", max_length=64)
    medal_description = discord.ui.TextInput(
        label="Description",
        placeholder="What this medal is awarded for",
        style=discord.TextStyle.paragraph,
        max_length=256,
    )

    async def on_submit(self, interaction: discord.Interaction):
        medals = storage.get_medals()
        key = self.medal_name.value.lower().replace(" ", "_")
        medals[key] = {"name": self.medal_name.value, "description": self.medal_description.value}
        storage.save_medals(medals)
        await interaction.response.send_message(
            f"Medal **{self.medal_name.value}** has been added.", ephemeral=True
        )


class RemoveMedalSelect(discord.ui.Select):
    def __init__(self, medals: dict):
        options = [discord.SelectOption(label=v["name"], value=k) for k, v in medals.items()]
        super().__init__(placeholder="Select a medal to remove…", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        medals   = storage.get_medals()
        removed  = medals.pop(self.values[0], None)
        storage.save_medals(medals)
        name = removed["name"] if removed else self.values[0]
        await interaction.response.send_message(f"Medal **{name}** removed.", ephemeral=True)


async def _set_channel_flow(interaction: discord.Interaction, label: str, key: str):
    await interaction.response.send_message(
        f"Mention the channel to use as the **{label}** channel. Type `cancel` to skip.",
        ephemeral=True,
    )

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await interaction.client.wait_for("message", check=check, timeout=60)
        if msg.content.lower() == "cancel":
            await msg.delete()
            return
        if msg.channel_mentions:
            ch  = msg.channel_mentions[0]
            cfg = storage.get_setup()
            cfg[key] = ch.id
            storage.save_setup(cfg)
            await msg.delete()
            await interaction.followup.send(f"{label} set to {ch.mention}.", ephemeral=True)
        else:
            await msg.delete()
            await interaction.followup.send("No channel mentioned. Try again.", ephemeral=True)
    except Exception:
        pass


class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Add Medal", style=discord.ButtonStyle.primary)
    async def add_medal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddMedalModal())

    @discord.ui.button(label="Remove Medal", style=discord.ButtonStyle.danger)
    async def remove_medal(self, interaction: discord.Interaction, button: discord.ui.Button):
        medals = storage.get_medals()
        if not medals:
            await interaction.response.send_message("No medals configured yet.", ephemeral=True)
            return
        view = discord.ui.View(timeout=120)
        view.add_item(RemoveMedalSelect(medals))
        await interaction.response.send_message("Select a medal to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="Welcome Channel", style=discord.ButtonStyle.secondary)
    async def set_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _set_channel_flow(interaction, "Welcome", "welcome_channel")

    @discord.ui.button(label="Mod Log Channel", style=discord.ButtonStyle.secondary)
    async def set_mod_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _set_channel_flow(interaction, "Moderation Log", "mod_log_channel")

    @discord.ui.button(label="Chat Log Channel", style=discord.ButtonStyle.secondary)
    async def set_chat_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _set_channel_flow(interaction, "Chat Log", "chat_log_channel")

    @discord.ui.button(label="Event Log Channel", style=discord.ButtonStyle.secondary)
    async def set_event_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _set_channel_flow(interaction, "Event Log", "event_log_channel")

    @discord.ui.button(label="CG Comms Channel", style=discord.ButtonStyle.secondary)
    async def set_cg_comms(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _set_channel_flow(interaction, "CG Comms", "cg_comms_channel")


def build_setup_embed(cfg: dict, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title="Bot Configuration", color=ACCENT)

    def ch(key):
        cid = cfg.get(key)
        if cid:
            c = guild.get_channel(cid)
            return c.mention if c else f"<#{cid}>"
        return "Not configured"

    embed.add_field(name="Welcome Channel",   value=ch("welcome_channel"),   inline=True)
    embed.add_field(name="Mod Log Channel",   value=ch("mod_log_channel"),   inline=True)
    embed.add_field(name="Chat Log Channel",  value=ch("chat_log_channel"),  inline=True)
    embed.add_field(name="Event Log Channel", value=ch("event_log_channel"), inline=True)
    embed.add_field(name="CG Comms Channel",  value=ch("cg_comms_channel"),  inline=True)

    medals      = storage.get_medals()
    medal_list  = "\n".join(f"**{v['name']}** — {v['description']}" for v in medals.values()) or "None configured"
    embed.add_field(name="Medals", value=medal_list[:1024], inline=False)
    embed.set_footer(text="Use the buttons below to configure each section.")
    return embed


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure the bot — channels, medals, and more.")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        cfg   = storage.get_setup()
        embed = build_setup_embed(cfg, interaction.guild)
        await interaction.response.send_message(embed=embed, view=SetupView(), ephemeral=True)

    @app_commands.command(name="editsetup", description="Edit the current bot configuration.")
    @app_commands.default_permissions(administrator=True)
    async def editsetup(self, interaction: discord.Interaction):
        cfg   = storage.get_setup()
        embed = build_setup_embed(cfg, interaction.guild)
        embed.title = "Edit Configuration"
        await interaction.response.send_message(embed=embed, view=SetupView(), ephemeral=True)

    @app_commands.command(name="medals", description="View all available medals.")
    async def medals(self, interaction: discord.Interaction):
        medals = storage.get_medals()
        if not medals:
            await interaction.response.send_message(
                "No medals configured yet. Use `/setup` to add some.", ephemeral=True
            )
            return
        embed = discord.Embed(title="Medals", color=ACCENT)
        for v in medals.values():
            embed.add_field(name=v["name"], value=v["description"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="assignmedal", description="Assign a medal to a user.")
    @app_commands.describe(user="The user to award", reason="Reason for the award")
    @app_commands.default_permissions(manage_roles=True)
    async def assignmedal(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        medals = storage.get_medals()
        if not medals:
            await interaction.response.send_message("No medals configured. Use `/setup` first.", ephemeral=True)
            return

        options = [discord.SelectOption(label=v["name"], value=k) for k, v in medals.items()]

        class MedalSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(placeholder="Choose a medal to award…", options=options[:25])

            async def callback(self_inner, inter: discord.Interaction):
                key   = self_inner.values[0]
                medal = medals[key]
                awarded = storage.get_awarded_medals()
                uid = str(user.id)
                if uid not in awarded:
                    awarded[uid] = []
                awarded[uid].append({"medal": key, "reason": reason, "awarded_by": inter.user.id})
                storage.save_awarded_medals(awarded)
                embed = discord.Embed(
                    title="Medal Awarded",
                    description=f"**{medal['name']}** has been awarded to {user.mention}.",
                    color=ACCENT,
                )
                embed.add_field(name="Reason",     value=reason)
                embed.add_field(name="Awarded by", value=inter.user.mention)
                await inter.response.edit_message(embed=embed, view=None)
                await inter.channel.send(embed=embed)

        view = discord.ui.View(timeout=120)
        view.add_item(MedalSelect())
        await interaction.response.send_message("Select a medal to award:", view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SetupCog(bot))
