from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import file
from services.storage import init_storage
from services.db import db
from config import settings

# Initialize directories
init_storage()

app = FastAPI(
    title="SmartUploader Engine",
    description="High performance upload, compression, and automation engine (Self-hosted Cloud)",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_db_client():
    try:
        # Ping the database to check if the connection is alive
        await db.command("ping")
        print("\n✅ [DATABASE] Successfully connected to MongoDB!\n")
    except Exception as e:
        print(f"\n❌ [DATABASE] Failed to connect to MongoDB: {e}\n")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(file.router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SmartUploader Engine",
        "storage_root": settings.STORAGE_ROOT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
