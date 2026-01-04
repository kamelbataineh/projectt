import os
import base64
import cv2
import numpy as np
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from tensorflow.keras.models import load_model
from PIL import Image

from database import predictions_collection
from mammo_explain import predict_and_explain

# ================== إعدادات ==================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
model = load_model("efficientnetv2l_mammography_3class.h5")

# ================== فحص شكلي (ماموجرام ولا لأ) ==================
def is_likely_mammogram(image_path: str) -> bool:
    img = Image.open(image_path)

    # تحويل إجباري إلى grayscale
    gray = img.convert("L")
    img_array = np.array(gray)

    # لازم تكون قناة وحدة فقط
    if len(img_array.shape) != 2:
        return False

    # حجم منطقي
    width, height = gray.size
    if width < 300 or height < 300:
        return False

    return True


# ================== تحويل numpy → base64 ==================
def np_to_base64(img_array):
    _, buffer = cv2.imencode(
        ".png",
        cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    )
    return base64.b64encode(buffer).decode("utf-8")

# ================== Endpoint التنبؤ ==================
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # حفظ الصورة
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 1️⃣ فحص شكلي قبل تشغيل النموذج
    if not is_likely_mammogram(file_path):
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="الصورة المرفوعة ليست صورة ماموجرام"
        )

    # 2️⃣ تشغيل النموذج + Grad-CAM
    try:
        result = predict_and_explain(model, file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"خطأ أثناء تشغيل النموذج: {str(e)}"
        )

    # 3️⃣ فحص الثقة
    confidence = max(result["probs"])
    if confidence < 0.6:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="النموذج غير واثق أن الصورة ماموجرام صالحة"
        )

    # 4️⃣ تحويل Grad-CAM إلى base64
    overlay_b64 = np_to_base64(result["overlay"])
    heatmap_b64 = np_to_base64(result["heatmap"])

    # 5️⃣ حفظ النتيجة في MongoDB
    record = {
        "filename": file.filename,
        "uploaded_at": datetime.utcnow(),
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "heatmap": heatmap_b64,
        "overlay": overlay_b64,
        "last_conv_layer": result["last_conv"],
        "findings": result.get("findings", []),
        "recommendations": result.get("recommendations", [])
    }

    inserted = predictions_collection.insert_one(record)

    # 6️⃣ الرد إلى Flutter
    return {
        "id": str(inserted.inserted_id),
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "heatmap": heatmap_b64,
        "overlay": overlay_b64,
        "findings": result.get("findings", []),
        "recommendations": result.get("recommendations", [])
    }

# ================== جلب السجلات ==================
@app.get("/records")
def get_records():
    records = list(predictions_collection.find({}, {"_id": 0}))
    return {"records": records}
