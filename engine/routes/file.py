import os
import shutil
import hashlib
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime

from config import settings
from services import storage, db, compressor, automation

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    compress: bool = Form(True),
    autoFormat: bool = Form(True),
    maxSize: str = Form(None)  # e.g., "100MB" (Node.js layer will also handle validation)
):
    # Read entire file into memory for hashing and duplicate check
    content = await file.read()
    
    # Simple size limit check if requested
    if maxSize:
        # Convert e.g., "100MB", "10KB", "5GB" to bytes
        try:
            unit = maxSize[-2:].upper()
            val = float(maxSize[:-2])
            limit_bytes = val
            if unit == "KB":
                limit_bytes *= 1024
            elif unit == "MB":
                limit_bytes *= 1024 * 1024
            elif unit == "GB":
                limit_bytes *= 1024 * 1024 * 1024
            
            if len(content) > limit_bytes:
                raise HTTPException(status_code=400, detail=f"File exceeds maximum size limit of {maxSize}")
        except Exception:
            pass # Skip validation if limit format is invalid
            
    # Step 1: Save to temp and calculate SHA256
    temp_path, file_hash, ext = storage.save_raw_file(content, file.filename, file.content_type)
    
    # Step 2: Duplicate Detection
    existing = await db.get_file_metadata_by_hash(file_hash)
    if existing:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        # Return existing file details to avoid duplicate storage
        return JSONResponse(content={
            "status": "success",
            "message": "Duplicate file detected. Serving existing resource.",
            "data": {
                "id": existing["id"],
                "filename": existing["filename"],
                "mime_type": existing["mime_type"],
                "size": existing["size"],
                "hash": existing["hash"],
                "url": existing["url"],
                "category": existing["category"]
            }
        })
        
    # Step 3: Determine target category & extension
    category = storage.get_file_category(file.content_type)
    file_id = storage.generate_short_id()
    
    # Perform Compression & Formats conversions
    final_path = None
    final_ext = ext
    mime_type = file.content_type
    
    # Create final directory just in case
    category_dir = os.path.join(settings.STORAGE_ROOT, category)
    os.makedirs(category_dir, exist_ok=True)
    
    if compress:
        if category == "images" and autoFormat:
            final_ext = ".webp"
            mime_type = "image/webp"
            dest_name = f"{file_id}{final_ext}"
            dest_path = os.path.join(category_dir, dest_name)
            success = compressor.compress_image(temp_path, dest_path)
            if success:
                final_path = dest_path
        elif category == "videos":
            final_ext = ".mp4"
            mime_type = "video/mp4"
            dest_name = f"{file_id}{final_ext}"
            dest_path = os.path.join(category_dir, dest_name)
            success = compressor.compress_video(temp_path, dest_path)
            if success:
                final_path = dest_path
        elif category == "docs" and ext == ".pdf":
            dest_name = f"{file_id}{ext}"
            dest_path = os.path.join(category_dir, dest_name)
            success = compressor.compress_pdf(temp_path, dest_path)
            if success:
                final_path = dest_path
        elif category == "docs" and ext in [".txt", ".json", ".xml", ".csv"]:
            final_ext = f"{ext}.gz"
            mime_type = "application/gzip"
            dest_name = f"{file_id}{final_ext}"
            dest_path = os.path.join(category_dir, dest_name)
            success = compressor.compress_text(temp_path, dest_path)
            if success:
                final_path = dest_path
                
    # Fallback if compression disabled or failed
    if not final_path:
        dest_name = f"{file_id}{ext}"
        dest_path = os.path.join(category_dir, dest_name)
        shutil.move(temp_path, dest_path)
        final_path = dest_path
    else:
        # Clean up temp file since we compressed it to a new path
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    # Get final file size
    final_size = os.path.getsize(final_path)
    
    # Generate Short URL
    short_url = f"{settings.PUBLIC_BASE_URL}/f/{file_id}"
    
    # Save Metadata to MongoDB
    metadata = {
        "id": file_id,
        "filename": f"{file_id}{final_ext}",
        "original_name": file.filename,
        "mime_type": mime_type,
        "size": final_size,
        "hash": file_hash,
        "category": category,
        "path": f"{category}/{file_id}{final_ext}",
        "url": short_url,
        "created_at": datetime.utcnow().isoformat()
    }
    
    await db.save_file_metadata(metadata)
    
    return {
        "status": "success",
        "data": metadata
    }

@router.get("/file/{file_id}")
async def get_metadata(file_id: str):
    metadata = await db.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")
    return {
        "status": "success",
        "data": metadata
    }

@router.get("/f/{file_id}")
async def serve_file(file_id: str):
    metadata = await db.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
        
    filepath = os.path.join(settings.STORAGE_ROOT, metadata["path"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Physical file not found on disk")
        
    return FileResponse(filepath, media_type=metadata["mime_type"], filename=metadata["filename"])

@router.delete("/file/{file_id}")
async def delete_file(file_id: str):
    metadata = await db.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")
        
    # Delete from storage
    storage.delete_physical_file(metadata["category"], metadata["filename"])
    
    # Delete from DB
    await db.delete_file_metadata(file_id)
    
    return {
        "status": "success",
        "message": f"File {file_id} deleted successfully"
    }

from pydantic import BaseModel

class CaptureRequest(BaseModel):
    url: str
    format_type: str = "screenshot" # screenshot or pdf

async def handle_capture(url: str, format_type: str):
    try:
        temp_path = await automation.capture_url(url, format_type)
        
        # Open and hash file
        with open(temp_path, "rb") as f:
            content = f.read()
            
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicates
        existing = await db.get_file_metadata_by_hash(file_hash)
        if existing:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return {
                "status": "success",
                "message": "Duplicate automation capture found.",
                "data": existing
            }
            
        # Determine metadata
        file_id = storage.generate_short_id()
        ext = ".pdf" if format_type == "pdf" else ".png"
        mime_type = "application/pdf" if format_type == "pdf" else "image/png"
        category = "docs" if format_type == "pdf" else "images"
        
        # Move capture out of temp
        category_dir = os.path.join(settings.STORAGE_ROOT, category)
        os.makedirs(category_dir, exist_ok=True)
        dest_filename = f"{file_id}{ext}"
        dest_path = os.path.join(category_dir, dest_filename)
        shutil.move(temp_path, dest_path)
        
        final_size = os.path.getsize(dest_path)
        short_url = f"{settings.PUBLIC_BASE_URL}/f/{file_id}"
        
        metadata = {
            "id": file_id,
            "filename": dest_filename,
            "original_name": f"{format_type}_capture{ext}",
            "mime_type": mime_type,
            "size": final_size,
            "hash": file_hash,
            "category": category,
            "path": f"{category}/{dest_filename}",
            "url": short_url,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await db.save_file_metadata(metadata)
        
        return {
            "status": "success",
            "data": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Automation failed: {str(e)}")

@router.post("/automation/capture")
async def capture_page(
    url: str = Form(...),
    format_type: str = Form("screenshot") # screenshot or pdf
):
    return await handle_capture(url, format_type)

@router.post("/capture")
async def capture_page_json(request: CaptureRequest):
    return await handle_capture(request.url, request.format_type)

