from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

# Load environment variables from the .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env"))

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    logger.error("MONGO_URI is not defined in .env")
    raise ValueError("MONGO_URI not set")

# Global variables for the database client and instance
client = None
db = None

async def connect_to_mongo():
    """
    Establish an async connection to MongoDB via Motor.
    Call this on application startup.
    """
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        # Using "CredenceAI" as the default database name
        db = client.CredenceAI
        
        # Verify the connection by sending a ping
        await client.admin.command('ping')
        logger.info("MongoDB connected successfully to database: CredenceAI")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise e

async def close_mongo_connection():
    """
    Close the MongoDB connection.
    Call this on application shutdown.
    """
    global client
    if client:
        client.close()
        logger.info("🔌 MongoDB connection closed")
        
def get_db():
    """
    Helper function to access the db instance.
    """
    if db is None:
        raise Exception("Database not initialized. Call connect_to_mongo() on startup.")
    return db
