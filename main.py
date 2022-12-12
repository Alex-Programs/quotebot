import discord
from discord.ext import commands
import json
from secrets import token_urlsafe
import os
import asyncio

intents = discord.Intents.all()

with open("config.json") as f:
    config = json.load(f)

bot = commands.Bot(config["clientid"], intents=intents)

quotechannel = None
if os.path.exists("quotechannel.txt"):
    with open("quotechannel.txt", "r") as f:
        quotechannel = int(f.read())
else:
    with open("quotechannel.txt", "w") as f:
        f.write("0")


@bot.event
async def on_ready():
    print("Bot is ready")


def get_attributed_quotes(text):
    # get all subquotes in the format "quote" - author in the string
    # return a list of tuples (quote, author)
    # work on multiple quotes.
    quotes = []
    inQuote = False
    quote = ""
    author = ""
    inAuthor = False
    for index, char in enumerate(text):
        if char == '"':
            if inQuote:
                inQuote = False
            else:
                inQuote = True
                if inAuthor:
                    quotes.append((quote, author))
                    author = ""
                    inAuthor = False
                quote = ""
        elif char == "-":
            if not inQuote:
                if quote != "":
                    inAuthor = True
        elif char == " " or char == "\n":
            if inAuthor and not inQuote and len(author.strip()) > 0 and len(quote.strip()) > 0:
                inAuthor = False
                quotes.append((quote, author))
                quote = ""
                author = ""
                print("Adding at index " + str(index))

            quote += char
        else:
            if inQuote:
                quote += char
            elif inAuthor:
                author += char

    if quote != "" and author != "":
        quotes.append((quote, author))

    return quotes


print(get_attributed_quotes('this is a "quote" - author and "this is another quote" - anotherauthor'))


@bot.event
async def on_message(message):
    if message.author != bot.user and "-" in message.content:
        quotes = get_attributed_quotes(message.content)
        if len(quotes) > 0:
            for quote in quotes:
                print(quote)
                txt, author = quote

                if len(txt.strip()) < 1 or len(author.strip()) < 1:
                    print(f"Quote or author is empty: {txt}, {author}")
                    continue

                if "<@" in author:
                    author = author.replace("<@", "")
                    author = author.replace(">", "")
                    author = author.replace("!", "")
                    author = int(author)
                    guild = message.guild
                    member = guild.get_member(author)
                    author = member.name
                    if member.nick:
                        author = author + " (" + member.nick + ")"

                viewid = token_urlsafe(16)
                embed = discord.Embed(title="New quote?")
                embed.add_field(name="Quote", value=txt)
                embed.add_field(name="Author", value=author)
                newmessage = await message.channel.send(embed=embed, view=ApproveView(viewid))
                viewID_to_messageID[viewid] = newmessage.id
                viewID_to_content[viewid] = txt
                viewID_to_author[viewid] = author
                viewID_to_submitted_by[
                    viewid] = message.author.nick if message.author.nick is not None else message.author.name

    await bot.process_commands(message)


viewID_to_messageID = {}
viewID_to_content = {}
viewID_to_author = {}
viewID_to_submitted_by = {}
have_approved = []


class ApproveView(discord.ui.View):
    def __init__(self, viewid):
        self.viewid = viewid
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.viewid in have_approved:
            await interaction.response.send_message("Race condition detected - someone else has approved it!",
                                                    ephemeral=True)
            return
        have_approved.append(self.viewid)
        await interaction.response.send_message("Approved!", ephemeral=True)
        content = viewID_to_content[self.viewid]
        author = viewID_to_author[self.viewid]
        quotesChannel = bot.get_channel(quotechannel)
        embed = discord.Embed(
            title=f"Quote from {viewID_to_submitted_by[self.viewid]} about {viewID_to_author[self.viewid]}",
            description='"' + content + '" - ' + author)
        await quotesChannel.send(embed=embed)
        await bot.get_message(viewID_to_messageID[self.viewid]).delete()

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red)
    async def deny(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Removed message!", ephemeral=True)
        await bot.get_message(viewID_to_messageID[self.viewid]).delete()


@bot.slash_command(name="set-quotechannel")
async def set_quotechannel(ctx, channel: discord.TextChannel):
    quotechannel = channel.id
    with open("quotechannel.txt", "w") as f:
        f.write(str(quotechannel))
    await ctx.respond(f"Channel set to {channel.name}", ephemeral=True)


bot.run(config["token"])
