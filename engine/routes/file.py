import os
import shutil
import hashlib
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timedelta

from config import settings
from services import storage, db, compressor, automation, stego

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    compress: bool = Form(True),
    autoFormat: bool = Form(True),
    maxSize: str = Form(None),  # e.g., "100MB" (Node.js layer will also handle validation)
    expires_in_mins: int = Form(None),
    burn_on_read: bool = Form(False),
    access: str = Form("public"),
    password: str = Form(None),
    stego_text: str = Form(None)
):
    expires_at = None
    if expires_in_mins:
        expires_at = (datetime.utcnow() + timedelta(minutes=expires_in_mins)).isoformat()
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
    has_stego = False
    
    # Create final directory just in case
    category_dir = os.path.join(settings.STORAGE_ROOT, category)
    os.makedirs(category_dir, exist_ok=True)
    
    # Steganographic pixel lock (Image only)
    if stego_text and category == "images":
        # Force lossless PNG to preserve stego pixel bits
        final_ext = ".png"
        mime_type = "image/png"
        dest_name = f"{file_id}{final_ext}"
        dest_path = os.path.join(category_dir, dest_name)
        success = stego.encode_text_in_image(temp_path, stego_text, dest_path)
        if success:
            final_path = dest_path
            has_stego = True
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    if not final_path and compress:
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
        # Clean up temp file since we compressed/encoded it to a new path
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
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at,
        "burn_on_read": burn_on_read,
        "access": access,
        "password": password,
        "has_stego": has_stego
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
    
    # If the file has a stego payload, decode it on the fly and return it
    if metadata.get("has_stego"):
        filepath = os.path.join(settings.STORAGE_ROOT, metadata["path"])
        if os.path.exists(filepath):
            metadata["stego_text"] = stego.decode_text_from_image(filepath)
            
    return {
        "status": "success",
        "data": metadata
    }

@router.get("/f/{file_id}")
async def serve_file(
    file_id: str,
    w: int = None, # width
    h: int = None, # height
    q: int = None,  # quality (1-100)
    password: str = None,
    token: str = None,
    authorization: str = Header(None)
):
    metadata = await db.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")

    # 1. Access Control Check (Public vs Private)
    if metadata.get("access") == "private":
        bearer_token = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer_token = authorization.split(" ")[1]
        
        client_token = token or bearer_token
        if client_token != settings.SECRET_KEY:
            raise HTTPException(status_code=403, detail="Access forbidden: Invalid or missing authentication token")

    # 2. Password Protection Check
    expected_password = metadata.get("password")
    if expected_password:
        if password != expected_password:
            raise HTTPException(status_code=401, detail="Access denied: Password protected resource")
        
    # Check Expiry
    if metadata.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(metadata["expires_at"])
            if datetime.utcnow() > expires_at:
                # File has expired! Clean it up from disk and DB
                storage.delete_physical_file(metadata["category"], metadata["filename"])
                await db.delete_file_metadata(file_id)
                raise HTTPException(status_code=410, detail="File link has expired")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            pass # Ignore parsing exceptions and proceed

    filepath = os.path.join(settings.STORAGE_ROOT, metadata["path"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Physical file not found on disk")

    # Burn-on-Read handler
    is_burn = metadata.get("burn_on_read", False)

    # Dynamic Image CDN
    is_image = metadata.get("mime_type", "").startswith("image/")
    if is_image and (w or h or q):
        try:
            # Process the image on-the-fly and return a streaming response
            from PIL import Image
            import io
            from fastapi.responses import StreamingResponse

            img = Image.open(filepath)
            img_format = img.format or "WEBP"

            # Resize logic preserving aspect ratio if only width or height is provided
            if w or h:
                width = w or img.width
                height = h or img.height
                if w and not h:
                    aspect = img.height / img.width
                    height = int(w * aspect)
                elif h and not w:
                    aspect = img.width / img.height
                    width = int(h * aspect)
                
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            # Quality compression and saving
            img_io = io.BytesIO()
            save_kwargs = {"format": img_format}
            if q is not None:
                quality_val = max(1, min(100, q))
                if img_format.upper() in ["JPEG", "JPG", "WEBP"]:
                    save_kwargs["quality"] = quality_val
            
            img.save(img_io, **save_kwargs)
            img_io.seek(0)

            # Clean up immediately if marked as burn-on-read
            if is_burn:
                storage.delete_physical_file(metadata["category"], metadata["filename"])
                await db.delete_file_metadata(file_id)

            return StreamingResponse(img_io, media_type=metadata["mime_type"])
        except Exception as e:
            print(f"CDN processing failed: {e}")
            pass

    # If it is burn-on-read, retrieve bytes first, delete, and return
    if is_burn:
        with open(filepath, "rb") as f:
            file_bytes = f.read()
        storage.delete_physical_file(metadata["category"], metadata["filename"])
        await db.delete_file_metadata(file_id)
        from fastapi.responses import Response
        return Response(content=file_bytes, media_type=metadata["mime_type"])

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

@router.get("/api/stats")
async def get_stats():
    try:
        stats = await db.get_storage_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

@router.get("/api/files")
async def get_files(category: str = None, search: str = None):
    try:
        files = await db.list_files(category, search)
        return {
            "status": "success",
            "data": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query files: {str(e)}")

from pydantic import BaseModel

class CaptureRequest(BaseModel):
    url: str
    format_type: str = "screenshot" # screenshot or pdf
    expires_in_mins: int = None
    burn_on_read: bool = False
    access: str = "public"
    password: str = None
    full_page: bool = True
    color_scheme: str = "light"
    delay: int = 0
    width: int = 1920
    height: int = 1080

async def handle_capture(
    url: str,
    format_type: str,
    expires_in_mins: int = None,
    burn_on_read: bool = False,
    access: str = "public",
    password: str = None,
    full_page: bool = True,
    color_scheme: str = "light",
    delay: int = 0,
    width: int = 1920,
    height: int = 1080
):
    try:
        temp_path = await automation.capture_url(
            url=url,
            format_type=format_type,
            full_page=full_page,
            color_scheme=color_scheme,
            delay=delay,
            width=width,
            height=height
        )
        
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
        
        expires_at = None
        if expires_in_mins:
            expires_at = (datetime.utcnow() + timedelta(minutes=expires_in_mins)).isoformat()

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
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "burn_on_read": burn_on_read,
            "access": access,
            "password": password
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
    format_type: str = Form("screenshot"), # screenshot or pdf
    expires_in_mins: int = Form(None),
    burn_on_read: bool = Form(False),
    access: str = Form("public"),
    password: str = Form(None),
    full_page: bool = Form(True),
    color_scheme: str = Form("light"),
    delay: int = Form(0),
    width: int = Form(1920),
    height: int = Form(1080)
):
    return await handle_capture(
        url, format_type, expires_in_mins, burn_on_read, access, password,
        full_page, color_scheme, delay, width, height
    )

@router.post("/capture")
async def capture_page_json(request: CaptureRequest):
    return await handle_capture(
        url=request.url,
        format_type=request.format_type,
        expires_in_mins=request.expires_in_mins,
        burn_on_read=request.burn_on_read,
        access=request.access,
        password=request.password,
        full_page=request.full_page,
        color_scheme=request.color_scheme,
        delay=request.delay,
        width=request.width,
        height=request.height
    )

