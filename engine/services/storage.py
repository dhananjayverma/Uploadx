import os
import hashlib
import string
import random
import shutil
from typing import Tuple
from config import settings

# Subfolders
SUBFOLDERS = ["images", "videos", "docs", "temp"]

def init_storage():
    """
    Initializes the storage root and subdirectories.
    """
    os.makedirs(settings.STORAGE_ROOT, exist_ok=True)
    for sub in SUBFOLDERS:
        os.makedirs(os.path.join(settings.STORAGE_ROOT, sub), exist_ok=True)

def generate_short_id(length: int = 8) -> str:
    """
    Generates a secure random short alphanumeric ID.
    """
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))

def get_file_category(mime_type: str) -> str:
    """
    Determines the storage subfolder based on the mime type.
    """
    if not mime_type:
        return "docs"
    
    mime_type = mime_type.lower()
    if mime_type.startswith("image/"):
        return "images"
    elif mime_type.startswith("video/"):
        return "videos"
    elif mime_type.startswith("text/") or mime_type in [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/epub+zip"
    ]:
        return "docs"
    else:
        return "docs"

def save_raw_file(file_content: bytes, filename: str, mime_type: str) -> Tuple[str, str, str]:
    """
    Saves a raw file content to the temp directory first.
    Returns: (temp_filepath, file_hash, file_extension)
    """
    # Calculate SHA256 hash
    hasher = hashlib.sha256()
    hasher.update(file_content)
    file_hash = hasher.hexdigest()
    
    _, ext = os.path.splitext(filename)
    if not ext:
        # Fallback based on mime type
        if mime_type == "image/png":
            ext = ".png"
        elif mime_type == "image/jpeg":
            ext = ".jpg"
        elif mime_type == "image/webp":
            ext = ".webp"
        elif mime_type == "application/pdf":
            ext = ".pdf"
        else:
            ext = ".bin"
            
    temp_id = f"temp_{generate_short_id()}{ext}"
    temp_path = os.path.join(settings.STORAGE_ROOT, "temp", temp_id)
    
    with open(temp_path, "wb") as f:
        f.write(file_content)
        
    return temp_path, file_hash, ext.lower()

def move_to_permanent(temp_path: str, category: str, file_id: str, ext: str) -> str:
    """
    Moves a file from temp to its permanent category subfolder.
    """
    dest_filename = f"{file_id}{ext}"
    dest_path = os.path.join(settings.STORAGE_ROOT, category, dest_filename)
    shutil.move(temp_path, dest_path)
    return dest_path

def delete_physical_file(category: str, filename: str):
    """
    Removes the file from disk if it exists.
    """
    filepath = os.path.join(settings.STORAGE_ROOT, category, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
