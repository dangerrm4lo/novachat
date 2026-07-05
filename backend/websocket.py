# websocket.py - менеджер WebSocket соединений
from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_rooms: Dict[str, str] = {}  # user_id -> chat_id
        self.room_members: Dict[str, Set[str]] = {}  # chat_id -> set(user_id)
    
    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"[WS] Пользователь {user_id} подключен")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        # Удаляем из комнат
        if user_id in self.user_rooms:
            room = self.user_rooms[user_id]
            if room in self.room_members:
                self.room_members[room].discard(user_id)
            del self.user_rooms[user_id]
        print(f"[WS] Пользователь {user_id} отключен")
    
    async def send_to_user(self, user_id: str, data: dict):
        """Отправить сообщение конкретному пользователю"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(data))
                return True
            except:
                self.disconnect(user_id)
        return False
    
    async def send_to_room(self, chat_id: str, data: dict, exclude: str = None):
        """Отправить сообщение всем участникам комнаты"""
        if chat_id not in self.room_members:
            return
        
        for user_id in self.room_members[chat_id]:
            if user_id == exclude:
                continue
            await self.send_to_user(user_id, data)
    
    def join_room(self, user_id: str, chat_id: str):
        """Добавить пользователя в комнату"""
        # Выходим из старой комнаты
        if user_id in self.user_rooms:
            old_room = self.user_rooms[user_id]
            if old_room in self.room_members:
                self.room_members[old_room].discard(user_id)
        
        self.user_rooms[user_id] = chat_id
        if chat_id not in self.room_members:
            self.room_members[chat_id] = set()
        self.room_members[chat_id].add(user_id)
    
    def get_room_members(self, chat_id: str) -> Set[str]:
        """Получить список участников комнаты"""
        return self.room_members.get(chat_id, set())
    
    async def broadcast_system(self, message: str):
        """Широковещательное системное сообщение"""
        data = {"type": "system", "content": message, "timestamp": datetime.now().isoformat()}
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, data)

# Глобальный экземпляр
manager = ConnectionManager()