# app/handlers/file_handler.py

import os
import json
import logging
from telegram import Update, PhotoSize
from telegram.ext import ContextTypes

from app.config import PROCESSED_FILE_IDS_PATH
from app.utils.logging_config import logger
from app.utils.user_state import USER_STATE  # Import shared USER_STATE

PROCESSED_FILE_IDS = set()

if os.path.exists(PROCESSED_FILE_IDS_PATH):
    with open(PROCESSED_FILE_IDS_PATH, "r") as f:
        PROCESSED_FILE_IDS = set(json.load(f))
else:
    PROCESSED_FILE_IDS = set()

def save_processed_file_ids():
    with open(PROCESSED_FILE_IDS_PATH, "w") as f:
        json.dump(list(PROCESSED_FILE_IDS), f)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id
    file_id = None
    file_name = ""
    file_type = ""
    
    logger.info(f"Handling file from user {user_id}")
    
    if message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "input_video.mp4"
        file_type = "video"
        logger.info(f"Received video file: {file_id}, name: {file_name}")
    elif message.photo:
        photo: PhotoSize = message.photo[-1]
        file_id = photo.file_id
        file_name = "input_photo.jpg"
        file_type = "photo"
        logger.info(f"Received photo file: {file_id}, name: {file_name}")
    elif message.document:
        mime_type = message.document.mime_type
        if mime_type.startswith("video"):
            file_id = message.document.file_id
            file_name = message.document.file_name or "input_video.mp4"
            file_type = "video"
            logger.info(f"Received document video file: {file_id}, name: {file_name}")
        elif mime_type.startswith("image"):
            file_id = message.document.file_id
            file_name = message.document.file_name or "input_photo.jpg"
            file_type = "photo"
            logger.info(f"Received document image file: {file_id}, name: {file_name}")
    else:
        await message.reply_text("Пожалуйста, отправь действительный файл видео или фото.")
        logger.warning(f"Unsupported file type from user {user_id}")
        return
    
    if file_id:
        USER_STATE[user_id] = {
            "file_id": file_id,
            "file_name": file_name,
            "file_type": file_type
        }
        logger.info(f"Stored file_id for user {user_id}: {USER_STATE[user_id]}")
        await message.reply_text(
            "Файл получен! Теперь используй /process <n>, чтобы указать количество уникальных вариантов."
        )
