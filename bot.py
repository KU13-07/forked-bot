import discord
from dotenv import load_dotenv
import os

load_dotenv()

bot = discord.Bot()


@bot.event
async def on_ready():
    print("Bot ready")


@bot.command()
async def ping(ctx):
    await ctx.respond(f'{bot.latency}')


if __name__ == "__main__":
    bot.run(os.getenv('TOKEN'))
