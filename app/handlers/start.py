from telegram import Update
from telegram.ext import ContextTypes

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне видео или фото, затем используй /process <n>, чтобы сгенерировать n уникальных вариантов с разными настройками яркости, резкости, температуры, контраста и гаммы."
    )
