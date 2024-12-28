# app/utils/file_processing.py

import os
import subprocess
import logging

logger = logging.getLogger("metaOfmBot")

def set_metadata_ffmpeg(input_path, output_path, metadata_dict):
    # Calculate filter values
    brightness_eq = metadata_dict['brightness'] - 1.0
    contrast_eq = metadata_dict['contrast']
    gamma_eq = metadata_dict['gamma']
    sharpen_amount = metadata_dict['sharpen']
    
    # Define video filters
    vf_filters = (
        f"eq=brightness={brightness_eq}:contrast={contrast_eq}:gamma={gamma_eq},"
        f"unsharp=5:5:{sharpen_amount}"
    )
    
    # Format metadata with semicolons to avoid FFmpeg parsing issues
    comment_metadata = (
        f"Brightness={metadata_dict['brightness']}; "
        f"Sharpen={metadata_dict['sharpen']}; "
        f"Temperature={metadata_dict['temp']}; "
        f"Contrast={metadata_dict['contrast']}; "
        f"Gamma={metadata_dict['gamma']}"
    )
    
    # FFmpeg command with optimizations
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output files without asking
        "-threads", "1",  # Limit to 1 thread to reduce CPU usage
        "-i", input_path,
        "-vf", vf_filters,
        "-preset", "ultrafast",  # Use ultrafast preset to minimize CPU usage
        "-metadata", f"comment={comment_metadata}",
        "-c:a", "copy",  # Copy audio without re-encoding
        output_path
    ]
    
    logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
    try:
        # Execute the FFmpeg command
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"FFmpeg output: {result.stdout.decode('utf-8')}")
        logger.info(f"Metadata update and video processing successful: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to set metadata and process video.")
        logger.error(f"Command: {' '.join(cmd)}")
        logger.error(f"Stdout: {e.stdout.decode('utf-8', errors='replace')}")
        logger.error(f"Stderr: {e.stderr.decode('utf-8', errors='replace')}")
        raise
