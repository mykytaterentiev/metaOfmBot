import os
import json
import logging
from telegram import Update, PhotoSize
from telegram.ext import ContextTypes

from app.config import PROCESSED_FILE_IDS_PATH
from app.utils.metadata import get_file_hash

logger = logging.getLogger(__name__)

PROCESSED_FILE_IDS = set()

if os.path.exists(PROCESSED_FILE_IDS_PATH):
    with open(PROCESSED_FILE_IDS_PATH, "r") as f:
        PROCESSED_FILE_IDS = set(json.load(f))
else:
    PROCESSED_FILE_IDS = set()

def save_processed_file_ids():
    with open(PROCESSED_FILE_IDS_PATH, "w") as f:
        json.dump(list(PROCESSED_FILE_IDS), f)

USER_STATE = {}

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id
    file_id = None
    file_name = ""
    file_type = ""
    
    if message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "input_video.mp4"
        file_type = "video"
    elif message.photo:
        photo: PhotoSize = message.photo[-1]
        file_id = photo.file_id
        file_name = "input_photo.jpg"
        file_type = "photo"
    elif message.document:
        mime_type = message.document.mime_type
        if mime_type.startswith("video"):
            file_id = message.document.file_id
            file_name = message.document.file_name or "input_video.mp4"
            file_type = "video"
        elif mime_type.startswith("image"):
            file_id = message.document.file_id
            file_name = message.document.file_name or "input_photo.jpg"
            file_type = "photo"
    else:
        await message.reply_text("Пожалуйста, отправь действительный файл видео или фото.")
        return
    
    if file_id:
        USER_STATE[user_id] = {
            "file_id": file_id,
            "file_name": file_name,
            "file_type": file_type
        }
        await message.reply_text(
            "Файл получен! Теперь используй /process <n>, чтобы указать количество уникальных вариантов."
        )
