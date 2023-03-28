import discord
from discord import ApplicationContext, ApplicationCommandError

class Settings(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
    

def setup(bot: discord.Bot):
    bot.add_cog(Settings(bot))