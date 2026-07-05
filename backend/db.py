# db.py — SQLite версия
import aiosqlite
from typing import Optional, Any
from datetime import datetime
import uuid
import os
import logging
import json

logger = logging.getLogger("nova-db")

class Database:
    _db: Optional[aiosqlite.Connection] = None
    
    @classmethod
    async def connect(cls):
        if cls._db is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'messenger.db')
            cls._db = await aiosqlite.connect(db_path)
            cls._db.row_factory = aiosqlite.Row
            await cls._init_tables()
            logger.info(f"✅ SQLite connected: {db_path}")
        return cls._db
    
    @classmethod
    async def _init_tables(cls):
        # Таблица пользователей
        await cls._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                avatar TEXT,
                bio TEXT,
                status TEXT DEFAULT 'online',
                is_admin INTEGER DEFAULT 0,
                is_online INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица чатов
        await cls._db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                name TEXT,
                is_group INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT REFERENCES users(id)
            )
        """)
        
        # Участники чатов
        await cls._db.execute("""
            CREATE TABLE IF NOT EXISTS chat_participants (
                chat_id TEXT REFERENCES chats(id) ON DELETE CASCADE,
                user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        
        # Сообщения
        await cls._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT REFERENCES chats(id) ON DELETE CASCADE,
                sender_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                content TEXT NOT NULL,
                is_encrypted INTEGER DEFAULT 0,
                reply_to TEXT REFERENCES messages(id),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                edited_at TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        
        # Индексы для скорости
        await cls._db.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
        await cls._db.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC)")
        await cls._db.execute("CREATE INDEX IF NOT EXISTS idx_chat_participants_user_id ON chat_participants(user_id)")
        await cls._db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        
        await cls._db.commit()
        logger.info("✅ SQLite tables initialized")
    
    @classmethod
    async def execute(cls, query: str, *args) -> Any:
        db = await cls.connect()
        cursor = await db.execute(query, args)
        return await cursor.fetchall()
    
    @classmethod
    async def execute_row(cls, query: str, *args) -> Any:
        db = await cls.connect()
        cursor = await db.execute(query, args)
        return await cursor.fetchone()
    
    @classmethod
    async def execute_val(cls, query: str, *args) -> Any:
        db = await cls.connect()
        cursor = await db.execute(query, args)
        row = await cursor.fetchone()
        return row[0] if row else None
    
    @classmethod
    async def close(cls):
        if cls._db:
            await cls._db.close()
            cls._db = None
    
    # ===== PROFILE METHODS =====
    
    @classmethod
    async def get_profile(cls, user_id: str) -> Optional[dict]:
        db = await cls.connect()
        cursor = await db.execute("""
            SELECT id, username, email, full_name, bio, avatar, status, 
                   is_online, is_admin, last_seen, created_at, updated_at
            FROM users 
            WHERE id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    @classmethod
    async def update_profile(cls, user_id: str, data: dict) -> bool:
        fields = []
        values = []
        
        for key, value in data.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(user_id)
        query = f"""
            UPDATE users 
            SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        
        db = await cls.connect()
        cursor = await db.execute(query, values)
        await db.commit()
        return cursor.rowcount > 0
    
    @classmethod
    async def check_username_available(cls, username: str, exclude_user_id: str = None) -> bool:
        query = "SELECT id FROM users WHERE username = ?"
        params = [username]
        if exclude_user_id:
            query += " AND id != ?"
            params.append(exclude_user_id)
        db = await cls.connect()
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row is None
    
    # ===== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ =====
    
    @classmethod
    async def create_user(cls, user_id: str, username: str, email: str, password_hash: str, full_name: str = None) -> bool:
        db = await cls.connect()
        await db.execute("""
            INSERT INTO users (id, username, email, password_hash, full_name)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, email, password_hash, full_name))
        await db.commit()
        return True
    
    @classmethod
    async def get_user_by_username(cls, username: str) -> Optional[dict]:
        db = await cls.connect()
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None