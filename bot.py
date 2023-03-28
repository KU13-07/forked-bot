import discord
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    print("Bot ready")

if __name__ == "__main__":
    cogs = [file for file in os.listdir("cogs") if file.endswith(".py")]
    bot.load_extensions(cogs)

    bot.run(os.getenv('TOKEN'))
