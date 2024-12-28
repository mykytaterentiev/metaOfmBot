import os
import tempfile
import json
import io
import random
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
    
    if user_id not in USER_STATE or "file_id" not in USER_STATE[user_id]:
        await message.reply_text("Нет сохраненного файла. Пожалуйста, сначала отправь видео или фото.")
        return
    
    args = context.args
    if len(args) != 1:
        await message.reply_text("Использование: /process <n> (например, /process 3)")
        return
    
    try:
        n = int(args[0])
        if not (1 <= n <= 10):
            await message.reply_text("Пожалуйста, запроси от 1 до 10 вариантов.")
            return
    except ValueError:
        await message.reply_text("Пожалуйста, укажи действительное целое число (1-10).")
        return
    
    file_id = USER_STATE[user_id]["file_id"]
    file_name = USER_STATE[user_id]["file_name"]
    file_type = USER_STATE[user_id]["file_type"]
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, file_name)
        try:
            file_obj = await context.bot.get_file(file_id)
            await file_obj.download_to_drive(input_path)
            logger.info(f"Файл скачан в {input_path}")
        except Exception as e:
            logger.error(f"Не удалось скачать файл: {e}")
            await message.reply_text("Не удалось скачать файл. Пожалуйста, попробуй снова.")
            return
        
        file_hash = get_file_hash(input_path)
        if file_hash in PROCESSED_FILE_IDS:
            await message.reply_text("Этот файл уже был обработан ранее. Пожалуйста, отправь другой файл.")
            return
        PROCESSED_FILE_IDS.add(file_hash)
        save_processed_file_ids()
        
        original_meta = get_metadata(input_path, file_type)
        logger.info("Original Metadata:")
        logger.info(original_meta)
        
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
                return
            
            logger.info(
                f"Variant #{i} generated parameters:\n"
                f"Brightness: {params['brightness']}, Sharpen: {params['sharpen']}, "
                f"Temperature: {params['temp']}, Contrast: {params['contrast']}, Gamma: {params['gamma']}"
            )
            
            try:
                output_file = f"output_{i}{os.path.splitext(file_name)[1]}"
                output_path = os.path.join(tmp_dir, output_file)
                
                set_metadata_ffmpeg(input_path, output_path, params)
                
                output_paths.append((output_path, params))
            except subprocess.CalledProcessError as e:
                await message.reply_text(f"Ошибка при генерации варианта #{i}: {e}")
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
        await message.reply_text("Всё готово! Отправь другой файл или используй /help для дополнительных команд.")