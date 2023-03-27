import discord
from discord.ext.pages import Paginator
import asyncio
from yt_dlp import YoutubeDL
from discord import ApplicationContext

class Source():
    YDL_OPTS = {
        "format": "bestaudio/best",
        "default_search": "auto",
        "quiet": True,
        "noplaylist": True
    }

    def __init__(self, ctx: ApplicationContext, search: str):
        try:
            with YoutubeDL(self.YDL_OPTS) as ydl:
                data = ydl.extract_info(search, download=False)
        except:
            raise discord.ApplicationCommandError("Invalid URL")

        if data.get("entries"):
            data = data["entries"][0]

        self.title = data.get("title")
        self.url = data.get("webpage_url")
        self.uploader = data.get("uploader")
        self.uploader_url = data.get("uploader_url")
        self.thumbnail = data.get("thumbnail")
        self.duration = data.get("duration")
        self.url = data.get("url")
        self.start_time = data.get("start_time") # Not always

        self.embed = discord.Embed(title=self.title, url=self.url)
        self.embed.set_author(name=self.uploader, url=self.uploader_url)
        self.embed.set_image(url=self.thumbnail)

class VoiceState:
    def __init__(self, bot: discord.Bot):
        self.volume = 0.5
        self.loop = False
        self.queue = asyncio.Queue()
        self.voice = None
        self.ctx = None

        self.next = asyncio.Event()
        self.current = None
        self.player = bot.loop.create_task(self.audio_player_task())
    
    @property
    def is_playing(self):
        return bool(self.current)

    def after(self, arg):
        self.next.set()

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                self.current = await self.queue.get()

            embed = self.current.embed
            embed.set_footer(text="Now playing")

            source = discord.FFmpegPCMAudio(self.current.url)
            new_source = discord.PCMVolumeTransformer(source, self.volume)

            self.voice.play(new_source, after=self.after)

            await self.ctx.respond(embed=embed)

            await self.next.wait() 

class Music(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    async def cog_command_error(self, ctx: ApplicationContext, error: Exception):
        if str(error) == "Application Command raised an exception: AttributeError: 'NoneType' object has no attribute 'channel'":
            error = "Bot is not currently in use"
        embed = discord.Embed(title='Error', description=error)
        await ctx.respond(embed=embed)

    def get_voice_state(self, ctx: ApplicationContext):
        voice_state = self.voice_states.get(ctx.guild_id)
        if not voice_state:
            voice_state = VoiceState(self.bot)
            self.voice_states[ctx.guild_id] = voice_state
        return voice_state

    # Runs before every command
    async def cog_before_invoke(self, ctx: ApplicationContext):
        ctx.voice_state = self.get_voice_state(ctx)

    # Stand checks
    async def connect(self, ctx: ApplicationContext):
        voice = ctx.author.voice

        if not voice:
            raise discord.ApplicationCommandError("User must be in a voice channel to use this command") 

        if ctx.voice_state.voice:
            if ctx.voice_state.voice.is_connected():
                if ctx.voice_state.is_playing:
                    if ctx.voice_state.voice.channel != voice.channel:
                        raise discord.ApplicationCommandError(
                            'Bot in use')
                    else:
                        return
            await ctx.voice_state.voice.move_to(voice.channel)
        else:
            ctx.voice_state.voice = await voice.channel.connect()
    async def check(self, ctx: ApplicationContext):
        voice = ctx.author.voice

        if not voice:
            raise discord.ApplicationCommandError("User must be in a voice channel to use this command")

        if voice.channel != ctx.voice_state.voice.channel:
            raise discord.ApplicationCommandError("User must be in the same voice channel as bot to use this command")

        if not ctx.voice_state.is_playing:
            raise discord.ApplicationCommandError("The queue is empty")

    @discord.command(name="connect")
    async def _connect(self, ctx: ApplicationContext):
        await self.connect(ctx)
        embed = discord.Embed(
            title='Bot connected', description=f"Bot has connected to {ctx.author.voice.channel.mention}")
        await ctx.respond(embed=embed)
    @discord.command(name="join")
    async def _join(self, ctx):
        await self._connect(ctx)
    @discord.command(name="summon")
    async def _summon(self, ctx):
        await self._connect(ctx)

    @discord.command(name="disconnect")
    async def _disconnect(self, ctx: ApplicationContext):
        voice = ctx.author.voice

        if not ctx.voice_state.voice or not ctx.voice_state.voice.is_connected():
            raise discord.ApplicationCommandError(
                'Bot is not currently connected to a voice channel')
        await ctx.voice_state.voice.disconnect()
        embed = discord.Embed(
            title='Bot disconnected', description=f'Bot disconnected from {ctx.voice_state.voice.channel.mention}')
        await ctx.respond(embed=embed)
    @discord.command(name="leave")
    async def _leave(self, ctx):
        await self._disconnect(ctx)

    @discord.command()
    async def skip(self, ctx: ApplicationContext):
        destination = ctx.author.voice.channel
        if destination != ctx.voice_state.voice.channel:
            raise discord.ApplicationCommandError("You must be in same voice channel as bot to use this command")            

        ctx.voice_state.voice.stop()

        embed = ctx.voice_state.current.embed
        embed.set_footer(text="Skipped")
        await ctx.respond(embed=embed)
 
    @discord.command()
    @discord.option("value", description="Volume value", min_value=0, max_value=2, required=True)
    async def volume(self, ctx: ApplicationContext, value: int):
        voice_state = self.get_voice_state(ctx)
        voice_state.volume = value

    @discord.command()
    async def loop(self, ctx: ApplicationContext):
        await self.check(ctx)

        embed = ctx.voice_state.current.embed
        if ctx.voice_state.loop: # => no longer looped
            embed.set_footer(text="No longer looping")
        else:
            embed.set_footer(text="Now looping")
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.respond(embed=embed)
        

    @discord.command(name="queue")
    async def _queue(self, ctx: ApplicationContext):
        await self.check(ctx)
        queue = list(ctx.voice_state.queue._queue)
        for num, song in enumerate(queue):
            song.embed.set_footer(text=f"{num+2}/{len(queue)+1}")
        ctx.voice_state.current.embed.set_footer(text=f"Currently playing | 1/{len(queue)+1}")
        queue = [ctx.voice_state.current] + queue

        paginator = Paginator(pages=[source.embed for source in queue])
        await paginator.respond(ctx.interaction, ephemeral=False)
    @discord.command(name="list")
    async def _list(self, ctx):
        await self._queue(ctx)

    @discord.command(name="pause")
    async def _pause(self, ctx: ApplicationContext):
        await self.check(ctx)
        voice = ctx.voice_state.voice

        if voice.is_paused():
            voice.resume()
        else:
            voice.pause()
    @discord.command(name="resume")
    async def _resume(self, ctx: ApplicationContext):
        await self._pause(ctx)

    @discord.command(name="play")
    @discord.option("search", description="Search for song", required=True)
    async def _play(self, ctx: ApplicationContext, search: str):
        await self.connect(ctx)
        await ctx.defer()

        source = Source(ctx, search)
        ctx.voice_state.ctx = ctx

        if ctx.voice_state.is_playing:
            queue_size = ctx.voice_state.queue.qsize()+2

            embed = source.embed
            embed.set_footer(text=f"Added to queue {queue_size}/{queue_size}")
            await ctx.respond(embed=embed)
        await ctx.voice_state.queue.put(source)

    @discord.command(name="stop")
    async def _stop(self, ctx: ApplicationContext):
        await self.check(ctx)
        q_size = ctx.voice_state.queue.qsize()+1
        text = "songs" if q_size != 1 else "song"
        embed = discord.Embed(title="Queue cleared", description=f"`{q_size}` {text} have been removed from the queue")
        ctx.voice_state.queue = asyncio.Queue()
        ctx.voice_state.voice.stop()
        await ctx.respond(embed=embed)
    @discord.command(name="clear")
    async def _clear(self, ctx):
        await self._stop(ctx)
    
def setup(bot: discord.Bot):
    bot.add_cog(Music(bot))
