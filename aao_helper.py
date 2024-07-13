
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import sqlite3
import os
import re
import random
import datetime as datetime_module # stupid aspect of datetime being also an object
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
intents = discord.Intents.all()

bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
tree = bot.tree

conn = sqlite3.connect("info.db")
cur = conn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS threads_persist (
        channelthread_id INTEGER PRIMARY KEY
    )
    """
)
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS ranks_added (
        user_id INTEGER PRIMARY KEY,
        rank TEXT,
        season_num INTEGER,
        note TEXT
    )
    """
)
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS ranked_seasons (
        season_num INTEGER PRIMARY KEY,
        end_timestamp INTEGER
    )
    """
)
conn.commit()



STAFF_ROLE_ID = 943827276104097842

TIME_FORMAT = "%Y/%m/%d %H:%M"



@tree.command(description="Randomly assign sides for 2-5 players")
@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.describe(
        player_one='Player one\'s name',
        player_two='Player two\'s name',
        player_three='Player three\'s name',
        player_four='Player four\'s name',
        player_five='Player five\'s name',
        )
async def sides(interaction: discord.Interaction, player_one: str, player_two: str, player_three: Optional[str] = None, player_four: Optional[str] = None, player_five: Optional[str] = None):
    players = [player_one, player_two, player_three, player_four, player_five]
    players = [x for x in players if x]
    random.shuffle(players)
    amount = len(players)
    g = amount - 2
    sides = [
        ['<:axis:665257614002749482>','<:allies:665257668797267989>'],
        ['<:allies:665257668797267989>','<:germany_aa:660218154286448676>','<:japan_aa:660218154638901279>'],
        ['<:us_r:1180308567694250055>','<:united_kingdom:660218154378854401>','<:germany_aa:660218154286448676>','<:japan_aa:660218154638901279>'],
        ['<:soviet_union:660218154227859457>','<:germany_aa:660218154286448676>','<:united_kingdom:660218154378854401>','<:japan_aa:660218154638901279>','<:united_states:660218154160619533>'],
    ]
    await interaction.response.send_message('\n'.join(a + b for a, b in zip(sides[g], players)))



@tree.command(description="Create or edit embed message (reply to edit)")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.describe(
        title='Title header of embed (max 256 char)',
        description='Body text of embed (max 4096 char)',
        footer='Footer text of embed (max 2048 char)',
        color='Color of embed siding (hex code)',
        image='Large image below body (url to image)',
        )
async def write_embed(interaction: discord.Interaction, title: str, description: str, footer: Optional[str] = None, color: Optional[str] = None, image: Optional[str] = None):
    async def hex_str_to_int(hex_str: str): # Helper function for color parameter
        hex_str = hex_str.strip().strip("#")
        for c in hex_str:
            if c not in "0123456789abcdefABCDEF": # characters that are valid in hexadecimal
                await interaction.response.send_message("Color must be provided as valid hex code.", ephemeral=True)
                return 0
        return int(hex_str, 16)
    
    TITLE_LIMIT = 256
    DESC_LIMIT = 4096
    FOOTER_LIMIT = 2048
    err_msg = ""
    if len(title) > TITLE_LIMIT:
        err_msg += f"Character limit of title ({TITLE_LIMIT}) exceeded by {len(title) - TITLE_LIMIT}\n"

    if len(description) > DESC_LIMIT:
        err_msg += f"Character limit of description ({DESC_LIMIT}) exceeded by {len(description) - DESC_LIMIT}\n"
    
    if footer and len(footer) > FOOTER_LIMIT:
        err_msg += f"Character limit of footer ({FOOTER_LIMIT}) exceeded by {len(footer) - FOOTER_LIMIT}\n"
    
    if err_msg: 
        await interaction.response.send_message(err_msg, ephemeral=True)
        return
        
    
    embed = discord.Embed(title=title, description=description, color=hex_str_to_int(color) if color else 0)
    if footer: embed.set_footer(footer)
    if image: embed.set_image(image) # Note: have not added url validation for the image

    target_msg = interaction.message.reference
    content = interaction.message.content
    if target_msg and target_msg.author == bot.user: 
        await target_msg.edit(embed=embed)
        if content:
            if re.match('^\s\s?$', content):
                await interaction.response.send_message("To help prevent accidental erasures, at least 3 spaces are required to delete non-embed message content.", ephemeral=True)
            elif re.match('^\s\s\s+$', content):
                await target_msg.edit(content=None)
            else:
                await target_msg.edit(content=content)

    else:
        await interaction.response.send_message(content=content, embed=embed)



@tree.command(description="Toggles whether a thread or channel is kept unarchived")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(manage_threads=True)
async def auto_unarchive(interaction: discord.Interaction):
    c_id = interaction.message.channel.id # Can be thread id or channel id if not thread
    cur.execute(
        "SELECT channelthread_id FROM threads_persist WHERE channelthread_id = (?)",
        (c_id)
    )
    if cur.fetchall():
        cur.execute(
            "DELETE FROM threads_persist WHERE channelthread_id = (?)",
            (c_id)
        )
        conn.commit()
        await interaction.response.send_message("No longer thread-unarchiving automatically")
    else:
        cur.execute(
            "INSERT OR REPLACE INTO threads_persist (channelthread_id) VALUES (?)",
            (c_id)
        )
        conn.commit()
        await interaction.response.send_message("Now thread-unarchiving automatically")



RANK_LIST = ["Top 10", "Platinum", "Gold", "Silver", "Bronze"]
RANK_DICT = {
    0: "",
    733500181601058896: RANK_LIST[0],
    659913624315232276: RANK_LIST[1],
    660255916305940480: RANK_LIST[2],
    660255959117201431: RANK_LIST[3],
    660255996391849985: RANK_LIST[4]
    }



class GrantRankModal(discord.ui.Modal):
    def __init__(self, user_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user_id = user_id
        cur.execute(
            "SELECT note FROM ranks_added WHERE user_id = (?)",
            (user_id)
        )
        note = cur.fetchone()
        note = note[0] if note else ""
        self.add_item(discord.ui.TextInput(label="Add or edit user note, e.g. #1 Axis / #1 Allies", default=note, max_length=50))

    async def callback(self, interaction: discord.Interaction):
        input_val = self.children[0].value
        cur.execute(
            "INSERT INTO ranks_added (user_id, rank, season_num, note) VALUES (?, "", 0, ?) ON CONFLICT (user_id) DO UPDATE SET note = (?)",
            (self.user_id, input_val, input_val)
        )
        conn.commit()
        await interaction.response.send_message("Edited user note!", ephemeral=True)


SEASON_END_WEEKS = 5 # Weeks before a season ends where it counts as already that season end

class GrantRankView(discord.ui.View):
    def __init__(self, user: discord.Member):
        self.user = user
        cur.execute("SELECT season_num, end_timestamp FROM ranked_seasons")
        self.seasons = sorted([(num, ts) for num, ts in cur.fetchall()], key=lambda pair : pair[0], reverse=True)
        seasons_copy = self.seasons.copy()
        for pair in self.seasons: # ensures select menu won't show future season ends
            if datetime.fromtimestamp(pair[1], timezone.utc) - datetime.now(timezone.utc) > timedelta(weeks=SEASON_END_WEEKS): 
                seasons_copy.remove(pair)
        self.seasons = seasons_copy # copy process allows for loop to not operate on constantly changing list
        self.role_id = 0
        self.seasonNum = 0

    @discord.ui.select(
        row = 0,
        options = [ discord.SelectOption(label=badge) for badge in RANK_LIST ],
        min_values = 0,
        placeholder = "Select rank (use Note to provide further info)"
    )
    async def select_callback_1(self, select, interaction):
        for r_id, v in RANK_DICT.items(): # assumes 1-to-1 dict
            if v == select.values[0].value: # assumes defaults to label
                self.role_id = r_id
                return
        self.role_id = 0


    def get_print_seasons(self):
        [("S"+str(num)+" - end: "+datetime.fromtimestamp(ts, timezone.utc).strftime(TIME_FORMAT), str(num)) for num, ts in self.seasons]

    @discord.ui.select(
        row = 1,
        options = [ discord.SelectOption(label=p[0], value=p[1]) for p in get_print_seasons() ],
        min_values = 0,
        placeholder = "Select season end (mid-season = previous season)"
    )
    async def select_callback_2(self, select, interaction):
        v = select.values[0].value
        self.seasonNum = int(v) if v else 0

    @discord.ui.button(
        row = 2,
        label = "Add Note",
        style = discord.ButtonStyle.secondary
    )
    async def button_callback_1(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(GrantRankModal(title="Add Note"))

    @discord.ui.button(
        row = 2,
        label = "Submit",
        style = discord.ButtonStyle.primary
    )
    async def button_callback_2(self, interaction: discord.Interaction, button):
        if self.role_id:
            for r_id in RANK_DICT.keys():
                if self.user.get_role(r_id) and override_rank(self.role_id, r_id):
                    await self.user.remove_roles(interaction.guild.get_role(r_id))
            
            await self.user.add_roles(interaction.guild.get_role(self.role_id))

        rank = RANK_DICT[self.role_id]
        cur.execute(
            "INSERT INTO ranks_added (user_id, rank, season_num, note) VALUES (?, ?, ?, "") ON CONFLICT (user_id) DO UPDATE SET rank = rank || (?), season_num = season_num || (?)",
            (self.user.id, rank, self.seasonNum, rank, self.seasonNum)
        )
        conn.commit()
        cur.execute(
            "SELECT rank, season_num, note FROM ranks_added WHERE user_id = (?)", 
            (self.user.id)
        )
        entry = cur.fetchone()
        confirm_str = "Rank granted!" if rank else "User updated."
        info_str = f"Rank: {entry[0]}\nFrom season: {entry[1]}\nNote:\n{entry[2]}"
        await interaction.response.send_message(f"{confirm_str}\n\n{info_str}", ephemeral=True)



@tree.command(description="Grants medallion rank with accounting for time")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.context_menu(name="Grant Rank")
async def grant_rank(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(view=GrantRankView(user), ephemeral=True)


USUAL_END_TIME = "17:00" # Usual end time in UTC for season end

@tree.command(description="Edit season end dates and times (set date blank to delete)")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.describe(
        seasonNum='Which number season to edit end time',
        endDate='Day (UTC) of season end in YYYY/MM/DD format',
        endTime='Time (UTC) of season end in HH:MM 24hr format',
)
async def set_season_end(interaction: discord.Interaction, seasonNum: int, endDate: str, endTime: str = USUAL_END_TIME):
    if endDate:
        try:
            endTimestamp = int(datetime.timestamp(datetime.strptime(endDate + " " + endTime, TIME_FORMAT)))

            cur.execute("SELECT season_num, end_timestamp FROM ranked_seasons")
            for pair in cur.fetchall():
                if seasonNum < pair[0] and endTimestamp >= pair[1] or seasonNum > pair[0] and endTimestamp <= pair[1]:
                    await interaction.response.send_message("ERROR: Higher number season must have later end time", ephemeral=True)
                    return
                
            cur.execute(
                "INSERT OR REPLACE INTO ranked_seasons (season_num, end_timestamp) VALUES (?, ?)",
                (seasonNum, endTimestamp)
            )
            conn.commit()

        except ValueError:
            await interaction.response.send_message("Invalid datetime provided, please check format", ephemeral=True)
    else:
        cur.execute(
            "DELETE FROM ranked_seasons WHERE season_num = (?)", 
            (seasonNum)
        )
        conn.commit()
        await interaction.response.send_message(f"Season {seasonNum} removed from seasons list", ephemeral=True)

    cur.execute("SELECT season_num, end_timestamp FROM ranked_seasons")
    desc = "\n".join(["    ".join((sn, datetime.fromtimestamp(ts, timezone.utc).strftime(TIME_FORMAT))) for sn, ts in cur.fetchall()])
    await interaction.response.send_message(embed=discord.Embed(title="Season    End Date", description=desc))


def expiry_season(rank: str, season_num: int) -> int:
    # Assumes that mid-season = previous season, i.e. the end date is the same either way
    if rank == RANK_LIST[0]:
        return season_num + 3
    else:
        return season_num + 2

@tree.command(description="Lists users in the ranks database, oldest first")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
async def show_user_ranks(interaction: discord.Interaction):
    with open("show_ranks.txt", 'w') as show_ranks:
        show_ranks.write("User                             Rank      Season  End Date            Note")
        cur.execute("SELECT season_num, end_timestamp FROM ranked_seasons")
        seasons = dict(cur.fetchall())
        cur.execute("SELECT user_id, rank, season_num, note FROM ranks_added")
        row_list = []
        for row in cur.fetchall():
            name = interaction.guild.get_member(row[0]).display_name
            rank = row[1]
            num = row[2]
            end_date = datetime.fromtimestamp(seasons[num], timezone.utc).strftime(TIME_FORMAT)
            note = row[3]
            row_list.append((name, " "*(33-len(name)), rank, " "*(10-len(rank)), str(num), " "*(8-len(str(num))), end_date, " "*(20-len(end_date)), note))
        row_list.sort(key=lambda tup : expiry_season(tup[2], seasons[int(tup[4])]))
        for row in row_list:
            show_ranks.write("".join(row))
        await interaction.response.send_message(file=show_ranks)



# Helper function for refactoring
async def message_checks(message: discord.Message):
    if message.author == bot.user or message.author.bot:
        return
    
    if message.channel.id == 941854510647762954: # server-logs
        return

    if "<@644511391302025226>" in message.content or "<@!644511391302025226>" in message.content: # SpectacularVernacular -> SadPuppies
        await message.reply("Did you mean <@!948208421054865410>?")

    if re.search("aa1942calc.com/#/[a-zA-Z0-9-_]+", message.content.lower()):
        await message.edit(suppress=True)



@bot.event
async def on_message(message):
    await message_checks(message)


@bot.event
async def on_message_edit(before, after):
    await message_checks(after)


@bot.event
async def on_thread_update(before: discord.Thread, after: discord.Thread):
    cur.execute("SELECT channelthread_id FROM threads_persist")
    c_ids = list(cur.fetchall())
    if not before.archived and after.archived and not after.archiver_id and not after.locked \
        and (after.parent_id in c_ids or after.id in c_ids):
        await after.edit(archived=False)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    payload.message_author_id


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx):
    ctx.bot.tree.copy_global_to(guild=ctx.guild)
    synced = await ctx.bot.tree.sync(guild=ctx.guild)
    await ctx.message.reply(f"Synced with {len(synced)} guilds")


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


# Start the bot
bot.run(TOKEN)