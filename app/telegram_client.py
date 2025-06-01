import os
import logging
import asyncio
import re
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import config, serializer, dqueue, sio


logger = logging.getLogger(__name__)


# Create the application
_telegram_api_token = os.getenv("TELEGRAM_API_BOT_TOKEN")
if not _telegram_api_token:
    logger.error('"TELEGRAM_API_BOT_TOKEN" not provided, exiting...')


# Create bot and dispatcher
dp = Dispatcher()
bot = Bot(token=_telegram_api_token)


# Command handler
@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer("Hello! I'm a bot created with aiogram.")


@dp.message(Command("help"))
async def help(message: Message):
    """Helper function to help user with the commands
    """
    logger.debug("help handler reached")
    help_txt = f"Hi {message.from_user.first_name}, I am your helper bot to download the videos from YouTube\n" \
    "You can simply send a YouTube url over and I will start the download for you"
    await message.answer(help_txt)


# Store the url of the video
URL = ""
URL_REGEX = re.compile(r'https?://\S+')


@dp.message()
async def handle_message(message: Message):
    global URL
    logger.info("Handling message: %s", message.message_id)
    if URL_REGEX.search(message.text or ''):
        await message.answer("Detected a URL!")
        
        URL = message.text
        logger.info("Received resource URL: %s", URL)

        # Define the keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard = [
                [KeyboardButton(text="MP4"), KeyboardButton(text="MP3")],
                [KeyboardButton(text="Cancel")]
            ],
            resize_keyboard=True,  # Makes the buttons fit better on mobile
            one_time_keyboard=True  # Hides keyboard after one use
        )
        logger.info('Saving "%s" url in memory', URL)

        await message.answer(
            "What format would you like the song/video",
            reply_markup=keyboard
        )

    if message.text.upper() in ['MP4', 'MP3']:
        res = "video" if message.text.upper() == "MP4" else "audio"
        logger.info("Downloading %s from YouTube", res)
        if not URL:
            await message.answer("Previously saved URL seem to be missing, please send a URL first")
            return
        url = URL
        quality = "0"
        vformat = message.text.lower()
        folder = None
        custom_name_prefix = ''
        auto_start = True
        playlist_strict_mode = '&list=' in url
        playlist_item_limit = 20

        logging.info(f"Downloading {url} as {message.text}")
        try:
            status = await dqueue.add(url, quality, vformat, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start)    
            # Reset the globla URL
            URL = None
            return web.Response(text=serializer.encode(status))
            # return response(text=serializer.encode(status))
        except Exception as e:
            logger.error("Unable to download the resource: %s", e)
            res = "video" if vformat == "MP4" else "song"
            await message.answer(f"Sorry, we were not able to download the {res}")

# Run the bot
async def start_bot() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())
