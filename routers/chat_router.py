import os
from fastapi import APIRouter, Response, UploadFile, File, Depends, Body
from fastapi.responses import JSONResponse
from Controller.chat_controller import UPLOAD_FOLDER, decrypt_bytes, handle_file_upload, verify_token, get_chats, fetch_messages, send_text_message
from pydantic import BaseModel



router = APIRouter(prefix="/chat")

# ===== Pydantic model للرسالة =====

class MessagePayload(BaseModel):
    receiver_id: str
    message: str
    type: str = "text"  # افتراضي نص



# ===== Send text message =====


# ================== API Endpoints ==================
@router.get("/messages/{other_id}")
async def messages_endpoint(other_id: str, token: dict = Depends(verify_token)):
    user_id = token["id"]
    result = await fetch_messages(user_id, other_id)  # <<-- لازم await
    return JSONResponse(result)

class MessagePayload(BaseModel):
    receiver_id: str
    message: str

@router.post("/send")
async def send_message_endpoint(payload: MessagePayload = Body(...), token: dict = Depends(verify_token)):
    user_id = token["id"]
    receiver_id = payload.receiver_id
    message = payload.message
    result = await send_text_message(user_id, receiver_id, message)
    return JSONResponse(result)

@router.get("/list")
async def list_chats(token: dict = Depends(verify_token)):
    user_id = token["id"]
    chats = await get_chats(user_id)  # هنا await
    return JSONResponse(chats)









