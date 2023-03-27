import discord
from discord import ApplicationContext, ApplicationCommandError

class Steam(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
    

    async def cog_command_error(self, ctx: ApplicationContext, error: Exception):
        embed = discord.Embed(title='Error', description=error)
        await ctx.respond(embed=embed)

    @discord.command(name="profit")
    @discord.option(name="buy", description="Value you intend to purchase at")
    @discord.option(name="sell", description="Value you intend to sell at")
    async def _profit(self, ctx: ApplicationContext, buy: float=0, sell: float=0):
        if not (buy or sell):
            raise ApplicationCommandError("Either a buy or sell value is required")

        profit = sell-(buy*1.15+0.01)
        embed = (discord.Embed(title="Steam", color=0x007bff)
                 .add_field(name="Buy value:", value=f"${format(buy, '.2f')}")
                 .add_field(name="Sell value:", value=f"${format(sell, '.2f')}")
                 .add_field(name="Profit:", value=f"${format(profit, '.2f')}"))
        if buy and sell:
            if profit > 0:
                embed.color = 0x00ff00
            elif profit < 0:
                embed.color = 0xff0000
        else:
            embed.set_field_at(2, name="Profit:", value="$0.00")
            if buy:
                embed.set_field_at(1, name="Sell value:", value=f"${format(buy*1.15+0.01, '.2f')}")
            else:
                embed.set_field_at(0, name="Buy value:", value=f"${format(sell/1.15-0.01, '.2f')}")
        await ctx.respond(embed=embed)

def setup(bot: discord.Bot):
    bot.add_cog(Steam(bot))