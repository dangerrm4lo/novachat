# migrate.py — скрипт для миграции БД
import asyncio
import asyncpg
from config import settings
from crypto import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate")

async def migrate():
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        logger.info("✅ Connected to database")
        
        # Добавляем поля
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT")
        await conn.execute("ALTER TABLE users ALTER COLUMN avatar TYPE TEXT")
        
        # Создаём администратора dangerrm4lo
        admin = await conn.fetchrow("SELECT id FROM users WHERE username = 'dangerrm4lo'")
        if not admin:
            hashed, salt = hash_password("admin123")
            await conn.execute("""
                INSERT INTO users (username, email, password_hash, full_name, is_admin)
                VALUES ($1, $2, $3, $4, $5)
            """, "dangerrm4lo", "admin@novachat.com", hashed, "Администратор NovaChat", True)
            logger.info("✅ Admin user 'dangerrm4lo' created")
        else:
            logger.info("✅ Admin user 'dangerrm4lo' already exists")
        
        await conn.close()
        logger.info("✅ Migration completed")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate())