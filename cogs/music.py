import discord
from discord.ext.pages import Paginator
import asyncio
from yt_dlp import YoutubeDL
from discord import ApplicationContext
import time

TIMEOUT = 300

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
                self.sort_data(data)
        except:
            raise discord.ApplicationCommandError("Invalid URL")

    def create_embed(self) -> discord.Embed:
        embed = (discord.Embed(title=self.title,
                                    url=self.video_url)
                 .set_author(name=self.uploader, url=self.uploader_url)
                 .set_image(url=self.thumbnail)
                 .add_field(name='Duration', value=f"{self.duration}s"))
        return embed
        
    def sort_data(self, data: dict):
        if data.get("entries"):
            data = data["entries"][0]

        self.title = data["title"]
        self.video_url = data["webpage_url"]
        self.uploader = data["uploader"]
        self.uploader_url = data["uploader_url"]
        self.thumbnail = data["thumbnail"]
        self.duration = data["duration"]
        self.url = data["url"]
        self.start_time = data.get("start_time") # Not always

class VoiceState:
    def __init__(self, bot: discord.Bot):
        self.volume = 0.5
        self.loop = False
        self.queue = asyncio.Queue()
        self.voice = None
        self.ctx = None

        self.next = asyncio.Event()
        self.events = []
        self.current = None
        self.player = bot.loop.create_task(self.audio_player_task())

    @property
    def is_playing(self):
        return self.voice.is_paused() or self.voice.is_playing()

    def after(self, arg):
        self.next.set()

    async def audio_player_task(self):
        while True:
            if not self.loop:
                try:
                    async with asyncio.timeout(TIMEOUT):
                        self.current = await self.queue.get()
                except asyncio.TimeoutError:
                    self.queue = asyncio.Queue()
                    await self.voice.disconnect()

            self.next.clear()
            self.events = [time.time()]

            embed = self.current.create_embed()
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

    # async def cog_command_error(self, ctx: ApplicationContext, error: Exception):
    #     if str(error) == "Application Command raised an exception: AttributeError: 'NoneType' object has no attribute 'channel'":
    #         error = "Bot is not currently in use"
    #     embed = discord.Embed(title='Error', description=error)
    #     await ctx.respond(embed=embed)

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

    @discord.command(name="skip")
    async def _skip(self, ctx: ApplicationContext):
        destination = ctx.author.voice.channel
        if destination != ctx.voice_state.voice.channel:
            raise discord.ApplicationCommandError("You must be in same voice channel as bot to use this command")            

        ctx.voice_state.voice.stop()

        embed = ctx.voice_state.current.create_embed()
        embed.set_footer(text="Skipped")
        await ctx.respond(embed=embed)
 
    @discord.command(name="volume")
    @discord.option("value", description="Volume value", min_value=0, max_value=2, required=True)
    async def _volume(self, ctx: ApplicationContext, value: int):
        voice_state = self.get_voice_state(ctx)
        voice_state.volume = value

    @discord.command(name="loop")
    async def _loop(self, ctx: ApplicationContext):
        await self.check(ctx)

        embed = ctx.voice_state.current.create_embed()
        if ctx.voice_state.loop: # => no longer looped
            embed.set_footer(text="No longer looping")
        else:
            embed.set_footer(text="Now looping")
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.respond(embed=embed)

    @discord.command(name="progress")
    async def _progress(self, ctx: ApplicationContext):
        await self.check(ctx)
        events = ctx.voice_state.events
        
        # idek stolen from chat-gpt
        total = 0
        for i in range(0, len(events), 2):
            start_time = events[i]
            end_time = events[i+1] if i+1 < len(events) else time.time()
            total += end_time - start_time

        embed = ctx.voice_state.current.create_embed()
        diff = int(total/ctx.voice_state.current.duration*10)
        embed.description = "⬜"*diff+"⬛"*(10-diff)
        embed.set_footer(text=f"Currently playing | 1/{ctx.voice_state.queue.qsize()+1}")

        await ctx.respond(embed=embed)
    @discord.command(name="current")
    async def _current(self, ctx: ApplicationContext):
        await self._progress(ctx)
    @discord.command(name="duration")
    async def _duration(self, ctx: ApplicationContext):
        await self._progress(ctx)

    @discord.command(name="queue")
    async def _queue(self, ctx: ApplicationContext):
        await self.check(ctx)
        queue = ctx.voice_state.queue._queue

        pages = [(ctx.voice_state.current.create_embed()
                 .set_footer(text=f"Currently playing | 1/{len(queue)+1}"))]
        
        for num, song in enumerate(list(queue)):
            pages.append((song.create_embed()
                          .set_footer(text=f"{num+2}/{len(queue)+1}")))
       
        paginator = Paginator(pages=pages)
        await paginator.respond(ctx.interaction, ephemeral=False)
    @discord.command(name="list")
    async def _list(self, ctx):
        await self._queue(ctx)

    @discord.command(name="pause")
    async def _pause(self, ctx: ApplicationContext):
        await self.check(ctx)
        voice = ctx.voice_state.voice

        ctx.voice_state.events.append(time.time())

        embed = ctx.voice_state.current.embed
        if voice.is_paused():
            voice.resume()
            embed.set_footer(text="Now playing")
        else:
            voice.pause()
            embed.set_footer(text="Now paused")
        await ctx.respond(embed=embed)
    @discord.command(name="resume")
    async def _resume(self, ctx: ApplicationContext):
        await self._pause(ctx)

    @discord.command(name="play")
    @discord.option("search", description="Search for song", required=True)
    async def _play(self, ctx: ApplicationContext, search: str):
        start = time.perf_counter()
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