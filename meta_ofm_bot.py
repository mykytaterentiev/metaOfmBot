import logging
import os
import tempfile
import subprocess
import io

from telegram import Update, Document, Video
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pymediainfo import MediaInfo
from PIL import Image, ImageEnhance, PngImagePlugin
import piexif

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO  # Уровень логирования изменен на INFO для снижения объема логов
)
logger = logging.getLogger(__name__)

USER_STATE = {}

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
    fields = ["title", "comment"]
    lines = []
    for field in fields:
        orig_val = original_meta.get(field, "N/A")
        new_val = updated_meta.get(field, "N/A")
        if orig_val != new_val:
            lines.append(f"{field.capitalize()} изменено:\n    {orig_val} → {new_val}")
        else:
            lines.append(f"{field.capitalize()} не изменено: {orig_val}")
    return "\n".join(lines)

def process_video(input_path, output_path, filter_string, metadata_dict):
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if filter_string:
        cmd.extend(["-vf", filter_string, "-c:v", "libx264", "-crf", "18"])
    else:
        cmd.extend(["-c:v", "copy"])
    cmd.extend(["-c:a", "copy"])
    for k, v in metadata_dict.items():
        cmd.extend(["-metadata", f"{k}={v}"])
    cmd.append(output_path)
    logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Video processed successfully: {output_path}")
        logger.debug(f"FFmpeg STDERR: {result.stderr}")
        return result.stdout, result.stderr
    else:
        logger.error("FFmpeg failed!")
        logger.error(f"stdout: {result.stdout}")
        logger.error(f"stderr: {result.stderr}")
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=cmd,
            output=result.stdout,
            stderr=result.stderr
        )

def process_photo(input_path, output_path, brightness, contrast, metadata_dict):
    try:
        image = Image.open(input_path)
        enhancer_brightness = ImageEnhance.Brightness(image)
        image = enhancer_brightness.enhance(brightness)
        enhancer_contrast = ImageEnhance.Contrast(image)
        image = enhancer_contrast.enhance(contrast)
        ext = os.path.splitext(input_path)[1].lower()
        if ext in [".jpg", ".jpeg", ".tiff"]:
            try:
                exif_dict = piexif.load(input_path)
                logger.debug(f"Original EXIF data: {exif_dict}")
            except piexif.InvalidImageDataError:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                logger.warning(f"No existing EXIF data. Initializing new EXIF dictionary.")
            if "0th" not in exif_dict:
                exif_dict["0th"] = {}
            if "title" in metadata_dict:
                exif_dict["0th"][piexif.ImageIFD.Artist] = metadata_dict["title"].encode()
            if "comment" in metadata_dict:
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = metadata_dict["comment"].encode()
            try:
                exif_bytes = piexif.dump(exif_dict)
                logger.debug(f"Modified EXIF bytes: {exif_bytes}")
            except Exception as e:
                logger.error(f"Failed to dump EXIF data: {e}")
                exif_bytes = None
            if exif_bytes:
                image.save(output_path, exif=exif_bytes)
                logger.info(f"Photo saved with EXIF data: {output_path}")
            else:
                image.save(output_path)
                logger.info(f"Photo saved without EXIF data: {output_path}")
        elif ext == ".png":
            png_info = PngImagePlugin.PngInfo()
            if "title" in metadata_dict:
                png_info.add_text("Title", metadata_dict["title"])
            if "comment" in metadata_dict:
                png_info.add_text("Description", metadata_dict["comment"])
            image.save(output_path, pnginfo=png_info)
            logger.info(f"PNG photo saved с metadata: {output_path}")
        else:
            image.save(output_path)
            logger.info(f"Photo saved without metadata: {output_path}")
        return "Brightness and contrast adjusted successfully.", ""
    except Exception as e:
        logger.error(f"Photo processing failed: {e}")
        raise e

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне видео или фото, затем используй /process <n>, чтобы сгенерировать n уникальных вариантов с разными яркостью/контрастом и метаданными."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться ботом:\n"
        "1. Отправь видео или фото (как Telegram media или документ).\n"
        "2. Используй /process <n> (например, /process 3), чтобы сгенерировать n уникальных вариантов.\n"
        "Каждый вариант будет иметь разные настройки яркости/контраста и уникальные метаданные.\n"
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
        file_id = message.photo[-1].file_id
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
        USER_STATE[user_id] = {"file_id": file_id, "file_name": file_name, "file_type": file_type}
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
    await message.reply_text(f"Генерация {n} уникальных вариантов. Пожалуйста, подожди...")
    try:
        file_obj = await context.bot.get_file(file_id)
    except Exception as e:
        logger.error(f"Failed to get file: {e}")
        await message.reply_text("Не удалось получить файл. Пожалуйста, попробуй снова.")
        return
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, file_name)
        try:
            await file_obj.download_to_drive(input_path)
            logger.info(f"Файл скачан в {input_path}")
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            await message.reply_text("Не удалось скачать файл. Пожалуйста, попробуй снова.")
            return
        original_meta = get_metadata(input_path, file_type)
        output_paths = []
        for i in range(1, n + 1):
            if file_type == "video":
                filter_str = f"eq=brightness={0.05 * i}:contrast={1.1 * i}"
                meta = {
                    "title": f"Filtered Video #{i}",
                    "comment": f"Brightness/Contrast Variation {i}"
                }
                output_file = f"output_{i}.mp4"
                output_path = os.path.join(tmp_dir, output_file)
                try:
                    ff_stdout, ff_stderr = process_video(input_path, output_path, filter_str, meta)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error generating variant #{i}: {e}")
                    await message.reply_text(f"Ошибка при генерации варианта #{i}: {e}")
                    return
                output_paths.append((output_path, ff_stdout, ff_stderr, "video"))
            elif file_type == "photo":
                # Ограничение увеличения яркости и контраста
                brightness = min(1.0 + 0.05 * i, 1.5)  # Максимум +0.5
                contrast = min(1.0 + 0.1 * i, 2.0)    # Максимум +1.0
                meta = {
                    "title": f"Filtered Photo #{i}",
                    "comment": f"Brightness/Contrast Variation {i}"
                }
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
                    # Default to .jpg if unsupported extension
                    ext = ".jpg"
                output_file = f"output_{i}{ext}"
                output_path = os.path.join(tmp_dir, output_file)
                try:
                    log_stdout, log_stderr = process_photo(input_path, output_path, brightness, contrast, meta)
                except Exception as e:
                    logger.error(f"Error generating variant #{i}: {e}")
                    await message.reply_text(f"Ошибка при генерации варианта #{i}: {e}")
                    return
                output_paths.append((output_path, log_stdout, log_stderr, "photo"))
        for i, (path, log1, log2, f_type) in enumerate(output_paths, 1):
            if not os.path.isfile(path):
                logger.error(f"Processed file not found: {path}")
                await message.reply_text(f"Ошибка: Обработанный файл для варианта #{i} не найден.")
                continue
            updated_meta = get_metadata(path, f_type)
            diff_text = compare_metadata(original_meta, updated_meta)
            if f_type == "video":
                ff_logs = f"STDOUT:\n{log1}\nSTDERR:\n{log2}"
            elif f_type == "photo":
                ff_logs = f"Processing Output:\n{log1}\nErrors:\n{log2}"
            summary = (
                f"Вот вариант #{i} с настройками яркости/контраста.\n\n"
                f"--- Изменения в метаданных ---\n"
                f"{diff_text}\n\n"
                f"--- Подробные логи ---\n"
                f"{ff_logs}\n"
            )
            log_file = io.StringIO(summary)
            await message.reply_document(
                document=log_file,
                filename=f"variant_{i}_logs.txt",
                caption=f"Логи для варианта #{i}"
            )
            with open(path, "rb") as file:
                if f_type == "video":
                    await message.reply_video(video=file)
                elif f_type == "photo":
                    await message.reply_photo(photo=file)
        # Очистка состояния пользователя после обработки
        del USER_STATE[user_id]
    await message.reply_text("Всё готово! Отправь другой файл или используй /help для дополнительных команд.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("process", process_command))
    application.add_handler(
        MessageHandler(
            (filters.VIDEO | filters.PHOTO | filters.Document.VIDEO | filters.Document.IMAGE) & ~filters.COMMAND,
            handle_file
        )
    )
    logger.info("Bot is starting. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()
