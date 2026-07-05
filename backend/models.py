# models.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    avatar: Optional[str]
    bio: Optional[str]
    status: str
    is_online: bool
    created_at: datetime

class MessageCreate(BaseModel):
    content: str
    chat_id: str
    reply_to: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    content: str
    created_at: datetime
    is_encrypted: bool = False

class ChatCreate(BaseModel):
    name: Optional[str] = None
    is_group: bool = False
    participants: List[str]

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None
    avatar: Optional[str] = None

class UsernameCheck(BaseModel):
    username: str