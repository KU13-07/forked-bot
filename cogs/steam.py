import discord
from discord import ApplicationContext, ApplicationCommandError

MARKET_BASE = 0.01
MARKET_RATE = 1.15

class Steam(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.command(name="profit")
    @discord.option(name="buy", description="Value you intend to purchase at")
    @discord.option(name="sell", description="Value you intend to sell at")
    async def _profit(self, ctx: ApplicationContext, buy: float=0, sell: float=0):
        def form(float):
            return format(float, '.2f')
        def into_sell(buy):
            return form(buy*MARKET_RATE+MARKET_BASE)
        def into_buy(sell):
            return form(sell/MARKET_RATE+MARKET_BASE)
        
        profit = sell-(into_sell)
        embed = (discord.Embed(title="Steam", color=0x007bff)
                 .add_field(name="Buy value:", value=f"${form(buy)}")
                 .add_field(name="Sell value:", value=f"${form(sell)}")
                 .add_field(name="Profit:", value=f"${form(profit)}"))
        
        # If profit != 0 then only one value provided
        if profit > 0:
            embed.color = 0x00ff00
        elif profit < 0:
            embed.color = 0xff0000
        elif buy:
            embed.set_field_at(1, name="Sell value:", value=f"${into_sell(buy)}")
        else:
            embed.set_field_at(0, name="Buy value:", value=f"${into_buy(sell)}")
        await ctx.respond(embed=embed)

    @_profit.before_invoke
    async def _before(ctx, buy, sell):
        if not (buy or sell):
            raise ApplicationCommandError("Either a buy or sell value is required")

def setup(bot: discord.Bot):
    bot.add_cog(Steam(bot))