import logging
from aiogram import Bot, Dispatcher
from aiogram.utils import executor
from config import API_TOKEN
from handlers_scheduler import register_handlers

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
register_handlers(dp, bot)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
