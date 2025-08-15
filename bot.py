import os
import logging
from datetime import time, date, datetime, timedelta
from io import BytesIO

import qrcode
import pandas as pd
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pytz

# Импортируем функции для работы с БД
import database as db

# Загружаем переменные окружения из .env файла (для локального тестирования)
load_dotenv()

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')
TIMEZONE = pytz.timezone('Europe/Moscow') # Укажите ваш часовой пояс

# --- Основные функции бота ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    await update.message.reply_text(
        'Здравствуйте! Пожалуйста, введите ваш персональный код для получения талона на питание.'
    )

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает введенный сотрудником код."""
    user_code = update.message.text.strip()
    chat_id = update.message.chat_id
    now = datetime.now(TIMEZONE)

    # 1. Проверка времени (с 9:00 до 18:00)
    if not (time(9, 0) <= now.time() <= time(18, 0)):
        await update.message.reply_text('Извините, получить талон можно только с 9:00 до 18:00.')
        return

    # 2. Поиск сотрудника в базе данных
    employee = db.get_employee_by_code(user_code)
    if not employee:
        await update.message.reply_text('Сотрудник с таким кодом не найден. Пожалуйста, проверьте код и попробуйте снова.')
        return

    employee_id, employee_name, _ = employee

    # 3. Проверка, не получал ли сотрудник талон сегодня
    if db.check_if_ticket_granted_today(employee_id):
        await update.message.reply_text('Вы уже получили свой талон на сегодня. Следующий талон можно будет получить завтра.')
        return

    # 4. Выдача талона
    db.grant_ticket(employee_id)
    logger.info(f"Выдан талон для сотрудника: {employee_name}")

    # 5. Генерация и отправка талона с QR-кодом
    ticket_text = (
        f"✅ Талон на питание\n\n"
        f"Сотрудник: {employee_name}\n"
        f"Дата: {now.strftime('%d.%m.%Y')}\n"
        f"Время выдачи: {now.strftime('%H:%M:%S')}\n\n"
        f"Этот талон действителен на сегодня."
    )

    # Создаем QR-код
    qr_img = qrcode.make(ticket_text)
    bio = BytesIO()
    bio.name = 'ticket_qr.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=bio,
        caption=ticket_text
    )

# --- Функции для отчетов ---

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет ежедневный отчет администратору."""
    logger.info("Формирование ежедневного отчета...")
    report_data = db.get_daily_report()
    today_str = date.today().strftime('%d.%m.%Y')

    if not report_data:
        message = f"📄 Ежедневный отчет за {today_str}\n\nСегодня талоны никто не получал."
    else:
        message = f"📄 Ежедневный отчет за {today_str}\n\n"
        message += f"Всего выдано талонов: {len(report_data)}\n\n"
        message += "Список сотрудников:\n"
        for i, (name, time_issued) in enumerate(report_data, 1):
            message += f"{i}. {name} - {time_issued.strftime('%H:%M:%S')}\n"

    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message)
    logger.info("Ежедневный отчет отправлен.")


async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Формирует и отправляет ежемесячный отчет в виде Excel файла."""
    logger.info("Формирование ежемесячного отчета...")
    today = date.today()
    # Отчет за предыдущий месяц
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    month = last_day_of_previous_month.month
    year = last_day_of_previous_month.year
    
    report_data = db.get_monthly_report(month, year)

    if not report_data:
        message = f"Ежемесячный отчет за {month:02}.{year}: талоны не выдавались."
        await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=message)
        logger.info("Ежемесячный отчет (пустой) отправлен.")
        return

    # Создаем DataFrame и Excel файл в памяти
    df = pd.DataFrame(report_data, columns=['Имя сотрудника', 'Дата', 'Время'])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    
    output.seek(0)
    
    file_name = f"monthly_report_{month:02}_{year}.xlsx"
    caption = f"📊 Ежемесячный отчет за {last_day_of_previous_month.strftime('%B %Y')}"

    await context.bot.send_document(
        chat_id=ADMIN_TELEGRAM_ID,
        document=output,
        filename=file_name,
        caption=caption
    )
    logger.info("Ежемесячный отчет отправлен.")


# --- Основная функция запуска ---

def main() -> None:
    """Запускает бота и настраивает обработчики."""
    # Инициализация базы данных
    db.init_db()

    # Создание приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Настройка планировщика задач
    job_queue = application.job_queue
    # Ежедневный отчет в 18:10
    job_queue.run_daily(send_daily_report, time=time(18, 10, 0, tzinfo=TIMEZONE))
    # Ежемесячный отчет 1-го числа в 9:00
    job_queue.run_monthly(send_monthly_report, when=time(9, 0, 0, tzinfo=TIMEZONE), day=1)

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    # Запуск бота
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
