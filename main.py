# main.py
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image as keras_image
import numpy as np
from tensorflow.keras.applications.efficientnet_v2 import preprocess_input as preprocess_efficientnet_v2
from datetime import datetime, timedelta
import logging
import os
from Controller.appointment_controller import send_daily_doctor_notifications
from Controller.patient_controller import patient_controller 
from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
# Routers
from apscheduler.triggers.cron import CronTrigger
import pytz  
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routers import chat_router, patient_router 
from routers import dector_router
from routers import appointment_router
from routers import admin_router
from routers import record_router

# إنشاء التطبيق
app = FastAPI()

# الصفحة الرئيسية
@app.get("/")
def read_root():
    return {"message": "🚀 Server is running with auto-reload!"}

# =============== Include Routers ===============
app.include_router(patient_router.router)
app.include_router(dector_router.router)
app.include_router(appointment_router.router)
app.include_router(admin_router.router)
app.include_router(chat_router.router)
app.include_router(record_router.router)
# للصور
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")




# ============== Logging ===============
logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def startup_event():
    await patient_controller.startup_event()
    
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Amman"))
    
    # جدول يومي الساعة 18:00
    scheduler.add_job(
        send_daily_doctor_notifications,
        trigger=CronTrigger(hour=13, minute=0, day_of_week='mon-thu,sat')
    )
    
    scheduler.start()
    print(f"✅ تم تشغيل Scheduler وسيتم إرسال الإيميل الساعة 18:00")
    
    # # 👈 إرسال تجريبي الآن
    # await send_daily_doctor_notifications()
    # print("✅ تم إرسال الإيميل التجريبي الآن")


IMG_SIZE = 456
CLASS_NAMES = ["benign", "malignant", "normal"]

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    label, probs = predict_image(file_path)
    return {"prediction": label, "probabilities": probs}


model = load_model("efficientnetv2l_mammography_3class.h5")

def predict_image(img_path):
    img = keras_image.load_img(img_path, target_size=(IMG_SIZE, IMG_SIZE))
    x = keras_image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_efficientnet_v2(x)
    
    preds = model.predict(x)
    pred_idx = np.argmax(preds[0])
    return CLASS_NAMES[pred_idx], preds[0].tolist()
