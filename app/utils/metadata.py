import os
import hashlib
import json
from PIL import Image
import piexif
from pymediainfo import MediaInfo
import logging

logger = logging.getLogger(__name__)

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

def compare_metadata(original_meta, updated_meta, parameters):
    fields = list(parameters.keys()) + ["title", "comment"]
    lines = []
    original_params = {}
    updated_params = {}

    if "comment" in original_meta:
        try:
            parts = original_meta["comment"].split(", ")
            for part in parts:
                key, value = part.split("=")
                original_params[key.lower()] = value
        except:
            pass

    if "comment" in updated_meta:
        try:
            parts = updated_meta["comment"].split(", ")
            for part in parts:
                key, value = part.split("=")
                updated_params[key.lower()] = value
        except:
            pass

    for field in parameters.keys():
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
