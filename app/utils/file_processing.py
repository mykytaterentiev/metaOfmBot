import os
import subprocess
import logging

logger = logging.getLogger("metaOfmBot")

def set_metadata_ffmpeg(input_path, output_path, metadata_dict):
    brightness_eq = metadata_dict['brightness'] - 1.0
    contrast_eq = metadata_dict['contrast']
    gamma_eq = metadata_dict['gamma']
    sharpen_amount = metadata_dict['sharpen']
    
    vf_filters = (
        f"eq=brightness={brightness_eq}:contrast={contrast_eq}:gamma={gamma_eq},"
        f"unsharp=5:5:{sharpen_amount}"
    )
    
    comment_metadata = (
        f"Brightness={metadata_dict['brightness']}, "
        f"Sharpen={metadata_dict['sharpen']}, "
        f"Temperature={metadata_dict['temp']}, "
        f"Contrast={metadata_dict['contrast']}, "
        f"Gamma={metadata_dict['gamma']}"
    )
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", vf_filters,
        "-metadata", f"comment={comment_metadata}",
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
