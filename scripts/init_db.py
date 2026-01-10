"""
Initialize database schema and create initial API key.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_database, async_session_maker, APIKey
from app.auth import generate_api_key
from datetime import datetime, UTC
import uuid


async def create_initial_api_key(service_name: str = "admin"):
    """Create initial API key for testing."""
    raw_key, key_hash = generate_api_key()

    async with async_session_maker() as session:
        api_key = APIKey()
        api_key.id = str(uuid.uuid4())
        api_key.key_hash = key_hash
        api_key.service_name = service_name
        api_key.description = "Initial admin API key"
        api_key.created_at = datetime.now(UTC)
        api_key.revoked = False
        api_key.usage_count = 0

        session.add(api_key)
        await session.commit()

        print(f"\nCreated API key for '{service_name}':")
        print(f"   API Key: {raw_key}")
        print(f"   Key ID: {api_key.id}")
        print(f"\nIMPORTANT: Save this API key now! It cannot be retrieved later.")

        return raw_key


async def main():
    """Main initialization function."""
    print("Initializing database...")

    # Create tables
    await init_database()
    print("Database tables created")

    # Create initial API key
    api_key = await create_initial_api_key()

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
