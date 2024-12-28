import logging

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("app/bot.log"),
        logging.StreamHandler()
    ]
)

# Create a logger for the bot
logger = logging.getLogger("metaOfmBot")  # Use a consistent logger name
