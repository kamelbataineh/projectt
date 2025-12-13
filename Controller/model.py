import os
from fastapi import FastAPI, UploadFile, File
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image as keras_image
import numpy as np
from tensorflow.keras.applications.efficientnet_v2 import preprocess_input as preprocess_efficientnet_v2
from datetime import datetime
from database import predictions_collection  # تأكد استدعاء collection بشكل صحيح

# ===== إعدادات =====
IMG_SIZE = 456
CLASS_NAMES = ["benign", "malignant", "normal"]
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===== FastAPI =====
app = FastAPI()

# ===== تحميل النموذج =====
model = load_model("efficientnetv2l_mammography_3class.h5")

# ===== دالة التنبؤ =====
def predict_image(img_path):
    img = keras_image.load_img(img_path, target_size=(IMG_SIZE, IMG_SIZE))
    x = keras_image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_efficientnet_v2(x)

    preds = model.predict(x)
    pred_idx = int(np.argmax(preds[0]))
    return CLASS_NAMES[pred_idx], preds[0].tolist()

# ===== Endpoint رئيسي للتنبؤ =====
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # حفظ الصورة على السيرفر
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # التنبؤ بالصورة
    label, probs = predict_image(file_path)

    # ===== حفظ البيانات في MongoDB =====
    record = {
        "filename": file.filename,
        "uploaded_at": datetime.utcnow(),
        "prediction": label,
        "probabilities": probs
    }
    inserted = predictions_collection.insert_one(record)

    # إعادة النتيجة مع ID فعلي
    return {
        "prediction": label,
        "probabilities": probs,
        "id": str(inserted.inserted_id)
    }

# ===== Endpoint اختياري لجلب كل السجلات =====
@app.get("/records")
def get_records():
    # جلب السجلات بدون _id ليكون الشكل نظيف
    records = list(predictions_collection.find({}, {"_id": 0}))
    return {"records": records}

