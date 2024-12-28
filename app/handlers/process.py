import os
import tempfile
import json
import io
import random
import subprocess  # Ensure subprocess is imported
from telegram import Update, PhotoSize
from telegram.ext import ContextTypes

from app.config import PARAMETERS, PARAM_OPTIONS, PROCESSED_FILE_IDS_PATH, USER_DATA_FILE
from app.utils.metadata import get_metadata, compare_metadata, get_file_hash
from app.utils.file_processing import set_metadata_ffmpeg
from app.utils.logging_config import logger  # Correct import

PROCESSED_FILE_IDS = set()
USER_STATE = {}

# Load processed file IDs
if os.path.exists(PROCESSED_FILE_IDS_PATH):
    with open(PROCESSED_FILE_IDS_PATH, "r") as f:
        PROCESSED_FILE_IDS = set(json.load(f))
else:
    PROCESSED_FILE_IDS = set()

def save_processed_file_ids():
    with open(PROCESSED_FILE_IDS_PATH, "w") as f:
        json.dump(list(PROCESSED_FILE_IDS), f)

def generate_random_params():
    return {
        "brightness": round(random.uniform(0.9, 1.1), 3),
        "sharpen": round(random.uniform(0.9, 1.1), 3),
        "temp": round(random.uniform(0.9, 1.1), 3),
        "contrast": round(random.uniform(0.9, 1.1), 3),
        "gamma": round(random.uniform(0.9, 1.1), 3),
    }

async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id
    
    logger.info(f"Processing command /process from user {user_id}")
    
    if user_id not in USER_STATE or "file_id" not in USER_STATE[user_id]:
        await message.reply_text("Нет сохраненного файла. Пожалуйста, сначала отправь видео или фото.")
        logger.warning(f"No file_id found in USER_STATE for user {user_id}")
        return
    
    args = context.args
    if len(args) != 1:
        await message.reply_text("Использование: /process <n> (например, /process 3)")
        logger.warning(f"Incorrect number of arguments for /process command from user {user_id}")
        return
    
    try:
        n = int(args[0])
        if not (1 <= n <= 10):
            await message.reply_text("Пожалуйста, запроси от 1 до 10 вариантов.")
            logger.warning(f"Invalid number of variants requested by user {user_id}: {n}")
            return
    except ValueError:
        await message.reply_text("Пожалуйста, укажи действительное целое число (1-10).")
        logger.warning(f"Non-integer argument for /process command from user {user_id}: {args[0]}")
        return
    
    file_id = USER_STATE[user_id]["file_id"]
    file_name = USER_STATE[user_id]["file_name"]
    file_type = USER_STATE[user_id]["file_type"]
    
    logger.info(f"User {user_id} has file_id: {file_id}, file_type: {file_type}, file_name: {file_name}")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, file_name)
        try:
            file_obj = await context.bot.get_file(file_id)
            await file_obj.download_to_drive(input_path)
            logger.info(f"Файл скачан в {input_path}")
        except Exception as e:
            logger.error(f"Не удалось скачать файл для user {user_id}: {e}")
            await message.reply_text("Не удалось скачать файл. Пожалуйста, попробуй снова.")
            return
        
        file_hash = get_file_hash(input_path)
        if file_hash in PROCESSED_FILE_IDS:
            await message.reply_text("Этот файл уже был обработан ранее. Пожалуйста, отправь другой файл.")
            logger.warning(f"File {file_hash} already processed for user {user_id}")
            return
        PROCESSED_FILE_IDS.add(file_hash)
        save_processed_file_ids()
        
        original_meta = get_metadata(input_path, file_type)
        logger.info(f"Original Metadata for user {user_id}: {original_meta}")
        
        await message.reply_text("Начинаю обработку. Пожалуйста, подожди...")
        
        used_combinations = set()
        output_paths = []
        for i in range(1, n + 1):
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                params = generate_random_params()
                params_tuple = tuple(params[param] for param in PARAMETERS)
                if params_tuple not in used_combinations:
                    used_combinations.add(params_tuple)
                    break
                attempt += 1
            else:
                await message.reply_text("Не удалось сгенерировать уникальные параметры для варианта.")
                logger.error(f"Failed to generate unique parameters for variant {i} for user {user_id}")
                return
            
            logger.info(
                f"Variant #{i} generated parameters for user {user_id}:\n"
                f"Brightness: {params['brightness']}, Sharpen: {params['sharpen']}, "
                f"Temperature: {params['temp']}, Contrast: {params['contrast']}, Gamma: {params['gamma']}"
            )
            
            try:
                output_file = f"output_{i}{os.path.splitext(file_name)[1]}"
                output_path = os.path.join(tmp_dir, output_file)
                
                set_metadata_ffmpeg(input_path, output_path, params)
                
                if os.path.isfile(output_path):
                    logger.info(f"Processed file saved at {output_path} for variant #{i}")
                else:
                    logger.error(f"Processed file not found at {output_path} for variant #{i}")
                    await message.reply_text(f"Ошибка: Обработанный файл для варианта #{i} не найден.")
                    continue
                
                output_paths.append((output_path, params))
            except subprocess.CalledProcessError as e:
                await message.reply_text(f"Ошибка при генерации варианта #{i}: {e}")
                logger.error(f"FFmpeg processing failed for variant #{i} for user {user_id}: {e}")
                return
        
        for i, (path, meta) in enumerate(output_paths, 1):
            if not os.path.isfile(path):
                logger.error(f"Обработанный файл не найден: {path}")
                await message.reply_text(f"Ошибка: Обработанный файл для варианта #{i} не найден.")
                continue
            updated_meta = get_metadata(path, file_type)
            diff_text = compare_metadata(original_meta, updated_meta, PARAMETERS)
            
            summary = (
                f"Вот вариант #{i} с настройками яркости, резкости, температуры, контраста и гаммы.\n\n"
                f"--- Изменения в метаданных ---\n"
                f"{diff_text}"
            )
            log_file = io.StringIO(summary)
            await message.reply_document(
                document=log_file,
                filename=f"variant_{i}_logs.txt",
                caption=f"Логи для варианта #{i}"
            )
            with open(path, "rb") as file:
                if file_type == "video":
                    await message.reply_video(video=file)
                elif file_type == "photo":
                    await message.reply_photo(photo=file)
        
        del USER_STATE[user_id]
        logger.info(f"Processing completed for user {user_id}")
        await message.reply_text("Всё готово! Отправь другой файл или используй /help для дополнительных команд.")