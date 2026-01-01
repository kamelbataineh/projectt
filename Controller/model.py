import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from datetime import datetime
from database import predictions_collection
from tensorflow.keras.models import load_model
from mammo_explain import predict_and_explain
import base64
import cv2
import numpy as np

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
model = load_model("efficientnetv2l_mammography_3class.h5")

# تحويل numpy array ل base64
def np_to_base64(img_array):
    _, buffer = cv2.imencode(".png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
    return base64.b64encode(buffer).decode("utf-8")

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # حفظ الصورة
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # تشغيل النموذج + Grad-CAM
    try:
        result = predict_and_explain(model, file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"خطأ بالنموذج: {str(e)}")

    confidence = max(result["probs"])
    if confidence < 0.6:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="النموذج غير واثق أن الصورة ماموجرام صالحة"
        )

    # تحويل overlay + heatmap ل base64
    overlay_b64 = np_to_base64(result["overlay"])
    heatmap_b64 = np_to_base64(result["heatmap"])

    # حفظ كل شيء في MongoDB مع findings و recommendations الحقيقية
    record = {
        "filename": file.filename,
        "uploaded_at": datetime.utcnow(),
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "heatmap": heatmap_b64,
        "overlay": overlay_b64,
        "last_conv_layer": result["last_conv"],
        "findings": result.get("findings", []),            # ← بيانات حقيقية
        "recommendations": result.get("recommendations", [])  # ← بيانات حقيقية
    }
    inserted = predictions_collection.insert_one(record)
    
    # الرد إلى Flutter مع كل البيانات الحقيقية
    return {
        "id": str(inserted.inserted_id),
        "prediction": result["pred_label"],
        "confidence": confidence,
        "probabilities": result["probs"],
        "heatmap": heatmap_b64,
        "overlay": overlay_b64,
        "findings": result.get("findings", []),           # ← بيانات حقيقية
        "recommendations": result.get("recommendations", [])  # ← بيانات حقيقية
    }


@app.get("/records")
def get_records():
    records = list(predictions_collection.find({}, {"_id": 0}))
    return {"records": records}
