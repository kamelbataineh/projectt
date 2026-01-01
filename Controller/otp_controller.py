# otp_controller
import logging
from fastapi import HTTPException
from datetime import datetime, timedelta
import random, aiosmtplib
from email.mime.text import MIMEText
from jose import jwt
from database import otp_collection, patients_collection  
from motor.motor_asyncio import AsyncIOMotorClient
from model.otp_model import OTPRequest, OTPVerifyRequest
logging.basicConfig(level=logging.INFO)

# ================= SMTP =================
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 465
SMTP_LOGIN = "9b77a8001@smtp-brevo.com"
SMTP_PASSWORD = "WSn3aDfVAKMhJwrd"
FROM_EMAIL = "Pink Scan <douhasharkawi@gmail.com>"

# ================= JWT =================
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

class PatientController:
    
    def startup_event(self):
        otp_collection.create_index("expires", expireAfterSeconds=0)
        logging.info(" TTL index on otp_storage collection is ready.")

    def generate_otp(self):
        return str(random.randint(100000, 999999))

    async def store_otp(self, email: str):
        otp_code = self.generate_otp()
        doc = {
            "email": email, 
            "otp": otp_code,
            "expires": datetime.utcnow() + timedelta(minutes=5),
            "attempts": 0
        }
        result = await otp_collection.update_one({"email": email}, {"$set": doc}, upsert=True)
        logging.info(f"OTP for {email} stored in DB: {otp_code} | Upserted: {result.upserted_id}")
        return otp_code

    async def verify_otp(self, email: str, otp: str):
        entry = await otp_collection.find_one({"email": email})
        if not entry:
            raise HTTPException(status_code=400, detail="لم يتم العثور على كود OTP")
        
        if datetime.utcnow() > entry["expires"]:
            logging.warning(f"OTP for {email} expired at {entry['expires']}")
            await otp_collection.delete_one({"email": email})
            raise HTTPException(status_code=400, detail="انتهت صلاحية OTP")
        
        if entry["attempts"] >= 5:
            raise HTTPException(status_code=400, detail="تم تجاوز عدد المحاولات المسموح بها")
        
        if entry["otp"] != otp:
            await otp_collection.update_one({"email": email}, {"$inc": {"attempts": 1}})
            raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")
        
        await otp_collection.update_one({"email": email}, {"$set": {"verified": True}})
        logging.info(f"OTP for {email} verified successfully (kept in DB)")
        return True

    async def send_email(self, recipient, otp_code):
        message = message = MIMEText(f"""
Pink Scan
-----------------
مرحباً بك في عيادتنا

🔑 رمز التحقق: {otp_code}

شكراً لاختيارك  Pink Scan
""", "plain", "utf-8")
        
        message["From"] = FROM_EMAIL
        message["To"] = recipient
        message["Subject"] = "رمز التحقق (OTP)"

        try:
            await aiosmtplib.send(
                message,
                hostname=SMTP_SERVER,
                port=SMTP_PORT,
                start_tls=True,
                username=SMTP_LOGIN,
                password=SMTP_PASSWORD,
            )
            logging.info(f"OTP sent to {recipient}")
        except Exception as e:
            logging.error(f" Error sending email to {recipient}: {e}")
            raise HTTPException(status_code=500, detail="فشل إرسال البريد الإلكتروني")

    def create_access_token(self, username: str, patient_id: str, expires_delta: timedelta = timedelta(hours=2)):
        expire = datetime.utcnow() + expires_delta
        payload = {"sub": username, "id": patient_id, "role": "patient", "exp": expire}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    async def send_otp_endpoint(self, request: OTPRequest):
        patient = await patients_collection.find_one({"email": request.email})
        if not patient:
            raise HTTPException(status_code=404, detail="البريد غير مسجل")
        
        otp_code = await self.store_otp(request.email)
        await self.send_email(request.email, otp_code)
        return {"message": "تم إرسال رمز التحقق إلى البريد الإلكتروني"}

    async def verify_login_otp(self, request: OTPVerifyRequest):
        patient = await patients_collection.find_one({"email": request.email})
        if not patient:
            raise HTTPException(status_code=404, detail="البريد غير مسجل")
        
        await self.verify_otp(request.email, request.otp)
        token = self.create_access_token(patient["username"], str(patient["_id"]))
        return {
            "message": f"مرحباً {patient['first_name']}!",
            "access_token": token,
            "token_type": "bearer",
            "patient_id": str(patient["_id"])
        }

# إنشاء instance من ال controller
patient_controller = PatientController()