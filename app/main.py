# app/main.py

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.config import BOT_TOKEN
from app.utils.logging_config import logger
from app.handlers.start import start_command
from app.handlers.help import help_command
from app.handlers.process import process_command
from app.handlers.file_handler import handle_file
from app.utils.metadata import get_file_hash

# Initialize FastAPI
app = FastAPI()

# Initialize Telegram Bot Application
application = Application.builder().token(BOT_TOKEN).build()

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

application.add_error_handler(error_handler)

# Register command handlers
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("process", process_command))

# Register message handler for files
application.add_handler(
    MessageHandler(
        (filters.VIDEO | filters.PHOTO | filters.Document.VIDEO | filters.Document.IMAGE) & ~filters.COMMAND,
        handle_file
    )
)

@app.get("/")
async def root():
    return {"message": "metaOfmBot is running."}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await application.initialize()
    await application.start()
    try:
        yield  # Application runs during this time
    finally:
        # Shutdown logic
        await application.stop()
        await application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = Update.de_json(await request.json(), application.bot)
        logger.info(f"Received update: {update}")
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status_code=500)
    return Response(status_code=200)
