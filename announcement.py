import discord.errors

from params import *
from discord import app_commands
from discord.utils import escape_mentions
from dotenv import load_dotenv

load_dotenv()

# Create and announcement and allow for it to be edited by any STAFF or BEAMDOG @spellignerror 11Jan2025
class CreateAnnouncementModal(discord.ui.Modal):
    def __init__(self, message=None, *args, **kwargs) -> None:
        kwargs['title'] = "Enter content for announcement"
        super().__init__(*args, **kwargs)
        self.message = message if message else None  # only valid when editing
        self.add_item(discord.ui.TextInput(label='Announcement content (max 4000 characters):', default=message.content if message else None, required=True))
        self.add_item(discord.ui.TextInput(label='Allow pings? "I WANT PAIN" to allow pings', default='I am normal', required=False))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        pings = self.children[1].value

        if pings == "I WANT PAIN":
            content = self.children[0].value
        else:
            content = escape_mentions(self.children[0].value)
        content_abridged = content[:3900]  # This allows for user mention so we don't run into errors with *very* long announcements not getting logged properly

        # Try to send the embed and responsible user.mention to the log channel
        log_channel = bot.get_channel(SERVER_COMM_CH)
        try:
            if self.message:
                await log_channel.send(f"{interaction.user} edited the following announcement:\n\n" + content_abridged)
                await self.message.edit(content=content)
            else:
                await log_channel.send(f"{interaction.user} sent the following announcement:\n\n" + content_abridged)
                announcement_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL)
                await announcement_channel.send(content=content)
        except discord.errors.Any as e:
            print("ERROR in announcement.py CreateAnnouncementModal on_submit\n", e)
            await interaction.followup.send("HTTP error: check image url", ephemeral=True)


@tree.command(description="Create an announcement with AAOHelper")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(send_messages=True)
async def announcement(interaction: discord.Interaction):
    await interaction.response.send_modal(CreateAnnouncementModal())


@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.context_menu(name="Edit message")
async def edit_announcement(interaction: discord.Interaction, message: discord.Message):
    if interaction.channel.id == SERVER_COMM_CH:
        await interaction.response.send_message(f"Cannot edit these log messages... BAD TROLL!", ephemeral=True)
    if message.author != bot.user:
        await interaction.response.send_message("Cannot edit message not sent by the same bot.", ephemeral=True)
        return
    if len(message.embeds) > 0:
        await interaction.response.send_message(
            "Not sure how the bot sent a message with embeds, but this can't edit it.", ephemeral=True)
        return
    else:
        await interaction.response.send_modal(CreateAnnouncementModal(message=message))


tree.add_command(edit_announcement)