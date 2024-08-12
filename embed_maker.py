
from params import *
from discord import app_commands


class CreateEmbedModal(discord.ui.Modal):
    def __init__(self, vals=(None,) * 5, message=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.vals = vals
        self.message = message  # only valid when editing
        self.add_item(discord.ui.TextInput(label='Title header of embed (max 256 char)', max_length=256, default=vals[0], row=0, required=False))
        self.add_item(discord.ui.TextInput(label='Body text of embed (max 4000 char)', max_length=4000, default=vals[1], row=1, style=discord.TextStyle.paragraph, required=True))
        self.add_item(discord.ui.TextInput(label='Footer text of embed (max 2048 char)', max_length=1500, default=vals[2], row=2, style=discord.TextStyle.paragraph, required=False))  # Low limit to not exceed 6000 combined limit
        self.add_item(discord.ui.TextInput(label='Color of embed siding (hex code)', max_length=7, default=vals[3], row=3, required=False))
        self.add_item(discord.ui.TextInput(label='Large image below body (url to image)', default=vals[4], row=4, required=False))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async def hex_str_to_int(hex_str: str):  # Helper function for color parameter
            if not hex_str:
                return 0
            hex_str = hex_str.strip().strip("#")
            for c in hex_str:
                if c not in "0123456789abcdefABCDEF":  # characters that are valid in hexadecimal
                    await interaction.followup.send("Color must be provided as valid hex code.", ephemeral=True)
                    return 0
            return int(hex_str, 16)

        title = self.children[0].value
        description = self.children[1].value
        footer = self.children[2].value
        color = await hex_str_to_int(self.children[3].value)
        image = self.children[4].value
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=footer)
        embed.set_image(url=image)
        if self.message:
            await self.message.edit(embed=embed)
        else:
            await interaction.channel.send(embed=embed)


"""
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
async def write_embed(interaction: discord.Interaction, title: str, description: str, footer: Optional[str] = None,
                      color: Optional[str] = None, image: Optional[str] = None):
    async def hex_str_to_int(hex_str: str):  # Helper function for color parameter
        hex_str = hex_str.strip().strip("#")
        for c in hex_str:
            if c not in "0123456789abcdefABCDEF":  # characters that are valid in hexadecimal
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
    if image: embed.set_image(image)  # Note: have not added url validation for the image

    target_msg = interaction.message.reference
    content = interaction.message.content
    if target_msg and target_msg.author == bot.user:
        await target_msg.edit(embed=embed)
        if content:
            if re.match('^\s\s?$', content):
                await interaction.response.send_message(
                    "To help prevent accidental erasures, at least 3 spaces are required to delete non-embed message content.",
                    ephemeral=True)
            elif re.match('^\s\s\s+$', content):
                await target_msg.edit(content=None)
            else:
                await target_msg.edit(content=content)

    else:
        await interaction.response.send_message(content=content, embed=embed)
"""


@tree.command(description="Create and send embed")
@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
async def create_embed(interaction: discord.Interaction):
    await interaction.response.send_modal(CreateEmbedModal(title="Enter values for embed fields"))


@app_commands.checks.has_role(STAFF_ROLE_ID)
@app_commands.checks.bot_has_permissions(send_messages=True)
@app_commands.context_menu(name="Edit embed")
async def edit_embed(interaction: discord.Interaction, message: discord.Message):
    if message.author != bot.user:
        await interaction.response.send_message("Cannot edit message not sent by the same bot.", ephemeral=True)
        return
    if len(message.embeds) > 1:
        await interaction.response.send_message("Not sure how the bot sent a message with multiple embeds, but this can't edit it.", ephemeral=True)
        return
    elif len(message.embeds) < 1:
        await interaction.response.send_message("Message does not contain an embed.", ephemeral=True)
        return
    else:
        embed = message.embeds[0]
        title = embed.title
        description = embed.description
        footer = embed.footer.text
        color = f'{embed.color.value:06x}'
        image = embed.image.url
        await interaction.response.send_modal(CreateEmbedModal(title="Edit values for embed fields", vals=(title, description, footer, color, image), message=message))


tree.add_command(edit_embed)


