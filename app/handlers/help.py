from telegram import Update
from telegram.ext import ContextTypes

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться ботом:\n"
        "1. Отправь видео или фото (как Telegram media или документ).\n"
        "2. Используй /process <n> (например, /process 3), чтобы сгенерировать n уникальных вариантов.\n"
        "Каждый вариант будет иметь небольшие изменения яркости, резкости, температуры, контраста и гаммы.\n"
        "Ты получишь подробные логи сравнения оригинальных и обновленных метаданных."
    )
