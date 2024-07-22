
from discord import app_commands
from typing import Optional
import re
import random

from params import *
from rank_grant import *



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