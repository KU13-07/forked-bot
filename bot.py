import discord
from discord.ext import commands
import filepaths
from datetime import datetime, date
import random
from functools import reduce
import requests
import json
import googletrans
import pickle
import asyncio
import os
from cleverbot import Cleverbot
from meme_generator import MemeGenerator
import dotenv
import os


# Load .env variables
dotenv.load_dotenv()

###########################
# Globals
###########################

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='!', intents=intents)
is_client_running = False


# asyncio locks
wolfram_alpha_chat_lock = asyncio.Lock()
cleverbot_active_chat_sessions_lock = asyncio.Lock()

###########################
# Events
###########################

@bot.event
async def on_ready():
    global is_client_running

    if not is_client_running:
        is_client_running = True
        print(f"Bot initialising...")


@bot.event
async def on_message(message):
    # Avoid the bot replying to bots
    if message.author.bot:
        return

    # Reply hello to hello messages
    if message.content.lower().startswith('hello'):
        await message.channel.send(f"Hello {message.author.mention}")
        return

    if not message.content.startswith('!'):
        return

    # Process command
    async with message.channel.typing():
        await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    # Only show the raw error output to the discord user if it is not an internal exception
    if isinstance(error, commands.CommandInvokeError):
        await ctx.send("An error occured while processing the command, but don't worry, a team of highly trained dolphins have been dispatched and are currently looking into it.")
    else:
        await ctx.send(error)

    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "command exception", type(error), error)
    raise error


###########################
# Utilities
###########################

def check_if_lucky(chance=0.5):
    def predicate(ctx):
        return random.random() < chance
    return commands.check(predicate)


def post_data_to_webhook(url, message):
    requests.post(url, data=json.dumps({'content': message}), headers={'Content-type': 'application/json'})


def create_file_if_does_not_exist(filepath, initial_value):
    if os.path.isfile(filepath):
        return

    with open(filepath, 'wb') as output:
        pickle.dump(initial_value, output)


async def send_chat_result_and_update_conversation(ctx, author_id_to_conversation, conversation):
    if 'result' in conversation:
        await ctx.send(conversation['result'])
    else:
        # WolframAlpha could not generate an answer so just return a default reply
        await ctx.send("I don't know")

    author_id_to_conversation[ctx.author.id] = (date.today(), conversation)
    with open(filepaths.WOLFRAM_ALPHA_CHAT_CONVERSATIONS, 'wb') as output:
        pickle.dump(author_id_to_conversation, output)


###########################
# Commands
###########################

@bot.command()
@commands.dm_only()
async def ping(ctx):
    await ctx.send("pong!")


@bot.command()
@commands.guild_only()
async def ding(ctx):
    await ctx.send("dong!")


@bot.command()
@commands.has_permissions(manage_webhooks=True)
async def iBeDev(ctx):
    await ctx.send("you be dev")


@bot.command()
@commands.has_any_role("admin", "moderator")
async def randomRange(ctx, a, b):
    result = random.randrange(int(a), int(b))
    await ctx.send(f"Random int in range [{a}; {b}[: **{result}**")


@bot.command()
@check_if_lucky()
async def tryMyLuck(ctx):
    await ctx.send("You're lucky pal!!!")


@bot.command(aliases=['youHaveBeenTerminated'])
@commands.is_owner()
async def terminate(ctx):
    await ctx.send("Terminating...")
    await bot.close()


@bot.command()
@commands.dm_only()
@commands.is_owner()
async def echo(ctx, *args):
    post_data_to_webhook(os.getenv('GENERAL_CHAT_WEBHOOK'), ' '.join(args))


@bot.command(aliases=['tr'])
async def translate(ctx, lang_to, *args):
    """
    Translates the given text to the language `lang_to`.
    The language translated from is automatically detected.
    """

    lang_to = lang_to.lower()
    if lang_to not in googletrans.LANGUAGES and lang_to not in googletrans.LANGCODES:
        raise commands.BadArgument("Invalid language to translate text to")

    text = ' '.join(args)
    translator = googletrans.Translator()
    text_translated = translator.translate(text, dest=lang_to).text
    await ctx.send(text_translated)


@bot.command(aliases=['wolframalpha', 'wa'])
async def oracle(ctx, *args):
    """
    Answers questions and queries using WolframAlpha's Simple API
    """

    query = '+'.join(args)
    url = f"https://api.wolframalpha.com/v1/result?appid={os.getenv('WOLFRAM_ALPHA_API_KEY')}&i={query}%3F"
    response = requests.get(url)

    if response.status_code == 501:
        await ctx.send("Unable to process that query")
        return

    await ctx.send(response.text)


@bot.command(aliases=['wolframalphachat', 'wac'])
async def wolframAlphaChat(ctx, *args):
    """
    Interactive version of the !oracle command using WolframAlpha's Conversational API.
    Previous conversations are set to expire after 24 hours.
    """

    async with wolfram_alpha_chat_lock:
        # Identify previous conversation between user and WolframAlpha server
        create_file_if_does_not_exist(filepaths.WOLFRAM_ALPHA_CHAT_CONVERSATIONS, dict())
        with open(filepaths.WOLFRAM_ALPHA_CHAT_CONVERSATIONS, 'rb') as input:
            author_id_to_conversation = pickle.load(input)
        query = '+'.join(args)

        # Resume existing conversation if exists and is not too long ago
        if ctx.author.id in author_id_to_conversation:
            last_conversation_date, last_conversation = author_id_to_conversation[ctx.author.id]
            CONVERSATION_DAYS_EXPIRE_THRESHOLD = 1
            time_delta = date.today() - last_conversation_date
            if time_delta.days < CONVERSATION_DAYS_EXPIRE_THRESHOLD:
                assert "wolframalpha.com" in last_conversation['host']
                get_request_s_parameter_addition = f"&s={last_conversation['s']}" if 's' in last_conversation else ""
                url = f"http://{last_conversation['host']}/api/v1/conversation.jsp?appid={os.getenv('WOLFRAM_ALPHA_API_KEY')}&conversationid={last_conversation['conversationID']}&i={query}%3f{get_request_s_parameter_addition}"
                response = json.loads(requests.get(url).text)
                await send_chat_result_and_update_conversation(ctx, author_id_to_conversation, response)
                return

        # Start new conversation
        url = f"http://api.wolframalpha.com/v1/conversation.jsp?appid={os.getenv('WOLFRAM_ALPHA_API_KEY')}&i={query}%3f"
        response = json.loads(requests.get(url).text)
        await send_chat_result_and_update_conversation(ctx, author_id_to_conversation, response)


@bot.command(aliases=['cleverbot', 'cleverbotChat', 'startChat'])
async def chat(ctx):
    def check_consistent_user_and_channel(message):
        return message.author == ctx.message.author and message.channel == ctx.message.channel
    STOP_SIGNAL = "_stop"

    async with cleverbot_active_chat_sessions_lock:
        create_file_if_does_not_exist(filepaths.CLEVERBOT_ACTIVE_CHAT_SESSIONS, set())
        with open(filepaths.CLEVERBOT_ACTIVE_CHAT_SESSIONS, 'rb') as input:
            author_ids_with_active_cleverbot_chat_sessions = pickle.load(input)

        # Check if user is already engaged in an active chat session
        if ctx.author.id in author_ids_with_active_cleverbot_chat_sessions:
            await ctx.send("You already have an active chat session. End it before starting a new one.")
            return

        # Init connection
        await ctx.send("Initialising chat session...")
        cleverbot = Cleverbot()
        await cleverbot.init_connection()
        await ctx.send(f"{ctx.message.author.mention} Ready to chat... Type ``{STOP_SIGNAL}`` to stop the active chat session.")

        # Update active chat sessions file
        author_ids_with_active_cleverbot_chat_sessions.add(ctx.author.id)
        with open(filepaths.CLEVERBOT_ACTIVE_CHAT_SESSIONS, 'wb') as output:
            pickle.dump(author_ids_with_active_cleverbot_chat_sessions, output)

    ### Active session ###
    is_chat_active = True
    while is_chat_active:
        try:
            # Wait for next chat message from user
            message = await bot.wait_for("message", check=check_consistent_user_and_channel, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.message.author.mention} Took too long to receive a reply. Ending chat session...")
            is_chat_active = False
        else:
            # Check for stop signal and intermediate commands, otherwise proceed with conversation
            if message.content == STOP_SIGNAL:
                await ctx.send(f"{ctx.message.author.mention} Until next time. Ending chat session...")
                is_chat_active = False
            elif message.content.startswith("!"):
                pass
            else:
                await ctx.trigger_typing()
                response = await cleverbot.get_response(message.content)
                if response.strip() == "":
                    # If could not fetch a cleverbot response then end the chat session
                    await ctx.send("I'm done talking. Ending chat session...")
                    is_chat_active = False
                else:
                    await ctx.send(response)

    # Terminate connection and update active chat sessions file
    await cleverbot.close()
    async with cleverbot_active_chat_sessions_lock:
        with open(filepaths.CLEVERBOT_ACTIVE_CHAT_SESSIONS, 'rb') as input:
            author_ids_with_active_cleverbot_chat_sessions = pickle.load(input)
        author_ids_with_active_cleverbot_chat_sessions.remove(ctx.author.id)
        with open(filepaths.CLEVERBOT_ACTIVE_CHAT_SESSIONS, 'wb') as output:
            pickle.dump(author_ids_with_active_cleverbot_chat_sessions, output)


@bot.command(aliases=['meme'])
async def generateMeme(ctx, meme_name, top_text="", bottom_text=""):
    meme_generator = MemeGenerator()
    meme_generator.generate_meme(meme_name, top_text, bottom_text)
    await ctx.send(file=discord.File(meme_generator.memes_folder_path + 'meme_edited.jpg'))


###########################
# Run Client
###########################

if __name__ == "__main__":
    bot.run(os.getenv('TOKEN'))