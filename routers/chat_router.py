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

# ===== Upload file =====
@router.post("/upload_file/{other_id}")
async def upload_file(other_id: str, file: UploadFile = File(...), token: dict = Depends(verify_token)):
    user_id = token["id"]
    file_data = await file.read()
    result = await handle_file_upload(user_id, other_id, file_data, file.filename)
    return JSONResponse(result)


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



@router.post("/upload_file/{other_id}")
async def upload_file(other_id: str, file: UploadFile = File(...), token: str = Depends(verify_token)):
    user_id = token["id"]
    file_data = await file.read()
    result = await handle_file_upload(user_id, other_id, file_data, file.filename)
    return JSONResponse(result)



UPLOAD_FOLDER = "uploads"  # تأكد أن نفس المسار

@router.get("/preview/{user_id}/{other_id}/{filename}")
async def preview_file(user_id: str, other_id: str, filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, user_id, other_id, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    with open(file_path, "rb") as f:
        decrypted_data = decrypt_bytes(f.read())
    
    return Response(content=decrypted_data, media_type="image/jpeg")  # أو type المناسب






