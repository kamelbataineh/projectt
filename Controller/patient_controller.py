
#
#----------------------------------------
#
##
###
####
#####
######
#######
########
#########
##########
#########
########
#######
######
#####
####
###
##
#
#----------------------------------------
#

# patient_controller.py
#
##
###
####
#####
######
#######
########
#########
##########
import os
import aiosmtplib
from email.mime.text import MIMEText
import logging
import random
from database import otp_collection, patients_collection  , temp_patients_collection
from Controller.otp_controller import PatientController
from fastapi import HTTPException, Depends, Request, status
from passlib.context import CryptContext
from model.otp_model import OTPRequest, OTPVerifyRequest
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from bson import ObjectId
from Controller.otp_controller import PatientController
from fastapi import UploadFile
from database import mongo_db
##########
#########
########
#######
######
#####
####
###
##
#
# ================== استدعاء الاتصال من database.py ==================
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 465
SMTP_LOGIN = "9b77a8001@smtp-brevo.com"
SMTP_PASSWORD = "WSn3aDfVAKMhJwrd"
FROM_EMAIL = "عياده الامل <douhasharkawi@gmail.com>"
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
patient_controller = PatientController()
patients_collection = mongo_db["patients"]
doctors_collection = mongo_db["doctors"]

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
blacklisted_tokens = set()
UPLOAD_DIR = "static/patient_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/patients/login")

#
##
###
##
#
conf = ConnectionConfig(
    MAIL_USERNAME="douh@gmail.com",
    MAIL_PASSWORD="douhash",
    MAIL_FROM="douh@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)
#
##
###
##
#
# ================== النماذج ==================
class CreatePatientRequest(BaseModel):
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    phone_number: str

class LoginPatientRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

class ChangePasswordRequest(BaseModel):
    email: str          
    new_password: str    

class UpdatePatientRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    profile_image_url: Optional[str] = None  


class TokenResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
#
#----------------------------------------
#
##
###
####
#####
######
#######           confirm_registration
########          register_patient
#########         login_patient
##########        update_patient
#########         logout_patient
########
#######
######
#####
####
###
##
#
#----------------------------------------
#
#
#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
#
async def confirm_registration(email: str, otp: str):
    # تحقق من OTP
    await patient_controller.verify_otp(email, otp)

    # جلب بيانات المريض المؤقتة
    temp_user = await temp_patients_collection.find_one({"email": email})
    if not temp_user:
        raise HTTPException(status_code=404, detail="No registration request found")

    # إنشاء الحساب في قاعدة البيانات الرئيسية
    new_patient = {
        "email": temp_user["email"],
        "username": temp_user["username"],
        "first_name": temp_user["first_name"],
        "last_name": temp_user["last_name"],
        "hashed_password": temp_user["hashed_password"],
        "phone_number": temp_user["phone_number"],
        "role": "patient",
        "appointments": [],
        "is_active": True,
        "profile_image_url": "",  # <-- هنا المكان الفارغ جاهز
        "created_at": datetime.utcnow()
    }
    result = await patients_collection.insert_one(new_patient)

    # حذف السجل المؤقت
    await temp_patients_collection.delete_one({"email": email})

    return {"message": "تم التحقق والتسجيل بنجاح ✅", "patient_id": str(result.inserted_id)}
#
#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
#
async def register_patient(request: CreatePatientRequest):
    # Check if email or username already exists in the main collection
    existing_patient = await patients_collection.find_one({
        "$or": [{"username": request.username}, {"email": request.email}]
    })
    if existing_patient:
        raise HTTPException(status_code=400, detail="Username or Email already exists")

    # Delete any old temporary record
    await temp_patients_collection.delete_one({"email": request.email})

    # ⚡ Adjustment: if username is same as email, take part before '@'
    if request.username == request.email:
        username_only = request.email.split("@")[0]
        request.username = username_only

    # Hash password
    hashed_password = bcrypt_context.hash(truncate_password(request.password))

    # Store temporary patient data
    temp_patient = {
        "email": request.email,
        "username": request.username,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "hashed_password": hashed_password,
        "phone_number": request.phone_number,
        "created_at": datetime.utcnow()
    }
    await temp_patients_collection.insert_one(temp_patient)

    # Send OTP
    otp_code = await patient_controller.store_otp(request.email)
    await patient_controller.send_email(request.email, otp_code)

    return {"message": "OTP has been sent to your email. Complete registration after verifying OTP."}

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
#

async def login_patient(request_data: LoginPatientRequest, request: Request):
    """
    Login a patient using username or email and password.
    Returns an access token and patient info if successful.
    """

    # 1️⃣ Build the query based on provided input
    query = {}
    if request_data.username:
        query["username"] = request_data.username
    elif request_data.email:
        query["email"] = request_data.email
    else:
        # Case: Neither username nor email is provided
        raise HTTPException(
            status_code=400,
            detail="Please provide either username or email."
        )

    # 2️⃣ Find patient in the database
    patient =await  patients_collection.find_one(query)

    # 3️⃣ Check if patient exists and password is correct
    if not patient:
        # Case: No patient found with the given username/email
        raise HTTPException(
            status_code=401,
            detail="Username or password is incorrect."
        )

    if not bcrypt_context.verify(request_data.password, patient["hashed_password"]):
        # Case: Password is incorrect
        raise HTTPException(
            status_code=401,
            detail="Username or password is incorrect."
        )

    # 4️⃣ Check if account is active
    if not patient.get("is_active", True):
        # Case: Account exists but is inactive
        raise HTTPException(
            status_code=403,
            detail="Account is inactive. Please contact administration."
        )

    # 5️⃣ If everything is fine, create an access token
    token = create_access_token(patient["email"], str(patient["_id"]))

    # 6️⃣ Return success response
    return {
        "message": f"Welcome back, {patient['first_name']}!",
        "access_token": token,
        "token_type": "bearer",
        "patient_id": str(patient["_id"]),
        "patient_data": {
            "username": patient["username"],
            "email": patient["email"],
            "full_name": f"{patient['first_name']} {patient['last_name']}",
            "role": "patient"
        }
    }

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
async def update_patient(update_data: UpdatePatientRequest, current_user, profile_image_url: Optional[str] = None):
    updates = {k: v for k, v in update_data.dict().items() if v is not None}

    if profile_image_url:
        updates["profile_image_url"] = profile_image_url

    if not updates:
        raise HTTPException(status_code=400, detail="لا يوجد بيانات لتحديثها")

    # انتظر حتى يتم التحديث
    await mongo_db["patients"].update_one({"_id": ObjectId(current_user["_id"])}, {"$set": updates})
    
    # انتظر حتى يتم جلب المريض بعد التحديث
    updated_patient = await mongo_db["patients"].find_one({"_id": ObjectId(current_user["_id"])})
    
    updated_patient["_id"] = str(updated_patient["_id"])
    return updated_patient

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
def logout_patient(token: str):
    blacklisted_tokens.add(token)
    return {"message": "Logged out successfully"}
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#----------------------------------------
#
##
###
####
#####
######         truncate_password
#######        create_access_token
########        verify_token
#########       get_current_patient
##########      get_profile_for_current_patient
#########       get_doctor_info
########        get_all_doctors_info
#######
######
#####
####
###
##
#
#----------------------------------------
#
#
#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
#

def truncate_password(password: str) -> str:
    """
    تقص الباسورد إلى أول 72 بايت بشكل آمن لباسوردات UTF-8.
    """
    # loop عبر الأحرف وحساب الطول بالبايت
    truncated = ""
    total_bytes = 0
    for char in password:
        char_bytes = char.encode("utf-8")
        if total_bytes + len(char_bytes) > 72:
            break
        truncated += char
        total_bytes += len(char_bytes)
    return truncated

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
## ================== دوال JWT ==================
def create_access_token(email: str, patient_id: str, expires_delta: Optional[timedelta] = None):
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=2))
    payload = {"sub": email, "id": patient_id, "role": "patient", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
def verify_token(token: str):
    if token in blacklisted_tokens:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role != "patient":
            raise HTTPException(status_code=401, detail="Invalid token or role")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
async def get_current_patient(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token: no email found")
        
        patient = await patients_collection.find_one({"email": email})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # تحويل ObjectId إلى string
        patient["_id"] = str(patient["_id"])
        return patient

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------

# ================== عرض الملف الشخصي ==================
def get_profile_for_current_patient(current_patient: dict):
    return {
        "full_name": f"{current_patient.get('first_name', '')} {current_patient.get('last_name', '')}".strip(),
        "email": current_patient.get("email"),
        "phone_number": current_patient.get("phone_number"),
        "username": current_patient.get("username"),
    }
#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
# ================== جلب كل معلومات دكتور ==================
async def get_doctor_info(doctor_id: str):
    """
    ترجع كل بيانات الدكتور بناءً على الID.
    """

    doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # تحويل ObjectId إلى string
    doctor["_id"] = str(doctor["_id"])

    # إرجاع كل البيانات للمريض
    return doctor
#-----------------------------
##
###
####
#####                    
####
###
##
#-----------------------------
# ================== جلب كل الدكاترة ==================
async def get_all_doctors_info():
    """
    ترجع قائمة بكل الدكاترة.
    """
    doctors_list = []
    async for doc in doctors_collection.find():
        doc["_id"] = str(doc["_id"])
        doctors_list.append(doc)
    return doctors_list
#
#
#
#
#
#
#
#
#
#
#


async def change_password_after_otp(request: ChangePasswordRequest):
    """
    تغيير كلمة المرور بعد التحقق من OTP بدون الحاجة إلى JWT
    """
    # 1) تأكد من وجود OTP ومتأكد له
    otp_entry = await otp_collection.find_one({"email": request.email})

    if not otp_entry or not otp_entry.get("verified", False):
        raise HTTPException(
            status_code=400,
            detail="الرجاء التحقق من OTP أولاً"
        )

    # 2) تأكد من وجود المريض
    patient = await patients_collection.find_one({"email": request.email})
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير موجود")

    # 3) تجزئة الباسورد الجديد
    hashed_password = bcrypt_context.hash(request.new_password)

    # 4) تحديث كلمة مرور المريض
    await patients_collection.update_one(
        {"email": request.email},
        {"$set": {"hashed_password": hashed_password}}
    )

    # 5) حذف OTP بعد إتمام العملية
    await otp_collection.delete_one({"email": request.email})

    return {"message": "تم تغيير كلمة المرور بنجاح"}


#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# ================= SMTP =================


class PatientController:
    def __init__(self):
        self.otp_collection = otp_collection  # تم تعريفها داخل الكلاس



#
##
###
##
#
    async def startup_event(self):
        await self.otp_collection.create_index("expires", expireAfterSeconds=0)

        logging.info(" TTL index on otp_storage collection is ready.")
#
##
###
##
#
    def generate_otp(self):
        return str(random.randint(100000, 999999))
#
##
###
##
#
    async def store_otp(self, email: str):
        otp_code = self.generate_otp()
        doc = {
            "email": email, 
            "otp": otp_code,
            "expires": datetime.utcnow() + timedelta(minutes=1),
            "attempts": 0
        }
        result = await self.otp_collection.update_one({"email": email}, {"$set": doc}, upsert=True)

        logging.info(f"OTP for {email} stored in DB: {otp_code} | Upserted: {result.upserted_id}")
        return otp_code
#
##
###
##
#
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
#
##
###
##
#
    async def send_email(self, recipient, otp_code):
        message = message = MIMEText(f"""
 عيادة الأمل 
-----------------
مرحباً بك في عيادتنا

🔑 رمز التحقق: {otp_code}

شكراً لاختيارك عيادة الأمل
""", "plain", "utf-8")
        
        message["From"] = FROM_EMAIL
        message["To"] = recipient
        message["Subject"] = "رمز التحقق (OTP)"

        try:
            
            await aiosmtplib.send(
                message,
                hostname=SMTP_SERVER,
                port=SMTP_PORT,
                use_tls=True,   # بدل start_tls
                username=SMTP_LOGIN,
                password=SMTP_PASSWORD
            )

            logging.info(f"OTP sent to {recipient}")
        except Exception as e:
            logging.error(f" Error sending email to {recipient}: {e}")
            raise HTTPException(status_code=500, detail="فشل إرسال البريد الإلكتروني")
#
##
###
##
#
    def create_access_token(self, username: str, patient_id: str, expires_delta: timedelta = timedelta(hours=2)):
        expire = datetime.utcnow() + expires_delta
        payload = {"sub": username, "id": patient_id, "role": "patient", "exp": expire}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
#
##
###
##
#
    async def send_otp_endpoint(self, request: OTPRequest):
        patient = await patients_collection.find_one({"email": request.email})
        if not patient:
            raise HTTPException(status_code=404, detail="البريد غير مسجل")
        
        otp_code = await self.store_otp(request.email)
        await self.send_email(request.email, otp_code)
        return {"message": "تم إرسال رمز التحقق إلى البريد الإلكتروني"}
#
##
###
##
#
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

patient_controller = PatientController()


