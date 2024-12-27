import logging
import os
import tempfile
import subprocess
import io
import json
import hashlib
import random

from fastapi import FastAPI, Request, Response
from telegram import Update, PhotoSize
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from pymediainfo import MediaInfo
from PIL import Image
import piexif

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROCESSED_FILE_IDS_PATH = "processed_files.json"

if os.path.exists(PROCESSED_FILE_IDS_PATH):
    with open(PROCESSED_FILE_IDS_PATH, "r") as f:
        PROCESSED_FILE_IDS = set(json.load(f))
else:
    PROCESSED_FILE_IDS = set()

def save_processed_file_ids():
    with open(PROCESSED_FILE_IDS_PATH, "w") as f:
        json.dump(list(PROCESSED_FILE_IDS), f)

USER_STATE = {}

PARAMETERS = {
    "brightness": {
        "base": 1.0,
        "increment": 0.03,
        "max": 1.2,
        "min": 0.8
    },
    "sharpen": {
        "base": 1.0,
        "increment": 0.03,
        "max": 1.2,
        "min": 0.8
    },
    "temp": {
        "base": 1.0,
        "increment": 0.03,
        "max": 1.2,
        "min": 0.8
    },
    "contrast": {
        "base": 1.0,
        "increment": 0.03,
        "max": 1.2,
        "min": 0.8
    },
    "gamma": {
        "base": 1.0,
        "increment": 0.03,
        "max": 1.2,
        "min": 0.8
    }
}

PARAM_OPTIONS = [0.8, 1.0, 1.2]

def generate_random_params():
    return {
        "brightness": round(random.uniform(0.9, 1.1), 3),
        "sharpen": round(random.uniform(0.9, 1.1), 3),
        "temp": round(random.uniform(0.9, 1.1), 3),
        "contrast": round(random.uniform(0.9, 1.1), 3),
        "gamma": round(random.uniform(0.9, 1.1), 3),
    }

app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()

def get_metadata(file_path, file_type):
    if not os.path.isfile(file_path):
        logger.warning(f"get_metadata: File not found: {file_path}")
        return {}
    metadata_dict = {}
    if file_type == "video":
        media_info = MediaInfo.parse(file_path)
        for track in media_info.tracks:
            if track.track_type == "General":
                if track.title:
                    metadata_dict["title"] = track.title
                if track.comment:
                    metadata_dict["comment"] = track.comment
    elif file_type == "photo":
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".jpg", ".jpeg", ".tiff"]:
            try:
                exif_dict = piexif.load(file_path)
                if "0th" in exif_dict:
                    if piexif.ImageIFD.Artist in exif_dict["0th"]:
                        metadata_dict["title"] = exif_dict["0th"][piexif.ImageIFD.Artist].decode(errors="ignore")
                    if piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                        metadata_dict["comment"] = exif_dict["0th"][piexif.ImageIFD.ImageDescription].decode(errors="ignore")
            except piexif.InvalidImageDataError:
                logger.warning(f"No EXIF data found for {file_path}.")
        elif ext == ".png":
            try:
                image = Image.open(file_path)
                info = image.info
                if 'Title' in info:
                    metadata_dict["title"] = info['Title']
                if 'Description' in info:
                    metadata_dict["comment"] = info['Description']
            except Exception as e:
                logger.error(f"PNG metadata extraction failed: {e}")
    return metadata_dict

def compare_metadata(original_meta, updated_meta):
    fields = list(PARAMETERS.keys()) + ["title", "comment"]
    lines = []
    original_params = {}
    updated_params = {}
    
    for field in PARAMETERS.keys():
        original_params[field] = "N/A"
        updated_params[field] = "N/A"
    
    if "comment" in original_meta:
        try:
            parts = original_meta["comment"].split(", ")
            for part in parts:
                key, value = part.split("=")
                if key.lower() in PARAMETERS:
                    original_params[key.lower()] = value
        except:
            pass
    
    if "comment" in updated_meta:
        try:
            parts = updated_meta["comment"].split(", ")
            for part in parts:
                key, value = part.split("=")
                if key.lower() in PARAMETERS:
                    updated_params[key.lower()] = value
        except:
            pass
    
    for field in PARAMETERS.keys():
        orig_val = original_params.get(field, "N/A")
        new_val = updated_params.get(field, "N/A")
        if orig_val != new_val:
            lines.append(f"{field.capitalize()} изменено:\n    {orig_val} → {new_val}")
        else:
            lines.append(f"{field.capitalize()} не изменено: {orig_val}")
    
    for field in ["title", "comment"]:
        orig_val = original_meta.get(field, "N/A")
        new_val = updated_meta.get(field, "N/A")
        if orig_val != new_val:
            lines.append(f"{field.capitalize()} изменено:\n    {orig_val} → {new_val}")
        else:
            lines.append(f"{field.capitalize()} не изменено: {orig_val}")
    
    return "\n".join(lines)

def get_file_hash(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def set_metadata_ffmpeg(input_path, output_path, metadata_dict):
    brightness_eq = metadata_dict['brightness'] - 1.0  
    contrast_eq = metadata_dict['contrast']          
    gamma_eq = metadata_dict['gamma']                 
    sharpen_amount = metadata_dict['sharpen']        
    
    vf_filters = (
        f"eq=brightness={brightness_eq}:contrast={contrast_eq}:gamma={gamma_eq},"
        f"unsharp=5:5:{sharpen_amount}"
    )
    
    cmd = [
        "ffmpeg",
        "-y",  
        "-i", input_path,
        "-vf", vf_filters,
        "-c:a", "copy",  
        output_path
    ]
    
    logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"Metadata update and video processing successful: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to set metadata and process video.")
        logger.error(f"Command: {' '.join(cmd)}")
        logger.error(f"Error: {e.stderr.decode('utf-8', errors='replace')}")
        raise

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне видео или фото, затем используй /process <n>, чтобы сгенерировать n уникальных вариантов с разными настройками яркости, резкости, температуры, контраста и гаммы."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться ботом:\n"
        "1. Отправь видео или фото (как Telegram media или документ).\n"
        "2. Используй /process <n> (например, /process 3), чтобы сгенерировать n уникальных вариантов.\n"
        "Каждый вариант будет иметь небольшие изменения яркости, резкости, температуры, контраста и гаммы.\n"
        "Ты получишь подробные логи сравнения оригинальных и обновленных метаданных."
    )

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
            diff_text = compare_metadata(original_meta, updated_meta)
            
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

application.add_error_handler(error_handler)

application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("process", process_command))
application.add_handler(
    MessageHandler(
        (filters.VIDEO | filters.PHOTO | filters.Document.VIDEO | filters.Document.IMAGE) & ~filters.COMMAND,
        handle_file
    )
)

@app.get("/")
async def root():
    return {"message": "metaOfmBot is running."}

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await application.start()

@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = Update.de_json(await request.json(), application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status_code=500)
    return Response(status_code=200)
