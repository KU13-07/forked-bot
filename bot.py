import discord
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print("Bot ready")

@bot.event
async def on_error(ctx, error):
    print(error)

if __name__ == "__main__":
    cogs = [file for file in os.listdir("cogs") if file.endswith(".py")]
    bot.load_extensions(cogs)

    print(f"{cog} loaded\n" for cog in cogs)

    bot.run(os.getenv('TOKEN'))