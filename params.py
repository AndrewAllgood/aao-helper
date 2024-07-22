
import discord
from discord.ext import commands
import sqlite3
import os
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
    CREATE TABLE IF NOT EXISTS current_season_end (
        singleton INTEGER PRIMARY KEY,
        season_num INTEGER,
        end_timestamp INTEGER
    )
    """
)
conn.commit()



STAFF_ROLE_ID = 943827276104097842
MOD_ROLE_ID = 659883868635267075
SERVER_COMM_CH = 670090977356021780

TITLE_LIMIT = 256
DESC_LIMIT = 4096
FOOTER_LIMIT = 2048

