
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
from discord.utils import MISSING
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
        time_added INTEGER PRIMARY KEY
        user_id INTEGER,
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
MOD_ROLE_ID = 659883868635267075
SERVER_COMM_CH = 670090977356021780

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
RANK1_LIST = ["#1 Rank Axis", "#1 Rank Allies"]
RANK_DICT = {
    733500181601058896: RANK_LIST[0],
    659913624315232276: RANK_LIST[1],
    660255916305940480: RANK_LIST[2],
    660255959117201431: RANK_LIST[3],
    660255996391849985: RANK_LIST[4],
    664624127617007618: RANK1_LIST[0],
    664624098311274506: RANK1_LIST[1]
    }
RANK_ID_DICT = { v: k for k, v in RANK_DICT }
REACTION_DICT = { # <:platinum:667881631473860667><:gold:667881111149477905><:silver:667880684244828201><:bronze:667882292622000158>
    667881631473860667: RANK_LIST[1],
    667881111149477905: RANK_LIST[2],
    667880684244828201: RANK_LIST[3],
    667882292622000158: RANK_LIST[4]
}
RANK_CHOICES = [ app_commands.Choice(name=rank, value=id) for id, rank in RANK_DICT.items() ]



def height(rank: str) -> int:
    if rank not in RANK_LIST:
        raise ValueError("Rank not in RANK_LIST")
    return len(RANK_LIST) - RANK_LIST.index(rank)

def expiry(rank: str, season_num: int) -> int:
    # assumes mid-season = previous season
    if rank == RANK_LIST[0]:
        return season_num + 3
    else:
        return season_num + 2

async def add_record(interaction: discord.Interaction, time_added: int, user_id: int, role_id: int, seasonNum: int, note: str):
    cur.execute(
        "SELECT rank, season_num FROM ranks_added WHERE user_id = (?)", 
        (user_id)
    )
    user_entries = sorted(cur.fetchall(), key= lambda pair : (height(pair[0]), expiry(pair[0], pair[1])), reverse=True)
    rank_to_add = RANK_DICT[role_id]
    user = interaction.guild.get_member(user_id)
    async def add_role(r_id):
        await user.add_roles(interaction.guild.get_role(r_id))
        cur.execute(
            "INSERT INTO ranks_added (time_added, user_id, rank, season_num, note) VALUES (?, ?, ?, ?, ?)",
            (time_added, user_id, rank_to_add, seasonNum, note)
        )
        conn.commit()

    confirm_str = ""
    for rank, season_num in user_entries:
        h_a = height(rank_to_add)
        h = height(rank)
        e_a = expiry(rank_to_add, seasonNum)
        e = expiry(rank, season_num)
        if h_a <= h and e_a <= e:
            if not confirm_str: confirm_str = f"{rank_to_add} rank NOT granted, redundant...\n"
            break # this is why user_entries is reverse sorted
        elif h_a >= h and e_a >= e:
            await add_role(role_id)
            r_id = RANK_ID_DICT[rank]
            if user.get_role(r_id):
                await user.remove_roles(interaction.guild.get_role(r_id))
            cur.execute(
                "DELETE FROM ranks_added WHERE user_id, rank, season_num = (?, ?, ?)",
                (user_id, rank, season_num)
            )
            conn.commit()
            if not confirm_str: confirm_str = f"{rank_to_add} rank granted!\n"
            confirm_str += f"Redundant {rank} rank also removed.\n"
        elif h_a > h and e_a < e or h_a < h and e_a > e:
            await add_role(role_id)
            if not confirm_str: confirm_str = f"{rank_to_add} rank granted!\n"

    cur.execute(
        "SELECT rank, season_num, note FROM ranks_added WHERE user_id = (?)", 
        (user_id)
    )
    entries = cur.fetchall()
    info_str = ""
    for entry in entries:
        r, s_n, n = entry
        info_str += f"\n\nRank: {r}\nExpires: {expiry(r, s_n)}\nNote: {n}"
    await interaction.response.send_message(f"{confirm_str}User's ranks recorded:\n\nUser: {interaction.guild.get_member(user_id).display_name}\n{info_str}", ephemeral=True)


SEASON_END_WEEKS = 5 # Weeks before a season ends where it counts as already that season end


class GrantRankModal(discord.ui.Modal):
    def __init__(self, view, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.view = view
        self.add_item(discord.ui.TextInput(label="Add user note", placeholder="Can be anything", max_length=50))

    async def callback(self, interaction: discord.Interaction):
        self.view.set_note(self.children[0].value)


class GrantRankView(discord.ui.View):
    def __init__(self, user: discord.Member, role_id: int):
        self.time_added = datetime.timestamp(datetime.now(timezone.utc))
        self.user = user
        cur.execute("SELECT season_num, end_timestamp FROM ranked_seasons")
        self.seasons = sorted([(num, ts) for num, ts in cur.fetchall()], key=lambda pair : pair[0], reverse=True)
        seasons_copy = self.seasons.copy()
        for pair in self.seasons: # ensures select menu won't show future season ends
            if datetime.fromtimestamp(pair[1], timezone.utc) - datetime.now(timezone.utc) > timedelta(weeks=SEASON_END_WEEKS): 
                seasons_copy.remove(pair)
        self.seasons = seasons_copy # copy process allows for loop to not operate on constantly changing list
        self.role_id = role_id
        self.seasonNum = self.seasons[0][0]
        self.note = ""

    def set_note(self, note):
        self.note = note

    def get_print_seasons(self):
        [("S"+str(num)+" - end: "+datetime.fromtimestamp(ts, timezone.utc).strftime(TIME_FORMAT), str(num)) for num, ts in self.seasons]

    @discord.ui.select(
        row = 0,
        options = [ discord.SelectOption(label=p[0], value=p[1], default=True) for p in get_print_seasons()[0:1] ] + [ discord.SelectOption(label=p[0], value=p[1]) for p in get_print_seasons()[1:] ],
        min_values = 1,
        placeholder = "Select season end (mid-season = previous season)"
    )
    async def select_callback(self, select, interaction):
        self.seasonNum = int(select.values[0].value)

    @discord.ui.button(
        row = 1,
        label = "Submit",
        style = discord.ButtonStyle.primary
    )
    async def button_callback(self, interaction: discord.Interaction, button):
        await add_record(interaction, self.time_added, self.user.id, self.role_id, self.seasonNum, self.note)

    @discord.ui.button(
        row = 1,
        label = "Add note",
        style = discord.ButtonStyle.secondary
    )
    async def button_callback(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(GrantRankModal(self))



@tree.command(description="Grants Top 10 rank with accounting for time")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.context_menu(name="Bestow Top 10")
async def grant_top_10(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(view=GrantRankView(user, RANK_ID_DICT[RANK_LIST[0]]), ephemeral=True)


# Alternative to fancier options
@tree.command(description="Grants rank with accounting for time. Includes #1 ranks")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(
        user_id='ID of member to grant rank to (enable developer tools and right-click user -> copy ID)',
        rank='Rank to grant member',
        seasonNum='Which number season end (mid-season = previous season)',
        note='Miscellaneous note to attach to this record'
)
@app_commands.choices(rank=RANK_CHOICES)
async def grant_rank(interaction: discord.Interaction, user_id: int, rank: app_commands.Choice, seasonNum: int, note: Optional[str] = ""):
    time_added = datetime.timestamp(datetime.now(timezone.utc))
    await add_record(interaction, time_added, user_id, rank.value, seasonNum, note)



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



def header_line() -> str:
    return "#   User                             Rank      Expires   Note"

def line_to_write(index: int, name: str, rank: str, expires: int, note: str) -> str:
    return "".join((str(index+1), " "*(4-len(str(index+1)), name, " "*(33-len(name)), rank, " "*(10-len(rank)), str(expires), " "*(10-len(str(expires))), note)))

class DeleteRanksModal(discord.ui.Modal):
    def __init__(self, row_list, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.row_list = row_list
        self.add_item(discord.ui.TextInput(label="Enter # index of record(s) to delete", placeholder="Number for single deletion, or #-# for range", max_length=50))

    async def callback(self, interaction: discord.Interaction):
        async def write_file(row_list):
            with open("deleted_ranks.txt", 'w') as deleted_ranks:
                deleted_ranks.write(header_line())
                for index, row in enumerate(row_list):
                    _, name, rank, expires, note = row
                    deleted_ranks.write(line_to_write(index, name, rank, expires, note))
                await interaction.guild.fetch_channel(SERVER_COMM_CH).send(content="Deleted the following records:", file=deleted_ranks)
                
        async def delete_rank(time_added, user_id, rank, commits=True):
            cur.execute(
                "DELETE FROM ranks_added WHERE time_added = (?)",
                (time_added)
            )
            if commits: conn.commit() # if, for faster performance in loop
            role = interaction.guild.get_role(RANK_ID_DICT[rank])
            if role:
                await interaction.guild.get_member(user_id).remove_roles(role)

        index1, index2 = re.search(r"(\d+)(-\d+)?", self.children[0].value).groups()
        if index1 and index2:
            i1, i2 = int(index1)-1, int(index2[1:])-1
            if i1 >= i2: return
            row_range = self.row_list[i1:i2+1]
            if interaction.guild.get_role(MOD_ROLE_ID) not in interaction.user.roles:
                for row in row_range:
                    if datetime.now(timezone.utc) - datetime.fromtimestamp(row[0], timezone.utc) > timedelta(hours=24):
                        await interaction.response.send_message("Need Mod role to delete any entries older than 24 hours", ephemeral=True)
                        return
            for row in row_range:
                cur.execute(
                    "SELECT FROM ranks_added WHERE time_added = (?)",
                    (row[0])
                )
                user_id = cur.fetchone()[1]
                delete_rank(row[0], user_id, row[2], False)
            conn.commit()
            await write_file(row_range)
            await interaction.response.send_message(f"Deleted {len(row_range)} records. Check {interaction.guild.fetch_channel(SERVER_COMM_CH).mention} for trace.", ephemeral=True)
        elif index1:
            time_added, name, rank, expires, note = self.row_list[int(index1)-1]
            cur.execute(
                "SELECT FROM ranks_added WHERE time_added = (?)",
                (time_added)
            )
            user_id = cur.fetchone()[1]
            delete_rank(time_added, user_id, rank)
            await interaction.response.send_message(f"Deleted 1 record.\n\n{header_line()}\n{line_to_write(index1, name, rank, expires, note)}", ephemeral=True)
        else:
            await interaction.response.send_message("No number(s) provided", ephemeral=True)



class ShowRanksView(discord.ui.View):
    def __init__(self, row_list: list):
        self.row_list = row_list

    @discord.ui.button(
        label = "Delete",
        style = discord.ButtonStyle.danger
    )
    async def button_callback(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(DeleteRanksModal(self.row_list, title="Delete Records"))



@tree.command(description="Lists users in the ranks database, oldest first")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
async def show_user_ranks(interaction: discord.Interaction):
    with open("show_ranks.txt", 'w') as show_ranks:
        show_ranks.write(header_line())

        cur.execute("SELECT time_added, user_id, rank, season_num, note FROM ranks_added")
        row_list = []
        for row in cur.fetchall():
            time_added, user_id, rank, num, note = row
            name = interaction.guild.get_member(user_id).display_name
            expires = expiry(rank, num)
            row_list.append([time_added, name, rank, expires, note])

        row_list.sort(key=lambda ls : (ls[3], ls[0]))
        for index, row in enumerate(row_list):
            _, name, rank, expires, note = row
            show_ranks.write(line_to_write(index, name, rank, expires, note))

        await interaction.response.send_message(file=show_ranks, view=ShowRanksView(row_list))



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



last_msgs = {}

@bot.event
async def on_message(message: discord.Message):
    await message_checks(message)

    channel_id = message.channel.id

    ## anti-spam auto-ban
    prev = last_msgs.get(message.author.id)
    limit = 5
    if prev:
        if len(message.content) > 4 and message.content == prev[-1].content and all(channel_id != msg.channel.id for msg in prev): 
            prev.append(message)
            if len(prev) >= limit and len(message.author.roles) <= 1: # only Commanders role
                await message.author.ban(reason=f"spammed {limit} times")
                bots_channel = message.author.guild.get_channel(SERVER_COMM_CH)
                dm_message = f"You have been banned from the server {message.author.guild.name} for spamming in channels. This is to guard against link scams. However, if your message was not a scam, you should be unbanned shortly.\n\nIf you have recovered and secured your account, send a friend request to the Discord user '{message.author.guild.owner.name}' and you may be unbanned."
                await message.author.send(dm_message)
                await bots_channel.send(f"Banned {message.author.mention} who joined <t:{round(message.author.joined_at.timestamp())}:f> for spamming {limit} times \nMessage: {'`'+message.clean_content+'`'}\n\nSent to user in DMs: {dm_message}")
        else:
            last_msgs[message.author.id] = [message]

    else:
        last_msgs[message.author.id] = [message]
    ##



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
    if payload.member.get_role(STAFF_ROLE_ID):
        guild = bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)
        rank_react = [ react for react in msg.reactions if react.emoji.id == payload.emoji.id ][0]
        staff_already = ""
        if [ user async for user in rank_react.users() if user.get_role(STAFF_ROLE_ID) and user.id != payload.member.id ]:
            staff_already = "A Staff member has already reacted to this post."
        await channel.send(staff_already, view=GrantRankView(guild.get_member(payload.message_author_id), RANK_ID_DICT[REACTION_DICT[payload.emoji.id]]), ephemeral=True)
        
        


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