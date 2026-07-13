import motor.motor_asyncio
from config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.DATABASE_NAME]

# Collections
files_collection = db["files"]

async def save_file_metadata(metadata: dict):
    """
    Saves or updates file metadata in MongoDB.
    """
    await files_collection.update_one(
        {"id": metadata["id"]},
        {"$set": metadata},
        upsert=True
    )

async def get_file_metadata(file_id: str):
    """
    Retrieves file metadata by its short ID.
    """
    return await files_collection.find_one({"id": file_id})

async def get_file_metadata_by_hash(file_hash: str):
    """
    Retrieves file metadata by its SHA-256 hash.
    Used for duplicate detection.
    """
    return await files_collection.find_one({"hash": file_hash})

async def delete_file_metadata(file_id: str):
    """
    Deletes file metadata from MongoDB.
    """
    await files_collection.delete_one({"id": file_id})

async def get_storage_stats() -> dict:
    """
    Computes storage aggregation metrics (total files, total size, size by category).
    """
    total_files = await files_collection.count_documents({})
    
    pipeline = [
        {
            "$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "total_size": {"$sum": "$size"}
            }
        }
    ]
    
    categories = {}
    total_size = 0
    
    async for doc in files_collection.aggregate(pipeline):
        cat = doc["_id"] or "unknown"
        categories[cat] = {
            "count": doc["count"],
            "size": doc["total_size"]
        }
        total_size += doc["total_size"]
        
    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "categories": categories
    }
