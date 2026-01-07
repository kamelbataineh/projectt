from pyexpat import model
from fastapi import APIRouter, UploadFile, File
import shutil
from tensorflow.keras.models import load_model
import os
from Controller.ai_controller import predict_and_explain
import os
import base64
import cv2
import numpy as np
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from tensorflow.keras.models import load_model
from PIL import Image

from database import predictions_collection

router = APIRouter(prefix="/ai", tags=["AI"])

UPLOAD_DIR = "uploads\image_Ai"
os.makedirs(UPLOAD_DIR, exist_ok=True)




MODEL_PATH = "efficientnetv2l_mammography_3class.h5"
ai_model = load_model(MODEL_PATH)
print("✅ AI model loaded successfully")



@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = predict_and_explain(ai_model, file_path)
    return result




@router.post("/momo")
async def predict(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # حفظ الصورة
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # تشغيل النموذج
    try:
        result = predict_and_explain(ai_model, file_path)  # ⚠ دالة عادية
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"خطأ أثناء تشغيل النموذج: {str(e)}")

    # فحص الثقة
    confidence = max(result["probs"])
    if confidence < 0.6:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="النموذج غير واثق أن الصورة ماموجرام صالحة")

    
    # حفظ النتيجة في MongoDB
    record = {
        "filename": file.filename,
        "uploaded_at": datetime.utcnow(),
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "last_conv_layer": result["last_conv"],
        "findings": result.get("findings", []),
        "recommendations": result.get("recommendations", [])
    }

    # لو تستخدم Motor (async)
    inserted = await predictions_collection.insert_one(record)  

    return {
        "id": str(inserted.inserted_id),  # ✅ تحويل ObjectId إلى string
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "findings": result.get("findings", []),
        "recommendations": result.get("recommendations", [])
    }

# ================== جلب السجلات ==================
@router.get("/records")
def get_records():
    records = list(predictions_collection.find({}, {"_id": 0}))
    return {"records": records}

