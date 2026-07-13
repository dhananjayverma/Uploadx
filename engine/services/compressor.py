import os
import subprocess
import gzip
import shutil
from PIL import Image
from config import settings

def compress_image(source_path: str, dest_path: str, max_width: int = 1920, quality: int = 80) -> bool:
    """
    Compresses an image, resizes it if it exceeds max_width, and converts it to WebP.
    """
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if in RGBA mode and saving as non-transparent (or keep RGBA for WebP transparency)
            if img.mode in ("RGBA", "LA") and img.format != "PNG":
                # Pillow supports WebP with transparency, so we keep mode as is.
                pass
            elif img.mode != "RGB" and img.mode != "RGBA":
                img = img.convert("RGB")
                
            # Resize if exceeds max_width
            if img.width > max_width:
                aspect_ratio = img.height / img.width
                new_height = int(max_width * aspect_ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            img.save(dest_path, "WEBP", quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Error compressing image: {e}")
        return False

def compress_video(source_path: str, dest_path: str) -> bool:
    """
    Compresses video by reducing bitrate and transcoding to H.264 using ffmpeg.
    If ffmpeg is missing, falls back to copying the file.
    """
    # Check if ffmpeg exists on the system path
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found, skipping video compression and copying raw file.")
        shutil.copy(source_path, dest_path)
        return False
        
    try:
        # Run ffmpeg to transcode to mp4 with reasonable quality
        # -crf 28 is a good default compression level (higher means more compression, lower quality)
        cmd = [
            "ffmpeg", "-y", "-i", source_path,
            "-vcodec", "libx264", "-crf", "28",
            "-preset", "fast", "-acodec", "aac",
            "-strict", "-2", dest_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr}")
            shutil.copy(source_path, dest_path)
            return False
        return True
    except Exception as e:
        print(f"Video compression failed: {e}")
        shutil.copy(source_path, dest_path)
        return False

def compress_pdf(source_path: str, dest_path: str) -> bool:
    """
    Optimizes/compresses a PDF. If ghostscript or gs is available, uses it.
    Otherwise, copies the file.
    """
    if not shutil.which("gs"):
        print("Ghostscript (gs) not found, copying raw PDF.")
        shutil.copy(source_path, dest_path)
        return False

    try:
        cmd = [
            "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen", "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={dest_path}", source_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        if result.returncode != 0:
            print(f"Ghostscript error: {result.stderr}")
            shutil.copy(source_path, dest_path)
            return False
        return True
    except Exception as e:
        print(f"PDF compression failed: {e}")
        shutil.copy(source_path, dest_path)
        return False

def compress_text(source_path: str, dest_path: str) -> bool:
    """
    Compresses text files using gzip.
    """
    try:
        with open(source_path, 'rb') as f_in:
            with gzip.open(dest_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception as e:
        print(f"Text compression failed: {e}")
        shutil.copy(source_path, dest_path)
        return False
