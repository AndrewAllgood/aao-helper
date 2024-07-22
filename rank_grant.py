
from discord import app_commands
from typing import Optional
import re
import datetime as datetime_module # stupid aspect of datetime being also an object
from datetime import datetime, timezone, timedelta

from params import *

TIME_FORMAT = "%Y/%m/%d %H:%M"
TOP_TIME = 3
SEASON_END_WEEKS = 5 # Weeks before a season ends where it counts as already that season end
USUAL_END_TIME = "17:00" # Usual end time in UTC for season end



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
        return season_num + TOP_TIME
    else:
        return season_num + TOP_TIME - 1

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

    cur.execute("SELECT season_num, end_timestamp FROM current_season_end")
    _, end_ts = cur.fetchone()
    currentness_warn = ""
    if datetime.fromtimestamp(end_ts, timezone.utc) - datetime.now(timezone.utc) < timedelta(0):
        "WARNING: Current season end setting is out of date. Use slash command `/set_season_end` to update as soon as possible.\n\n"

    await interaction.response.send_message(f"{currentness_warn}{confirm_str}User's ranks recorded:\n\nUser: {interaction.guild.get_member(user_id).display_name}\n{info_str}", ephemeral=True)



class GrantRankModal(discord.ui.Modal):
    def __init__(self, view, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.view = view
        self.add_item(discord.ui.TextInput(label="Add user note", placeholder="Can be anything", max_length=50))

    async def callback(self, interaction: discord.Interaction):
        self.view.set_note(self.children[0].value)


def season_select_options() -> list[discord.SelectOption]:
    cur.execute("SELECT season_num, end_timestamp FROM current_season_end")
    seasonNum, end_ts = cur.fetchone()
    if datetime.fromtimestamp(end_ts, timezone.utc) - datetime.now(timezone.utc) > timedelta(weeks=SEASON_END_WEEKS): 
        seasonNum -= 1
    return [ discord.SelectOption(label=str(seasonNum), default=True) ] + [ discord.SelectOption(label=str(seasonNum - x)) for x in range(1, TOP_TIME+1) ]


class GrantRankView(discord.ui.View):
    def __init__(self, user: discord.Member, role_id: int):
        self.time_added = datetime.timestamp(datetime.now(timezone.utc))
        self.user = user
        self.seasonNum = 0
        self.role_id = role_id
        self.note = ""

    def set_note(self, note):
        self.note = note

    @discord.ui.select(
        row = 0,
        options = season_select_options(),
        min_values = 1,
        max_values = 1,
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
            if i1 >= i2:
                await interaction.response.send_message("Invalid range provided", ephemeral=True)
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



@tree.command(description="Edit current season end date and time")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.describe(
        seasonNum='Current number season whose end is coming up',
        endDate='Day (UTC) of season end in YYYY/MM/DD format',
        endTime='Time (UTC) of season end in HH:MM 24hr format',
)
async def set_season_end(interaction: discord.Interaction, seasonNum: int, endDate: str, endTime: str = USUAL_END_TIME):
    try:
        end_datetime = datetime.strptime(endDate + " " + endTime, TIME_FORMAT)
        endTimestamp = int(datetime.timestamp(end_datetime))
            
        cur.execute(
            "INSERT OR REPLACE INTO current_season_end (singleton, season_num, end_timestamp) VALUES (?, ?, ?)",
            (0, seasonNum, endTimestamp)
        )
        conn.commit()
        await interaction.guild.fetch_channel(SERVER_COMM_CH).send(f"Current season set to S{seasonNum}, end set to {datetime.strftime(end_datetime, TIME_FORMAT)} UTC")

    except ValueError:
        await interaction.response.send_message("Invalid datetime provided, please check format", ephemeral=True)



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

