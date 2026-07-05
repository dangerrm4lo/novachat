from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import json
from datetime import datetime
import uuid
import os
import logging
from config import settings
from db import Database
from websocket import manager
from crypto import hash_password, generate_session_token
from models import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nova-api")

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
logger.info(f"📁 Frontend path: {frontend_path}")

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    logger.info("✅ Static files mounted at /static")

# ===== ГЛАВНАЯ СТРАНИЦА - РЕДИРЕКТ НА LOGIN =====
@app.get("/")
async def serve_index():
    # Всегда редиректим на login.html
    return RedirectResponse(url="/login.html")

@app.get("/chat")
async def serve_chat():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "error", "message": "index.html not found"}

@app.get("/login.html")
async def serve_login():
    login_path = os.path.join(frontend_path, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return {"status": "error", "message": "login.html not found"}

@app.get("/profile.html")
async def serve_profile():
    profile_path = os.path.join(frontend_path, "profile.html")
    if os.path.exists(profile_path):
        return FileResponse(profile_path)
    return {"status": "error", "message": "profile.html not found"}

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    full_path = os.path.join(frontend_path, file_path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    return {"status": "error", "message": f"File not found: {file_path}"}

# ===== API =====
@app.get("/api")
async def root():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

# ===== AUTH =====
@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    existing = await Database.execute_row(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        user_data.username, user_data.email
    )
    if existing:
        raise HTTPException(400, "Пользователь с таким email или username уже существует")
    
    hashed, salt = hash_password(user_data.password)
    user_id = str(uuid.uuid4())
    
    await Database.execute(
        "INSERT INTO users (id, username, email, password_hash, full_name) VALUES (?, ?, ?, ?, ?)",
        user_id, user_data.username, user_data.email, hashed, user_data.full_name
    )
    return {"status": "success", "user_id": user_id}

@app.post("/api/auth/login")
async def login(login_data: UserLogin):
    user = await Database.execute_row(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        login_data.username
    )
    if not user:
        raise HTTPException(401, "Неверный логин или пароль")
    
    token = generate_session_token()
    return {"status": "success", "token": token, "user_id": str(user["id"])}

# ===== USERS =====
@app.get("/api/users")
async def get_users():
    users = await Database.execute(
        "SELECT id, username, full_name, avatar, is_online, status FROM users ORDER BY username"
    )
    return [dict(u) for u in users]

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    user = await Database.execute_row(
        "SELECT id, username, email, full_name, avatar, bio, status, is_online, created_at FROM users WHERE id = ?",
        user_id
    )
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return dict(user)

# ===== PROFILE =====
@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
    if not user:
        await Database.execute(
            "INSERT INTO users (id, username, full_name, status) VALUES (?, ?, ?, ?)",
            user_id, user_id[:8], "Новый пользователь", "online"
        )
        logger.info(f"👤 Auto-created user for profile: {user_id}")
    
    profile = await Database.get_profile(user_id)
    if not profile:
        raise HTTPException(404, "Пользователь не найден")
    return profile

@app.put("/api/profile/{user_id}")
async def update_profile(user_id: str, data: ProfileUpdate):
    user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    if data.username:
        if len(data.username) < 3 or len(data.username) > 30:
            raise HTTPException(400, "Юзернейм должен быть от 3 до 30 символов")
        available = await Database.check_username_available(data.username, user_id)
        if not available:
            raise HTTPException(400, "Юзернейм уже занят")
    
    update_data = {}
    if data.full_name is not None:
        update_data["full_name"] = data.full_name
    if data.username is not None:
        update_data["username"] = data.username
    if data.bio is not None:
        update_data["bio"] = data.bio
    if data.status is not None:
        valid_statuses = ["online", "away", "busy", "offline"]
        if data.status not in valid_statuses:
            raise HTTPException(400, f"Недопустимый статус. Доступны: {', '.join(valid_statuses)}")
        update_data["status"] = data.status
    if data.avatar is not None:
        update_data["avatar"] = data.avatar
    
    if not update_data:
        raise HTTPException(400, "Нет данных для обновления")
    
    success = await Database.update_profile(user_id, update_data)
    if not success:
        raise HTTPException(500, "Ошибка обновления профиля")
    
    return {"status": "success", "message": "Профиль обновлён"}

@app.post("/api/profile/check-username")
async def check_username(data: UsernameCheck):
    if len(data.username) < 3 or len(data.username) > 30:
        return {"username": data.username, "available": False}
    available = await Database.check_username_available(data.username)
    return {"username": data.username, "available": available}

# ===== CHATS =====
@app.get("/api/chats/{user_id}")
async def get_user_chats(user_id: str):
    chats = await Database.execute("""
        SELECT c.id, c.name, c.is_group, c.created_at,
               (SELECT content FROM messages m WHERE m.chat_id = c.id ORDER BY m.created_at DESC LIMIT 1) as last_message
        FROM chats c
        JOIN chat_participants cp ON cp.chat_id = c.id
        WHERE cp.user_id = ?
        ORDER BY c.created_at DESC
    """, user_id)
    return [dict(c) for c in chats]

@app.post("/api/chats")
async def create_chat(chat_data: ChatCreate):
    chat_id = str(uuid.uuid4())
    await Database.execute(
        "INSERT INTO chats (id, name, is_group) VALUES (?, ?, ?)",
        chat_id, chat_data.name, 1 if chat_data.is_group else 0
    )
    for user_id in chat_data.participants:
        await Database.execute(
            "INSERT INTO chat_participants (chat_id, user_id) VALUES (?, ?)",
            chat_id, user_id
        )
    return {"status": "success", "chat_id": chat_id}

# ===== MESSAGES =====
@app.get("/api/messages/{chat_id}")
async def get_messages(chat_id: str, limit: int = 50, offset: int = 0):
    messages = await Database.execute("""
        SELECT m.id, m.sender_id, m.content, m.created_at, u.username, u.full_name
        FROM messages m
        LEFT JOIN users u ON u.id = m.sender_id
        WHERE m.chat_id = ? AND m.is_deleted = 0
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
    """, chat_id, limit, offset)
    return [dict(m) for m in messages]

@app.post("/api/messages")
async def send_message(msg_data: MessageCreate):
    msg_id = str(uuid.uuid4())
    await Database.execute(
        "INSERT INTO messages (id, chat_id, sender_id, content) VALUES (?, ?, ?, ?)",
        msg_id, msg_data.chat_id, None, msg_data.content
    )
    return {"status": "success", "message_id": msg_id}

# ===== SYSTEM: SUPPORT CHAT =====
@app.post("/api/system/create-support-chat/{user_id}")
async def create_support_chat(user_id: str):
    logger.info(f"📨 Creating support chat for user_id: {user_id}")
    
    user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
    if not user:
        logger.info(f"👤 Auto-creating user: {user_id}")
        await Database.execute(
            "INSERT INTO users (id, username, full_name, status) VALUES (?, ?, ?, ?)",
            user_id, user_id[:8], "Новый пользователь", "online"
        )
        user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
        if not user:
            logger.error(f"❌ Failed to create user: {user_id}")
            raise HTTPException(500, "Не удалось создать пользователя")
    
    admin = await Database.execute_row("SELECT id FROM users WHERE username = 'dangerrm4lo'")
    if not admin:
        logger.info("👤 Creating admin user 'dangerrm4lo'...")
        admin_id = str(uuid.uuid4())
        hashed, salt = hash_password("admin123")
        await Database.execute(
            "INSERT INTO users (id, username, email, password_hash, full_name, is_admin, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            admin_id, "dangerrm4lo", "admin@novachat.com", hashed, "Администратор NovaChat", 1, "online"
        )
        admin = {"id": admin_id}
        logger.info(f"✅ Admin user 'dangerrm4lo' created with id: {admin_id}")
    
    existing = await Database.execute_row("""
        SELECT c.id FROM chats c
        JOIN chat_participants cp1 ON cp1.chat_id = c.id AND cp1.user_id = ?
        JOIN chat_participants cp2 ON cp2.chat_id = c.id AND cp2.user_id = ?
        WHERE c.is_group = 0
    """, user_id, admin["id"])
    
    if existing:
        logger.info(f"✅ Support chat already exists: {existing['id']}")
        return {"status": "success", "chat_id": str(existing["id"]), "exists": True}
    
    chat_id = str(uuid.uuid4())
    await Database.execute(
        "INSERT INTO chats (id, name, is_group) VALUES (?, ?, ?)",
        chat_id, "Поддержка NovaChat", 0
    )
    await Database.execute(
        "INSERT INTO chat_participants (chat_id, user_id) VALUES (?, ?)",
        chat_id, user_id
    )
    await Database.execute(
        "INSERT INTO chat_participants (chat_id, user_id) VALUES (?, ?)",
        chat_id, admin["id"]
    )
    
    rules = (
        "👋 Привет! Я dangerrm4lo, создатель NovaChat.\n"
        "Задавай любые вопросы по проекту.\n\n"
        "📋 Правила чата:\n"
        "1️⃣ Без спама и флуда\n"
        "2️⃣ Уважай собеседника\n"
        "3️⃣ Задавай конкретные вопросы\n"
        "4️⃣ Я отвечаю в течение 24 часов"
    )
    
    msg_id = str(uuid.uuid4())
    await Database.execute(
        "INSERT INTO messages (id, chat_id, sender_id, content) VALUES (?, ?, ?, ?)",
        msg_id, chat_id, admin["id"], rules
    )
    
    return {"status": "success", "chat_id": chat_id, "exists": False}

# ===== WEBSOCKET =====
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    try:
        user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
        if not user:
            logger.info(f"👤 Auto-creating user from WebSocket: {user_id}")
            await Database.execute(
                "INSERT INTO users (id, username, full_name, status) VALUES (?, ?, ?, ?)",
                user_id, user_id[:8], "Новый пользователь", "online"
            )
            user = await Database.execute_row("SELECT id FROM users WHERE id = ?", user_id)
            if not user:
                await websocket.close(code=1008, reason="User creation failed")
                return
        
        await manager.connect(user_id, websocket)
        await Database.execute(
            "UPDATE users SET is_online = 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
            user_id
        )
        logger.info(f"🔌 WebSocket connected: {user_id}")
        
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    msg_type = message.get("type", "message")
                    
                    if msg_type == "message":
                        chat_id = message.get("to")
                        content = message.get("content")
                        if chat_id and content:
                            msg_id = str(uuid.uuid4())
                            await Database.execute(
                                "INSERT INTO messages (id, chat_id, sender_id, content) VALUES (?, ?, ?, ?)",
                                msg_id, chat_id, user_id, content
                            )
                            response = {
                                "type": "message",
                                "id": msg_id,
                                "from": user_id,
                                "content": content,
                                "timestamp": datetime.now().isoformat()
                            }
                            await manager.send_to_room(chat_id, response, exclude=user_id)
                            await manager.send_to_user(user_id, {
                                "type": "delivered",
                                "message_id": msg_id
                            })
                    
                    elif msg_type == "join":
                        chat_id = message.get("chat_id")
                        if chat_id:
                            manager.join_room(user_id, chat_id)
                            history = await Database.execute(
                                "SELECT id, sender_id, content, created_at FROM messages WHERE chat_id = ? ORDER BY created_at LIMIT 50",
                                chat_id
                            )
                            messages_data = [
                                {
                                    "id": str(m["id"]),
                                    "from": str(m["sender_id"]),
                                    "content": m["content"],
                                    "timestamp": m["created_at"]
                                }
                                for m in history
                            ]
                            await manager.send_to_user(user_id, {
                                "type": "history",
                                "messages": messages_data
                            })
                    
                    elif msg_type == "typing":
                        chat_id = message.get("chat_id")
                        is_typing = message.get("is_typing", False)
                        if chat_id:
                            await manager.send_to_room(chat_id, {
                                "type": "typing",
                                "from": user_id,
                                "is_typing": is_typing
                            }, exclude=user_id)
                
                except json.JSONDecodeError:
                    await manager.send_to_user(user_id, {
                        "type": "error",
                        "content": "Invalid JSON"
                    })
        
        except WebSocketDisconnect:
            manager.disconnect(user_id)
            await Database.execute(
                "UPDATE users SET is_online = 0, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                user_id
            )
            logger.info(f"🔌 WebSocket disconnected: {user_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

# ===== RUN =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info")