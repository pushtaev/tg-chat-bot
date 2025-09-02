from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import pandas as pd
from datetime import datetime, timedelta
import asyncio
from utils import parse_custom_time, format_custom_time

current_df = None
notification_time = None
notification_task = None
notification_days = set()

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("Приближающиеся работы"))
keyboard.add(KeyboardButton("Добавить наработку"))
keyboard.add(KeyboardButton("Установить время уведомлений"))
keyboard.add(KeyboardButton("Управление днями уведомлений"))

def register_handlers(dp: Dispatcher, bot):
    # Обработчик /start
    @dp.message_handler(commands=['start'])
    async def send_welcome(message: types.Message):
        await message.reply(
            "Привет! Отправь мне файл в формате .xlsx с колонками «Наработка и «Планируется» (формат 756:10, где 756 — часы, 10 — минуты). "
            "Я могу уведомлять тебя о приближающихся событиях и добавлять наработку к колонке «Наработка.",
            reply_markup=keyboard
        )

    # Обработчик для файлов .xlsx
    @dp.message_handler(content_types=types.ContentType.DOCUMENT)
    async def handle_document(message: types.Message):
        global current_df

        if message.document.mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            file_id = message.document.file_id
            file = await bot.get_file(file_id)
            file_path = file.file_path
            await bot.download_file(file_path, "temp.xlsx")

            try:
                df = pd.read_excel("temp.xlsx")

                if 'Наработка' not in df.columns or 'Планируется' not in df.columns:
                    await message.reply("В таблице отсутствуют колонки «Наработка или «Планируется». Пожалуйста, добавьте их.")
                    return

                current_df = df

                await message.reply("Файл успешно загружен. Используй кнопки для управления.", reply_markup=keyboard)

            except Exception as e:
                await message.reply(f"Произошла ошибка при обработке файла: {e}")
        else:
            await message.reply("Пожалуйста, отправьте файл в формате .xlsx.", reply_markup=keyboard)
    # Обработчик  «Приближающиеся работы»
    @dp.message_handler(lambda message: message.text == "Приближающиеся работы")
    async def show_upcoming_events(message: types.Message):
        global current_df

        if current_df is None:
            await message.reply("Файл ещё не загружен. Пожалуйста, отправьте файл .xlsx.")
            return

        upcoming_events = []

        for index, row in current_df.iterrows():
            current_time_str = row['Наработка']
            event_time_str = row['Планируется']

            current_time = parse_custom_time(current_time_str)
            event_time = parse_custom_time(event_time_str)

            if current_time is None or event_time is None:
                upcoming_events.append(f"Ошибка: время в строке «{row.get('Пункт регламента', 'Без названия')}» указано в неправильном формате.")
                continue

            time_difference = event_time - current_time

            if timedelta(hours=0) < time_difference < timedelta(hours=5):
                time_left = format_custom_time(time_difference)
                upcoming_events.append(f"{index}.  {row.get('Пункт регламента', 'Без названия')}, осталось: {time_left}")

        if upcoming_events:
            await message.reply("Приближающиеся работы:\n" + "\n".join(upcoming_events))
        else:
            await message.reply("Нет работ, до которых осталось менее 5 часов.")

    # Обработчик «Добавить наработку»
    @dp.message_handler(lambda message: message.text == "Добавить наработку")
    async def ask_for_work_hours(message: types.Message):
        await message.reply("Введите время наработки в формате 25:30 (часы:минуты):")

    # Обработчик ввода времени наработки
    @dp.message_handler(lambda message: ":" in message.text and message.text.count(":") == 1)
    async def add_work_hours(message: types.Message):
        global current_df

        if current_df is None:
            await message.reply("Файл ещё не загружен. Пожалуйста, отправьте файл .xlsx.")
            return

        work_time_str = message.text
        work_time = parse_custom_time(work_time_str)

        if work_time is None:
            await message.reply("Неправильный формат времени. Используйте формат 25:30 (часы:минуты).")
            return

        try:
            for index, row in current_df.iterrows():
                current_time_str = row['Наработка']
                current_time = parse_custom_time(current_time_str)
                if current_time is not None:
                    new_time = current_time + work_time
                    current_df.at[index, 'Наработка'] = format_custom_time(new_time)

            updated_file_path = "updated_temp.xlsx"
            current_df.to_excel(updated_file_path, index=False)

            with open(updated_file_path, "rb") as file:
                await message.reply_document(file, caption="Таблица с добавленной наработкой.")

        except Exception as e:
            await message.reply(f"Произошла ошибка при добавлении наработки: {e}")

    # Обработчик «Установить время уведомлений»
    @dp.message_handler(lambda message: message.text == "Установить время уведомлений")
    async def ask_notification_time(message: types.Message):
        await message.reply("Введите время для уведомлений в формате ЧЧ.ММ (например, 09.00):")

    # Обработчик ввода времени для уведомлений
    @dp.message_handler(lambda message: "." in message.text and message.text.count(".") == 1)
    async def set_notification_time(message: types.Message):
        global notification_time, notification_task

        time_str = message.text

        try:
            hours, minutes = map(int, time_str.split('.'))
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError

            notification_time = (hours, minutes)

            if notification_task:
                notification_task.cancel()

            notification_task = asyncio.create_task(schedule_notifications(message.chat.id))

            await message.reply(f"Время уведомлений установлено на {time_str}.")
        except ValueError:
            await message.reply("Неправильный формат времени. Используйте формат ЧЧ.ММ (например, 09.00).")

    # Обработчик «Управление днями уведомлений»
    @dp.message_handler(lambda message: message.text == "Управление днями уведомлений")
    async def manage_notification_days(message: types.Message):
        days_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        days_keyboard.add(KeyboardButton("Понедельник"))
        days_keyboard.add(KeyboardButton("Вторник"))
        days_keyboard.add(KeyboardButton("Среда"))
        days_keyboard.add(KeyboardButton("Четверг"))
        days_keyboard.add(KeyboardButton("Пятница"))
        days_keyboard.add(KeyboardButton("Суббота"))
        days_keyboard.add(KeyboardButton("Воскресенье"))
        days_keyboard.add(KeyboardButton("Назад"))

        await message.reply("Выберите день недели для управления уведомлениями:", reply_markup=days_keyboard)

    # Обработчик выбора дня недели
    @dp.message_handler(lambda message: message.text in ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"])
    async def toggle_notification_day(message: types.Message):
        global notification_days

        day_mapping = {
            "Понедельник": 0,
            "Вторник": 1,
            "Среда": 2,
            "Четверг": 3,
            "Пятница": 4,
            "Суббота": 5,
            "Воскресенье": 6,
        }

        day_number = day_mapping[message.text]

        if day_number in notification_days:
            notification_days.remove(day_number)
            await message.reply(f"Уведомления в {message.text} отключены.", reply_markup=keyboard)
        else:
            notification_days.add(day_number)
            await message.reply(f"Уведомления в {message.text} включены.", reply_markup=keyboard)

    # Обработчик «Назад»
    @dp.message_handler(lambda message: message.text == "Назад")
    async def back_to_main_menu(message: types.Message):
        await message.reply("Возвращаемся в главное меню.", reply_markup=keyboard)


    # Функция для планирования уведомлений
    async def schedule_notifications(chat_id):
        global notification_time, current_df, notification_days

        while True:
            try:
                now = datetime.now()

                if notification_time and (now.hour, now.minute) == notification_time and now.weekday() in notification_days:
                    if current_df is None:
                        await bot.send_message(chat_id, "Файл ещё не загружен. Пожалуйста, отправьте файл .csv.")
                        return

                    upcoming_events = []

                    for index, row in current_df.iterrows():
                        current_time_str = row['Наработка']
                        event_time_str = row['Планируется']

                        current_time = parse_custom_time(current_time_str)
                        event_time = parse_custom_time(event_time_str)

                        if current_time is None or event_time is None:
                            upcoming_events.append(f"Ошибка: время в строке «{row.get('Пункт регламента', 'Без названия')}» указано в неправильном формате.")
                            continue

                        time_difference = event_time - current_time

                        if timedelta(hours=0) < time_difference < timedelta(hours=5):
                            upcoming_events.append(f"Событие: «{row.get('Пункт регламента', 'Без названия')}», осталось: {time_difference}")

                    if upcoming_events:
                        await bot.send_message(chat_id, "Приближающиеся работы:\n" + "\n".join(upcoming_events))
                    else:
                        await bot.send_message(chat_id, "Нет событий, до которых осталось менее 5 часов.")

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await bot.send_message(chat_id, f"Произошла ошибка при проверке событий: {e}")
                await asyncio.sleep(60)
