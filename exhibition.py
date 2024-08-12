
from discord import app_commands
from typing import Optional
import json

from params import *

EXHIBITION_CHANNELS = {
    776900400842276864: {  #exhibition-match-1
        'label': '1',
        'role': 945560810988658719,
        'color': int('d93725', 16)
    },
    776900905781559336: {  #exhibition-match-2
        'label': '2',
        'role': 945560810988658719,
        'color': int('245ee3', 16)
    },
}

"""Debugging in A&AO Test Server"""
if True:
    EXHIBITION_CHANNELS = {
        975900061659701299: {
            'label': '1',
            'role': 950636361608736818,
            'color': int('d93725', 16)
        },
        975900080118841384: {
            'label': '2',
            'role': 950636361608736818,
            'color': int('245ee3', 16)
        },
        975900115032219728: {
            'label': '3',
            'role': 950636361608736818,
            'color': int('000000', 16)
        }
    }
""""""


## Embeds
def exhibition_start__embed(color):
    return discord.Embed(color=color,
                         description="Exhibition match started.\n\nAnyone (including staff) may invoke slash command `/end_exhibition` when done. On the honor system, make sure ending it is the right thing to do.")


def exhibition_end__embed(color, winner):
    return discord.Embed(color=color,
                         description=f"Exhibition match ended.\n\n{'Congratulations to the winner(s): ' if winner else ''}{winner}")


def exhibition_init__embed(color):
    return discord.Embed(color=color,
                         description="Press the button below to start an exhibition match in this channel. Players will be granted the Exhibition role, which will hide commentary from them.")


class ExhibitionStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.cancel_word = "cancel"

    @discord.ui.button(label='Create Match', style=discord.ButtonStyle.primary, custom_id='exhibition_start_view')
    async def create_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        exh = EXHIBITION_CHANNELS.get(interaction.channel_id)
        exh_label = exh['label']
        exh_role = interaction.guild.get_role(exh['role'])
        exh_color = exh['color']
        if not exh or not exh_label or not exh_role or not exh_color and exh_color != 0:
            await interaction.followup.send("Invalid data might be stored in program.", ephemeral=True)
            return

        cur.execute("SELECT user_id, channel FROM exhibition_users")
        participants = cur.fetchall()
        exh_part = [p for p in participants if exh_label in json.loads(p[1])]
        if exh_part:
            await interaction.followup.send(
                "Exhibition already started. Player or staff must invoke slash command `/end_exhibition`.",
                ephemeral=True)
            return

        def check(msg: discord.Message):
            return msg.channel.id == interaction.channel_id and msg.author.id == interaction.user.id and (
                    msg.mentions or self.cancel_word in msg.content.lower())

        await interaction.followup.send(
            f"@ Mention all players who are to participate. Make sure to ping YOURSELF too if you are included. Or type `{self.cancel_word}` to cancel the command.",
            ephemeral=True)
        exh_ch = interaction.guild.get_channel_or_thread(interaction.channel_id)
        await exh_ch.set_permissions(interaction.user, send_messages=True)
        message = await bot.wait_for('message', timeout=600.0, check=check)
        await exh_ch.set_permissions(interaction.user, overwrite=None)

        if self.cancel_word in message.content.lower():
            await interaction.followup.send("Command canceled.", ephemeral=True)
            await message.delete()
            return
        for user in message.mentions:
            cur.execute(
                "SELECT user_id, channel FROM exhibition_users WHERE user_id = (?)",
                (user.id,)
            )
            participant = cur.fetchall()
            if not participant:
                cur.execute(
                    "INSERT INTO exhibition_users (user_id, channel) VALUES (?, ?)",
                    (user.id, json.dumps([exh_label]))
                )
                conn.commit()
            else:
                _, ch_labels = participant[0]
                ch_labels = json.loads(ch_labels)
                if exh_label not in ch_labels:
                    ch_labels.append(exh_label)
                    cur.execute(
                        "REPLACE INTO exhibition_users (user_id, channel) VALUES (?, ?)",
                        (user.id, json.dumps(ch_labels))
                    )
                    conn.commit()
            await user.add_roles(exh_role)

        await interaction.followup.send(embed=exhibition_start__embed(exh_color))


@tree.command(description="Set up exhibition channels with interactive start button.")
@app_commands.default_permissions(manage_guild=True)
async def init_exhibitions(interaction: discord.Interaction):
    for exh_id in EXHIBITION_CHANNELS.keys():
        exh_ch = interaction.guild.get_channel_or_thread(exh_id)
        await exh_ch.send(embed=exhibition_init__embed(EXHIBITION_CHANNELS[exh_id]['color']), view=ExhibitionStartView())
    await interaction.response.send_message("Initial embeds sent to exhibition channels!")


@tree.command(description="Stops exhibition match in channel, removes roles")
@app_commands.checks.bot_has_permissions(send_messages=True, manage_roles=True)
@app_commands.describe(
    winner="Name the winners if any, for commemoration"
)
async def end_exhibition(interaction: discord.Interaction, winner: Optional[str] = ""):
    await interaction.response.defer()
    exh = EXHIBITION_CHANNELS.get(interaction.channel_id)
    if not exh:
        await interaction.followup.send("Must be in exhibition channel.", ephemeral=True)
        return
    exh_label = exh['label']
    exh_role = interaction.guild.get_role(exh['role'])
    exh_color = exh['color']
    if not exh_label or not exh_role or not exh_color and exh_color != 0:
        await interaction.followup.send("Invalid data might be stored in program.", ephemeral=True)
        return

    cur.execute("SELECT user_id, channel FROM exhibition_users")
    participants = cur.fetchall()
    exh_part = [p for p in participants if exh_label in json.loads(p[1])]
    if not exh_part:
        await interaction.followup.send("No ongoing exhibition detected in this channel.", ephemeral=True)
        return
    for p in exh_part:
        member = interaction.guild.get_member(p[0])
        if not member:
            cur.execute(
                "DELETE FROM exhibition_users WHERE user_id = (?)",
                (p[0],)
            )
            conn.commit()
            continue
        ch_labels = json.loads(p[1])
        ch_labels.remove(exh_label)
        if ch_labels:
            cur.execute(
                "REPLACE INTO exhibition_users (user_id, channel) VALUES (?, ?)",
                (member.id, json.dumps(ch_labels))
            )
            conn.commit()
        else:
            await member.remove_roles(exh_role)
            cur.execute(
                "DELETE FROM exhibition_users WHERE user_id = (?)",
                (member.id,)
            )
            conn.commit()

    await interaction.followup.send(embed=exhibition_end__embed(exh_color, winner))
    await interaction.followup.send(embed=exhibition_init__embed(exh_color), view=ExhibitionStartView())


"""
@tree.command(description="Starts an exhibition match with pinged users")
@app_commands.checks.bot_has_permissions(send_messages=True, manage_roles=True, manage_channels=True)
@app_commands.describe(
    include_self='Whether to automatically include yourself as a participant'
)
@app_commands.choices(include_self=[app_commands.Choice(name="Yes", value=True), app_commands.Choice(name="No", value=False)])
async def start_exhibition(interaction: discord.Interaction, include_self: app_commands.Choice[bool] = True):
    exh = EXHIBITION_CHANNELS.get(interaction.channel_id)
    if not exh:
        await interaction.response.send_message("Must be in exhibition channel.", ephemeral=True)
        return
    exh_label = exh['label']
    exh_role = interaction.guild.get_role(exh['role'])
    if not exh_label or not exh_role:
        await interaction.response.send_message("Invalid data stored.", ephemeral=True)
        return

    async def add_exh_role(user: discord.Member):
        cur.execute(
            "SELECT user_id, channel FROM exhibition_users WHERE user_id = (?)",
            (user.id,)
        )
        participant = cur.fetchall()
        if not participant:
            cur.execute(
                "INSERT INTO exhibition_users (user_id, channel) VALUES (?, ?)",
                (user.id, json.dumps([exh_label]))
            )
            conn.commit()
        else:
            _, ch_labels = participant[0]
            ch_labels = json.loads(ch_labels)
            if exh_label not in ch_labels:
                ch_labels.append(exh_label)
                cur.execute(
                    "REPLACE INTO exhibition_users (user_id, channel) VALUES (?, ?)",
                    (user.id, json.dumps(ch_labels))
                )
                conn.commit()
        await user.add_roles(exh_role)

    cancel_word = 'cancel'  # must be lowercase if later checked against .lower()

    def check(msg: discord.Message):
        return msg.channel.id == interaction.channel_id and msg.author.id == interaction.user.id and (msg.mentions or cancel_word in msg.content.lower())

    try:
        self_incl_str = "@ Mention all other players NOT including yourself." if include_self else "@ Mention all players; you are NOT included by default."
        await interaction.followup.send(f"{interaction.user.mention} Ready to start an exhibition match? {self_incl_str} Or type `{cancel_word}` to cancel command.")
        message = await bot.wait_for(event='message', timeout=600.0, check=check)
        if cancel_word in message.content.lower():
            await interaction.response.send_message("Command canceled.")
            return
        for usr in message.mentions:
            await add_exh_role(usr)
        if include_self.value:
            await add_exh_role(interaction.user)
    except asyncio.TimeoutError:
        await interaction.response.send_message("Command timed out.", ephemeral=True)
    else:
        exh_ch = interaction.guild.get_channel(interaction.channel_id)
        await exh_ch.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message("Exhibition match started. You can invoke this command again to add more people.\n\nAnyone (including staff) may invoke slash command `/end_exhibition` when done. On the honor system, make sure it is right to end.")
"""