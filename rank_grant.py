import discord.ui
from discord import app_commands
from discord.ext import tasks
from typing import Optional
import re
import csv
import datetime as datetime_module  # stupid aspect of datetime being also an object
from datetime import datetime, timezone, timedelta

from params import *

TIME_FORMAT = "%Y/%m/%d %H:%M"
MEDAL_TIME = 2  # Number of seasons until medallion rank expires (mid-season counted as previous)
TOP_TIME = 3  # Number of seasons until Top 10 role expires
SEASON_END_WEEKS = 5.0  # Weeks before a season ends where it counts as already that season end
USUAL_END_TIME = "17:00"  # Usual end time in UTC for season end
SEASON_START_WEEKS = 5.0  # Weeks after a new season starts where ranks cannot be assigned for the new season

RANK_LIST = ["Top 10", "Platinum", "Gold", "Silver", "Bronze"]  # These must not contain commas for upload_ranks() to work
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
REACTION_DICT = {
    # <:platinum:667881631473860667><:gold:667881111149477905><:silver:667880684244828201><:bronze:667882292622000158>
    667881631473860667: RANK_LIST[1],
    667881111149477905: RANK_LIST[2],
    667880684244828201: RANK_LIST[3],
    667882292622000158: RANK_LIST[4]
}
"""Debugging in A&AO Test Server"""
if True:
    RANK_DICT = {
        1265216205459951668: RANK_LIST[0],
        943044793074847755: RANK_LIST[1],
        941353136470253638: RANK_LIST[2],
        943044862503186443: RANK_LIST[3],
        1265216424570257488: RANK_LIST[4],
        943969266774978580: RANK1_LIST[0],
        943968858170081301: RANK1_LIST[1]
    }
    REACTION_DICT = {
        # <:platinum:940837874746675211> <:gold:940837874927038504><:silver:940837874851512340><:bronze:940837874948001822>
        940837874746675211: RANK_LIST[1],
        940837874927038504: RANK_LIST[2],
        940837874851512340: RANK_LIST[3],
        940837874948001822: RANK_LIST[4]
    }
""""""
RANK_ID_DICT = {v: k for k, v in RANK_DICT.items()}
RANK_CHOICES = [app_commands.Choice(name=rank, value=str(role_id)) for role_id, rank in RANK_DICT.items()]

HEADER_LINE = "#     Discord Username              Rank            Season #   Note"


def line_to_write(index: int, name: str, rank: str, season_num: int, note: str) -> str:
    return "".join([str(index + 1), " " * (4 - len(str(index + 1)) + ": ", name, "," + " " * (33 - len(name)),
                            rank, "," + " " * (15 - len(rank)), str(season_num), "," + " " * (10 - len(str(season_num))), note)])
#TODO sort by expiry but make column season num

def is_top_10_role_id(role_id):
    return role_id in [RANK_ID_DICT[RANK_LIST[0]]] + [RANK_ID_DICT[r_name] for r_name in RANK1_LIST]


def height(rank: str) -> int:
    if rank not in RANK_LIST:
        raise ValueError("Rank not in RANK_LIST")
    return len(RANK_LIST) - RANK_LIST.index(rank)


def expiry(rank: str, season_num: int) -> int:
    # assumes mid-season = previous season
    if is_top_10_role_id(RANK_ID_DICT[rank]):
        return season_num + TOP_TIME
    else:
        return season_num + MEDAL_TIME


def expiry_back(role_id: int, current_season: int) -> int:
    if is_top_10_role_id(role_id):
        return current_season - TOP_TIME
    else:
        return current_season - MEDAL_TIME


async def delete_rank(guild, time_added, user_id, rank, commits=True):
    cur.execute(
        "DELETE FROM ranks_added WHERE time_added = (?)",
        (time_added,)
    )
    if commits:
        conn.commit()  # if, for faster performance in loop
    role = guild.get_role(RANK_ID_DICT[rank])
    if role:
        await guild.get_member(user_id).remove_roles(role)


async def add_record(interaction: discord.Interaction, time_added: int, user_id: int, role_id: int, season_num: int,
                     note: str):
    await interaction.response.defer()
    cur.execute("SELECT season_num, end_timestamp FROM current_season_end")
    current_end = cur.fetchone()
    if not current_end:
        await interaction.followup.send("No current season end stored yet. Use slash command `/set_season_end`.", ephemeral=True)
        return
    c_num, end_ts = current_end
    if season_num > c_num:
        await interaction.followup.send(f"Provided season end number cannot be greater than current season number, which is: {c_num}", ephemeral=True)
        return
    if season_num < expiry_back(role_id, c_num):
        await interaction.followup.send(f"Provided season end number cannot be that far in the past for that rank. Current season: {c_num}", ephemeral=True)
        return
    if datetime.now(timezone.utc) - datetime.fromtimestamp(end_ts, timezone.utc) > timedelta(weeks=SEASON_START_WEEKS):
        await interaction.followup.send("Current season end setting is out of date. Wait for bot to auto-update it (preferred, as it can auto-delete ranks too) or use slash command `/set_season_end`.", ephemeral=True)
        return
    if season_num == c_num:
        if is_top_10_role_id(role_id) and datetime.fromtimestamp(end_ts, timezone.utc) - datetime.now(timezone.utc) > timedelta(seconds=0.0):
            await interaction.followup.send("Cannot grant Top 10 role for current season before season end.", ephemeral=True)
            return
        if datetime.fromtimestamp(end_ts, timezone.utc) - datetime.now(timezone.utc) > timedelta(weeks=SEASON_END_WEEKS):
            season_num -= 1
            await interaction.followup.send("Note: since it's mid-season, the current season will be recorded as the previous season.", ephemeral=True)

    cur.execute(
        "SELECT rank, season_num FROM ranks_added WHERE user_id = (?)",
        (user_id,)
    )
    user_entries = sorted(cur.fetchall(), key=lambda pair: (height(pair[0]), expiry(pair[0], pair[1])), reverse=True)
    rank_to_add = RANK_DICT[role_id]
    user = interaction.guild.get_member(user_id)

    async def add_role(r_id):
        await user.add_roles(interaction.guild.get_role(r_id))
        cur.execute(
            "INSERT INTO ranks_added (time_added, user_id, rank, season_num, note) VALUES (?, ?, ?, ?, ?)",
            (time_added, user_id, rank_to_add, season_num, note)
        )
        conn.commit()

    confirm_str = ""
    if not user_entries:
        await add_role(role_id)
        confirm_str = f"{rank_to_add} rank granted!\n"
    else:
        for rank, season_num in user_entries:
            h_a = height(rank_to_add)
            h = height(rank)
            e_a = expiry(rank_to_add, season_num)
            e = expiry(rank, season_num)
            if h_a <= h and e_a <= e:
                if not confirm_str:
                    confirm_str = f"{rank_to_add} rank NOT granted, redundant...\n"
                break  # this is why user_entries is reverse sorted
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
                if not confirm_str:
                    confirm_str = f"{rank_to_add} rank granted!\n"
                confirm_str += f"Redundant {rank} rank also removed.\n"
            elif h_a > h and e_a < e or h_a < h and e_a > e:
                await add_role(role_id)
                if not confirm_str:
                    confirm_str = f"{rank_to_add} rank granted!\n"

    cur.execute(
        "SELECT rank, season_num, note FROM ranks_added WHERE user_id = (?)",
        (user_id,)
    )
    entries = cur.fetchall()
    info_str = ""
    for entry in entries:
        r, s_n, n = entry
        info_str += f"\n\nRank: {r}\nExpires: {expiry(r, s_n)}\nNote: {n}"

    await interaction.followup.send(
        f"{confirm_str}User's ranks recorded:\n\nUser: {interaction.guild.get_member(user_id).display_name}\n{info_str}",
        ephemeral=True)


class NoteTakeModal(discord.ui.Modal):
    def __init__(self, view, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.view = view
        self.add_item(discord.ui.TextInput(label="Add user note", placeholder="Can be anything", max_length=50))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.set_note(self.children[0].value)


def season_select_options() -> list[discord.SelectOption]:
    cur.execute("SELECT season_num FROM current_season_end")
    current_end = cur.fetchone()
    if not current_end:
        return [discord.SelectOption(label="No current season set", value="0")]
    season_num = current_end[0]
    return [discord.SelectOption(label=str(season_num), default=True)] + [
        discord.SelectOption(label=str(season_num - x))
        for x in range(1, TOP_TIME + 1)]


class GrantRankView(discord.ui.View):
    def __init__(self, user: discord.Member, role_id: int) -> None:
        super().__init__()
        self.time_added = int(datetime.timestamp(datetime.now(timezone.utc)))
        self.user = user
        self.seasonNum = 0
        self.role_id = role_id
        self.note = ""

        self.select = discord.ui.Select(
            row=0,
            options=season_select_options(),
            min_values=1,
            max_values=1,
            placeholder="Select season end (mid-season = previous season)"
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    def set_note(self, note):
        self.note = note

    async def select_callback(self, interaction):
        await interaction.response.defer()
        self.seasonNum = int(self.select.values[0])

    @discord.ui.button(
        row=1,
        label="Submit",
        style=discord.ButtonStyle.primary
    )
    async def button_callback_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await add_record(interaction, self.time_added, self.user.id, self.role_id, self.seasonNum, self.note)

    @discord.ui.button(
        row=1,
        label="Add note",
        style=discord.ButtonStyle.secondary
    )
    async def button_callback_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoteTakeModal(self, title="Miscellaneous Note"))


class DeleteRanksModal(discord.ui.Modal):
    def __init__(self, row_list, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.row_list = row_list
        self.add_item(discord.ui.TextInput(label="Enter # index of record(s) to delete",
                                           placeholder="Number for single deletion, or #-# for range", max_length=50))

    async def on_submit(self, interaction: discord.Interaction):
        index1, index2 = re.search(r"(\d+)(-\d+)?", self.children[0].value).groups()
        if index1 and index2:
            server_comm_ch = interaction.guild.get_channel_or_thread(SERVER_COMM_CH)
            if not server_comm_ch:
                await interaction.response.send_message("Error: SERVER_COMM_CH not found", ephemeral=True)
                return
            i1, i2 = int(index1) - 1, int(index2[1:]) - 1
            if i1 >= i2:
                await interaction.response.send_message("Invalid range provided", ephemeral=True)
            row_range = self.row_list[i1:i2 + 1]
            if interaction.guild.get_role(MOD_ROLE_ID) not in interaction.user.roles:
                for row in row_range:
                    if datetime.now(timezone.utc) - datetime.fromtimestamp(row[0], timezone.utc) > timedelta(hours=24):
                        await interaction.response.send_message(
                            "Need Mod role to delete any entries older than 24 hours", ephemeral=True)
                        return
            for row in row_range:
                cur.execute(
                    "SELECT FROM ranks_added WHERE time_added = (?)",
                    (row[0],)
                )
                user_id = cur.fetchone()[1]
                await delete_rank(interaction.guild, row[0], user_id, row[2], False)
            conn.commit()
            with open(deleted_ranks_path, 'r+') as deleted_ranks: #TODO
                deleted_ranks.write(HEADER_LINE)
                for index, row in enumerate(row_range):
                    _, name, rank, num, note = row
                    deleted_ranks.write(line_to_write(index, name, rank, num, note))
                await server_comm_ch.send(content="Deleted the following records:", file=discord.File(deleted_ranks_path))
            await interaction.response.send_message(
                f"Deleted {len(row_range)} records. Check {server_comm_ch.mention} for trace.",
                ephemeral=True)
        elif index1:
            i1 = int(index1) - 1
            time_added, name, rank, num, note = self.row_list[i1]
            cur.execute(
                "SELECT FROM ranks_added WHERE time_added = (?)",
                (time_added,)
            )
            user_id = cur.fetchone()[1]
            await delete_rank(interaction.guild, time_added, user_id, rank)
            await interaction.response.send_message(
                f"Deleted 1 record.\n\n{HEADER_LINE}\n{line_to_write(i1, name, rank, num, note)}",
                ephemeral=True)
        else:
            await interaction.response.send_message("No number(s) provided", ephemeral=True)


class ShowRanksView(discord.ui.View):
    def __init__(self, row_list: list):
        super().__init__()
        self.row_list = row_list

    @discord.ui.button(
        label="Delete Rows",
        style=discord.ButtonStyle.secondary
    )
    async def button_callback(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(DeleteRanksModal(self.row_list, title="Delete Records"))


# Commands


@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.context_menu(name="Bestow Top 10")
async def grant_top_10(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(view=GrantRankView(user, RANK_ID_DICT[RANK_LIST[0]]), ephemeral=True)


tree.add_command(grant_top_10)


# Alternative to fancier options
@tree.command(description="Grants rank with accounting for time. Includes #1 ranks")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(
    user_id='ID of member to grant rank to (enable developer tools and right-click user -> copy ID)',
    rank='Rank to grant member',
    season_num='Which number season end (mid-season = previous season)',
    note='Miscellaneous note to attach to this record'
)
@app_commands.choices(rank=RANK_CHOICES)
async def grant_rank(interaction: discord.Interaction, user_id: str, rank: app_commands.Choice[str], season_num: int,
                     note: Optional[str] = ""): #TODO allow username use
    try:
        user = interaction.guild.get_member(int(user_id))
        if not user:
            await interaction.response.send_message("Must provide valid user_id", ephemeral=True)
            return
    except ValueError:
        await interaction.response.send_message("Must provide valid user_id", ephemeral=True)
        return

    time_added = int(datetime.timestamp(datetime.now(timezone.utc)))
    await add_record(interaction, time_added, int(user_id), int(rank.value), season_num, note)


@tree.command(description="Show current season end date and time")
async def get_season_end(interaction: discord.Interaction):
    cur.execute(
        "SELECT season_num, end_timestamp FROM current_season_end WHERE guild_id = (?)",
        (interaction.guild_id,)
    )
    current_end = cur.fetchone()
    if not current_end:
        await interaction.response.send_message(f"No season end setting found for {interaction.guild.name}")
        return
    season_num, end_ts = current_end
    end_datetime = datetime.fromtimestamp(end_ts, timezone.utc)
    await interaction.response.send_message(f"Current season set to S{season_num}, end set to {datetime.strftime(end_datetime, TIME_FORMAT)} UTC")


OVERRIDE_CODE = "beamdog"


@tree.command(description="Edit current season end date and time")
@app_commands.checks.has_any_role(MOD_ROLE_ID, BEAMDOG_ROLE_ID)
@app_commands.describe(
    season_num='Current number season whose end is coming up',
    end_date_time='Day and time (UTC) of season end in "YYYY/MM/DD hh:mm" (24hr) format',
    override_code=f'Code to insist on an unexpected season change. Value to enter: {OVERRIDE_CODE}'
)
async def set_season_end(interaction: discord.Interaction, season_num: int, end_date_time: str, override_code: Optional[str] = None):
    try:
        g_id = interaction.guild_id
        end_datetime = datetime.strptime(end_date_time, TIME_FORMAT).replace(tzinfo=timezone.utc)
        end_timestamp = int(datetime.timestamp(end_datetime))

        server_comm_ch = interaction.guild.get_channel_or_thread(SERVER_COMM_CH)
        if not server_comm_ch:
            await interaction.response.send_message("Error: SERVER_COMM_CH not found", ephemeral=True)
            return
        cur.execute(
            "SELECT season_num, end_timestamp FROM current_season_end WHERE guild_id = (?)",
            (g_id,)
        )
        current_end = cur.fetchone()
        if current_end:
            c_num, end_ts = current_end
            if override_code != OVERRIDE_CODE:
                if timedelta(seconds=0.0) < datetime.now(timezone.utc) - datetime.fromtimestamp(end_ts, timezone.utc) < timedelta(weeks=SEASON_START_WEEKS):
                    await interaction.response.send_message(
                        f"Too early to update season. Wait until grace period of {SEASON_START_WEEKS} weeks is over, or use override code.",
                        ephemeral=True)
                    return
                if not (season_num == c_num or season_num == c_num + 1):
                    await interaction.response.send_message(
                        "Season number is neither this season nor next -- typo? Use override code if intended.",
                        ephemeral=True)
                    return
                if datetime.fromtimestamp(end_timestamp, timezone.utc) - datetime.now(timezone.utc) < timedelta(
                        seconds=0.0):
                    await interaction.response.send_message(
                        "End datetime provided is in the past -- typo? Use override code if intended.",
                        ephemeral=True)
                    return

        cur.execute(
            "INSERT OR REPLACE INTO current_season_end (guild_id, season_num, end_timestamp) VALUES (?, ?, ?)",
            (g_id, season_num, end_timestamp)
        )
        conn.commit()
        if not auto_update_season.is_running():
            auto_update_season.start()
        await server_comm_ch.send(
            f"Current season set to S{season_num}, end set to {datetime.strftime(end_datetime, TIME_FORMAT)} UTC")
        await interaction.response.send_message(f"Successfully set season end. See {server_comm_ch.mention}", ephemeral=True)

    except ValueError:
        await interaction.response.send_message("Invalid datetime provided, please check format", ephemeral=True)


def flip_season(end_ts):
    month_flip = {2: 8, 8: 2}  # Alternate between Feb and Aug
    c_dt = datetime.fromtimestamp(end_ts, timezone.utc)
    if c_dt.day > 28:
        raise ValueError("Day is set higher than 28, which will fail for February.")
    new_year = c_dt.year
    new_month = month_flip[c_dt.month]
    if new_month == 2:
        new_year += 1
    new_dt = c_dt.replace(year=new_year, month=new_month)
    return int(datetime.timestamp(new_dt))


@tasks.loop(minutes=30.0)
async def auto_update_season():
    cur.execute("SELECT guild_id, season_num, end_timestamp FROM current_season_end")
    current_ends = cur.fetchall()
    if not current_ends:
        return
    for current_end in current_ends:
        g_id, c_num, end_ts = current_end
        guild = bot.get_guild(g_id)

        if datetime.now(timezone.utc) - datetime.fromtimestamp(end_ts, timezone.utc) > timedelta(weeks=SEASON_START_WEEKS):
            server_comm_ch = guild.get_channel_or_thread(SERVER_COMM_CH)
            if not server_comm_ch:
                print(f"In auto_update_season(): SERVER_COMM_CH not found for guild: {guild.name}")
                return
            with open(deleted_ranks_path, 'r+') as deleted_ranks: #TODO
                deleted_ranks.write(HEADER_LINE)

                cur.execute("SELECT time_added, user_id, rank, season_num, note FROM ranks_added")
                row_list = [row for row in cur.fetchall()]
                row_list.sort(key=lambda tup: (tup[3], tup[0]))
                for index, row in enumerate(row_list):
                    time_added, user_id, rank, num, note = row
                    if num < expiry_back(RANK_ID_DICT[rank], c_num + 1):
                        deleted_ranks.write(line_to_write(index, guild.get_member(user_id).name, rank, expiry(rank, num), note))
                        await delete_rank(guild, time_added, user_id, rank, False)
                conn.commit()
            try:
                cur.execute(
                    "REPLACE INTO current_season_end (guild_id, season_num, end_timestamp) VALUES (?, ?, ?)",
                    (g_id, c_num + 1, flip_season(end_ts))
                )
                conn.commit()
                await server_comm_ch.send("Auto-updated current season to S{season_num}, end set to {datetime.strftime(end_datetime, TIME_FORMAT)} UTC\nDeleted ranks:", file=discord.File(deleted_ranks_path))
            except ValueError as e:
                await server_comm_ch.send(f"{guild.get_role(MOD_ROLE_ID).mention} Error updating season end: ValueError: {e}\n\nUse slash command `/set_season_end` to manually update it.")
                auto_update_season.stop()


@auto_update_season.before_loop
async def before_auto_update_season():
    await bot.wait_until_ready()


@tree.command(description="Lists users in the ranks database, oldest first")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
async def show_user_ranks(interaction: discord.Interaction):
    with open(show_ranks_path, 'r+') as show_ranks: #TODO
        show_ranks.write(HEADER_LINE)
        cur.execute("SELECT time_added, user_id, rank, season_num, note FROM ranks_added")
        row_list = []
        for row in cur.fetchall():
            time_added, user_id, rank, num, note = row
            row_list.append([time_added, interaction.guild.get_member(user_id).name, rank, num, note])

        row_list.sort(key=lambda ls: (expiry(ls[2], ls[3]), ls[0]))
        for index, row in enumerate(row_list):
            _, name, rank, num, note = row
            show_ranks.write(line_to_write(index, name, rank, num, note))

        await interaction.response.send_message(f"Ranks stored in database, sorted by earliest expiration first. Expiry is Season +{MEDAL_TIME} if normal, +{TOP_TIME} if Top 10 type.",
                                                file=discord.File(show_ranks_path), view=ShowRanksView(row_list))


async def rank_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.member.get_role(STAFF_ROLE_ID):
        guild = bot.get_guild(payload.guild_id)
        author = guild.get_member(payload.message_author_id)
        msg = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
        rank_react = [react for react in msg.reactions if react.emoji.id == payload.emoji.id][0]
        staff_msg = f"{payload.member.mention} Select a season end for grant rank to user: {author.display_name}"
        if [user async for user in rank_react.users() if user.get_role(STAFF_ROLE_ID) and user.id != payload.member.id]:
            staff_msg = f"{payload.member.mention} A Staff member has already reacted to this post for user: {payload.member.display_name}"
        await guild.get_channel(SERVER_COMM_CH).send(content=staff_msg, view=GrantRankView(author, RANK_ID_DICT[
            REACTION_DICT[payload.emoji.id]]))
