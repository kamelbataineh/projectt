from fastapi import APIRouter, HTTPException, Header, Body, Depends
from fastapi.responses import JSONResponse
from bson import ObjectId
from database import messages_collection, patients_collection, doctors_collection
from datetime import datetime
import os
from cryptography.fernet import Fernet
import jwt
from jwt.exceptions import PyJWTError

router = APIRouter(prefix="/chat")

from PIL import Image
from io import BytesIO

def is_image_file(file_data: bytes) -> bool:
    """
    تتحقق إذا الملف هو صورة صالحة.
    """
    try:
        Image.open(BytesIO(file_data))  # تحاول تفتح البايت كصورة
        return True
    except:
        return False

# ================== إعداد التشفير ==================
SECRET_KEY_FILE = "fernet.key"
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "rb") as f:
        SECRET_KEY = f.read()
else:
    SECRET_KEY = Fernet.generate_key()
    with open(SECRET_KEY_FILE, "wb") as f:
        f.write(SECRET_KEY)
cipher = Fernet(SECRET_KEY)

UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================== Token Verification ==================
JWT_SECRET = "mysecretkey"
ALGORITHM = "HS256"

def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token_value = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token_value, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalid")
        return {"id": user_id}
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalid")

# ================== Helpers ==================
def encrypt_bytes(data: bytes) -> bytes:
    return cipher.encrypt(data)

def decrypt_bytes(data: bytes) -> bytes:
    return cipher.decrypt(data)

# ================== إرسال نص ==================
async def send_text_message(sender_id: str, receiver_id: str, text: str):
    timestamp = datetime.utcnow()
    await messages_collection.insert_one({
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "message_text": text,
        "type": "text",
        "filename": None,
        "timestamp": timestamp,
        "delivered": False
    })
    return {
        "status": "success",
        "message_text": text,
        "type": "text",
        "timestamp": str(timestamp)
    }
# ================== رفع الملفات ==================
async def handle_file_upload(user_id: str, other_id: str, file_data: bytes, filename: str):
    timestamp = datetime.utcnow()

    # تحديد نوع الملف
    is_image = is_image_file(file_data)  # للتحقق من الصور
    is_pdf = filename.lower().endswith(".pdf")
    is_word = filename.lower().endswith((".doc", ".docx"))

    user_folder = os.path.join(UPLOAD_FOLDER, user_id, other_id)
    os.makedirs(user_folder, exist_ok=True)

    file_path = os.path.join(user_folder, filename)
    with open(file_path, "wb") as f:
        f.write(encrypt_bytes(file_data))

    # حفظ المعلومات في الـ MongoDB
    messages_collection.insert_one({
        "sender_id": user_id,
        "receiver_id": other_id,
        "message_text": "" if is_image else file_path,  # الصور فارغة نصيًا
        "type": "image" if is_image else "file",
        "filename": filename,
        "timestamp": timestamp,
        "delivered": False
    })

    # تحديد preview
    preview = f"/chat/preview/{user_id}/{other_id}/{filename}" if is_image else None

    return {
        "status": "success",
        "filename": filename,
        "type": "image" if is_image else "file",
        "preview": preview,
        "timestamp": str(timestamp)
    }

# ================== جلب الرسائل ==================
# ================== جلب الرسائل ==================
async def fetch_messages(user_id: str, other_id: str):
    cursor = messages_collection.find(
        {"$or": [
            {"sender_id": user_id, "receiver_id": other_id},
            {"sender_id": other_id, "receiver_id": user_id}
        ]}
    ).sort("timestamp", 1)

    msgs = await cursor.to_list(length=None)  # <<-- هذا مهم

    result = []
    for m in msgs:
        preview = f"/chat/preview/{m['sender_id']}/{m['receiver_id']}/{m['filename']}" if m['type'] == 'image' else None
        result.append({
            "sender_id": m["sender_id"],
            "receiver_id": m["receiver_id"],
            "message_text": m["message_text"],
            "type": m["type"],
            "filename": m["filename"],
            "preview": preview,
            "timestamp": str(m["timestamp"])
        })
    return result







async def get_chats(user_id: str):
    pipeline = [
        {"$match": {"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": {
                "chat_with": {
                    "$cond": [
                        {"$eq": ["$sender_id", user_id]},
                        "$receiver_id",
                        "$sender_id"
                    ]
                }
            },
            "lastMessage": {"$first": "$message_text"},
            "type": {"$first": "$type"},
            "filename": {"$first": "$filename"},
            "chat_with_id": {
                "$first": {
                    "$cond": [
                        {"$eq": ["$sender_id", user_id]},
                        "$receiver_id",
                        "$sender_id"
                    ]
                }
            },
            "timestamp": {"$first": "$timestamp"}
        }},
        {"$sort": {"timestamp": -1}}
    ]

    chats_cursor = messages_collection.aggregate(pipeline)
    chats = await chats_cursor.to_list(length=None)

    final_list = []

    for c in chats:
        other_id = c["chat_with_id"]

        # ==== اجلب بيانات الشخص من أي مجموعة ====
        user = await doctors_collection.find_one({"_id": ObjectId(other_id)})
        if not user:
            user = await patients_collection.find_one({"_id": ObjectId(other_id)})

        if not user:
            continue

        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        profile_image = user.get("profile_image_url", "")

               # جلب آخر رسالة كاملة من messages_collection
        last_msg_doc = await messages_collection.find_one(
            {"$or": [
                {"sender_id": user_id, "receiver_id": other_id},
                {"sender_id": other_id, "receiver_id": user_id}
            ]},
            sort=[("timestamp", -1)]
        )
        
        if not last_msg_doc:
            continue
        
        final_list.append({
            "chat_with": full_name,
            "chat_with_id": other_id,
            "profile_image_url": profile_image,
            "lastMessage": {
                "message_text": last_msg_doc.get("message_text", ""),
                "sender_id": last_msg_doc.get("sender_id", ""),
                "delivered": last_msg_doc.get("delivered", False),
                "type": last_msg_doc.get("type", "text"),
                "filename": last_msg_doc.get("filename")
            },
            "timestamp": str(last_msg_doc.get("timestamp"))
        })
        

    return final_list








