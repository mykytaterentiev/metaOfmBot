import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

PROCESSED_FILE_IDS_PATH = "app/data/processed_files.json"
USER_DATA_FILE = "app/data/user_data.json"

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
