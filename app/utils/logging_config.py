# app/utils/logging_config.py

import logging
from logging.handlers import RotatingFileHandler

# Configure logging with RotatingFileHandler to prevent log files from growing indefinitely
handler = RotatingFileHandler("app/bot.log", maxBytes=5*1024*1024, backupCount=5)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        handler,
        logging.StreamHandler()
    ]
)

# Create a logger for the bot
logger = logging.getLogger("metaOfmBot")  # Use a consistent logger name
