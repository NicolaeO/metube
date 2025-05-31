import os
import logging
import asyncio
import time

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    Updater,
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger(__name__).setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class TelegramDownloader:

    # Store the url of the video
    URL = ""

    def __init__(self, dqueue, response, serializer):
        # Create the application
        self._telegram_api_token = os.getenv("TELEGRAM_API_BOT_TOKEN")
        if not self._telegram_api_token:
            logger.error('"TELEGRAM_API_BOT_TOKEN" not provided, exiting...')
            return None

        self.response = response
        self.dqueue = dqueue
        self.serializer = serializer


    async def botloop_routine(self):
        """Start bootloop
        """
        self.application = Application.builder().token(self._telegram_api_token).build()
        
        # Set default and error commands
        self.application.add_error_handler(self.error)
        self.application.add_handler(CommandHandler("help", self.help))

        # Set message commands
        self.application.add_handler(MessageHandler(filters.Entity("url") | filters.Entity("text_link"), self.get_youtube_url))
        # self.application.add_handler(MessageHandler(filters.TEXT & (filters.Text("MP3") | filters.Text("MP4")), self.download_youtube))
        self.application.add_handler(MessageHandler(filters.Regex("MP3|MP4"), self.download_youtube))

        self.application.add_handler(MessageHandler(filters.TEXT, self.help))

        await self.application.initialize()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await self.application.start()
        
        # Telegram now runs in the background, as an asyncio coroutine.
        # the other asyncio couroutine "task" is the following loop
        while True:
            # exiting from this loop will make the bot exit
            await asyncio.sleep(1)
        
        # dropped from the loop -> shutdown bot
        await self.application.Updater.stop()
        await self.application.stop()
        await self.application.shutdown()


    async def botloop_starttask(self):
        """Start the task
        """
        bot_routine = asyncio.create_task(self.botloop_routine())
        await bot_routine


    # start botloop. This blocks, so this must be started as a new thread.
    def botloop(self, *args, **kwargs):
        """Entry point
        tg_thread = Thread(target=botloop, name="botloop")
        tg_thread.daemon = True
        tg_thread.start()
        """
        asyncio.run(self.botloop_starttask())


    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Catch any errors or unknown commands
        """
        logger.debug("Error handler reached")
        await update.message.reply_text('Sorry I am limited in responses')
        logger.error("Update %s caused error %s", update, context.error)


    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Helper function to help user with the commands
        """
        logger.debug("help handler reached")
        help_txt = f"Hi {update.effective_user.first_name}, I am your helper bot to download the videos from YouTube\n" \
        "You can simply send a YouTube url over and I will start the download for you"
        await update.message.reply_text(help_txt)


    async def get_youtube_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect the url from the message"""
        logger.debug("get_youtube_url handler reached")
        self.URL = update.message.text
        logger.info('Saving "%s" url in memory', self.URL)
        reply_keyboard = [["MP3", "MP4", "Cancel"]]

        await update.message.reply_text(
            "What format would you like the song/video",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, input_field_placeholder="Song or Video"
            ),
        )


    async def download_youtube(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the download of the YouTube content
        """
        logger.debug("download_youtube handler reached")
        if not self.URL:
            await update.message.reply_text("Unknown URL...")
            return
        if update.message.text not in ("MP3", "MP4"):
            await update.message.reply_text("Ok, canceled!")
            return
        url = self.URL
        quality = 0
        vformat = update.message.text
        folder = None
        custom_name_prefix = ''
        auto_start = True
        playlist_strict_mode = 'false'
        playlist_item_limit = '0'

        logging.info(f"Downloading {url} as {update.message.text}")
        try:
            status = await self.dqueue.add(url, quality, vformat, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start)    
            # Reset the globla URL
            URL = None
            return self.response(text=self.serializer.encode(status))
        except Exception as e:
            logger.error("Unable to download the resource: %s", e)
            res = "video" if vformat == "MP4" else "song"
            await update.message.reply_text(f"Sorry, we were not able to download the {res}")
