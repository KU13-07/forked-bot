import discord
from discord import ApplicationContext, ApplicationCommandError

class Pokemon(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

def setup(bot: discord.Bot):
    bot.add_cog(Pokemon(bot))