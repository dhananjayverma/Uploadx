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
