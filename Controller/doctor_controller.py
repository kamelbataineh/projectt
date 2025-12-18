from email.mime.text import MIMEText
import logging
import random
import aiosmtplib
from fastapi import HTTPException, Depends, Request, UploadFile, File
from jose import jwt, JWTError
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
import os
from bson import ObjectId
from model.doctor_model import UpdateDoctorModel,LoginDoctorModel
from database import mongo_db ,temp_doctors_collection,otp_collection
from model.otp_model import OTPRequest, OTPVerifyRequest

# ============= الإعدادات العامة =============


doctors_collection = mongo_db["doctors"]
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/doctors/login")
blacklisted_tokens = set()

# 📂 مجلد حفظ ملفات السيرة الذاتية
UPLOAD_DIR = "uploads/cv_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


#
#----------------------------------------
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



# ============= إنشاء توكن JWT =============
def create_access_token(username: str, user_id: str, role: str, expires_delta: timedelta = timedelta(hours=4)):
    payload = {"sub": username, "id": user_id, "role": role, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

#
#----------------------------------------
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


async def confirm_doctor_registration(email: str, otp: str):

    # 1) التحقق من OTP
    await doctor_controller.verify_otp(email, otp)

    # 2) جلب الدكتور من temp
    temp_doctor = await temp_doctors_collection.find_one({"email": email})
    if not temp_doctor:
        raise HTTPException(status_code=404, detail="لا يوجد طلب تسجيل لهذا البريد")

    # 3) إنشاء الحساب في doctors_collection
    new_doctor = {
        "email": temp_doctor["email"],
        "username": temp_doctor["username"],
        "first_name": temp_doctor["first_name"],
        "last_name": temp_doctor["last_name"],
        "hashed_password": temp_doctor["hashed_password"],
        "phone_number": temp_doctor["phone_number"],
        "role": temp_doctor["role"],
        "cv_url": temp_doctor["cv_url"],
        "is_active": True,
        "is_approved": False,    # ✳️ ينتظر موافقة الإدارة
        "created_at": datetime.utcnow()
    }

    result = await doctors_collection.insert_one(new_doctor)

    # 4) حذف السجل المؤقت
    await temp_doctors_collection.delete_one({"email": email})

    return {"message": "تم التحقق والتسجيل بنجاح ✅ بانتظار موافقة الإدارة", "doctor_id": str(result.inserted_id)}
#
#----------------------------------------
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

async def register_doctor_temp(
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    phone_number: str,
    role: str,
    cv_file: UploadFile = File(...)
):
    # ---------------- التحقق من صيغة الملف ----------------
    if not (cv_file.content_type.startswith("image/") or cv_file.content_type in [
        "application/pdf", "application/x-pdf", "application/octet-stream"
    ]):
        raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة. استخدم PDF أو صورة.")

    # ---------------- التحقق من عدم وجود حساب ----------------
    existing_doctor = await doctors_collection.find_one({
        "$or": [{"email": email}, {"username": username}]
    })
    if existing_doctor:
        raise HTTPException(status_code=400, detail="البريد أو اسم المستخدم مستخدم بالفعل")

    # حذف أي تسجيل مؤقت قديم
    await temp_doctors_collection.delete_one({"email": email})

    # ---------------- حفظ CV ----------------
    ext = cv_file.filename.split(".")[-1]
    file_path = os.path.join(UPLOAD_DIR, f"{username}_cv.{ext}")

    with open(file_path, "wb") as f:
        f.write(await cv_file.read())

    # ---------------- تشفير كلمة المرور ----------------
    hashed_password = bcrypt_context.hash(password)

    # ---------------- تخزين الدكتور مؤقتًا ----------------
    temp_doctor = {
        "email": email,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "hashed_password": hashed_password,
        "phone_number": phone_number,
        "role": role,
        "cv_url": f"/{file_path}",
        "created_at": datetime.utcnow(),
    }

    await temp_doctors_collection.insert_one(temp_doctor)

    # ---------------- إرسال OTP ----------------
    otp_code = await doctor_controller.store_otp(email)
    await doctor_controller.send_email(email, otp_code)

    return {"message": "تم إرسال OTP إلى بريدك الإلكتروني. أكمل التسجيل بعد التحقق."}





















#
#----------------------------------------
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




# # ============= تسجيل دكتور جديد مع رفع CV =============
# def register_doctor_with_cv(
#     username: str,
#     email: str,
#     first_name: str,
#     last_name: str,
#     password: str,
#     phone_number: str,
#     role: str,
#     cv_file: UploadFile = File(...)
# ):
#     # 📌 التحقق من نوع الملف
#     allowed_types = [
#     "application/pdf",
#     "application/x-pdf",
#     "application/octet-stream",
#     "image/jpeg",
#     "image/jpg",
#     "image/png",
#     "image/gif",
#     "image/bmp",
#     "image/webp"
#     ]
# # 📌 السماح بأي صورة أو PDF
#     if not (cv_file.content_type.startswith("image/") or cv_file.content_type in ["application/pdf", "application/x-pdf", "application/octet-stream"]):
#         raise HTTPException(
#         status_code=400,
#         detail="صيغة الملف غير مدعومة. استخدم PDF أو أي صورة."
#     )


#     # 📌 التحقق من وجود الحساب مسبقًا
#     existing = doctors_collection.find_one({
#         "$or": [{"email": email}, {"username": username}]
#     })
#     if existing:
#         raise HTTPException(status_code=400, detail="اسم المستخدم أو البريد مستخدم بالفعل")

#     # 📂 حفظ الملف محليًا
#     ext = cv_file.filename.split(".")[-1]
#     file_path = os.path.join(UPLOAD_DIR, f"{username}_cv.{ext}")
#     with open(file_path, "wb") as f:
#         f.write(cv_file.file.read())

#     # 🔐 تشفير كلمة المرور
#     hashed_password = bcrypt_context.hash(password)

#     # 🧾 إنشاء سجل الدكتور
#     new_doctor = {
#         "username": username,
#         "email": email,
#         "first_name": first_name,
#         "last_name": last_name,
#         "phone_number": phone_number,
#         "role": role,
#         "hashed_password": hashed_password,
#         "cv_url": f"/{file_path}",
#         "is_approved": False,   # ✳️ ينتظر موافقة الأدمن
#         "is_active": True,
#         "created_at": datetime.utcnow()
#     }

#     doctors_collection.insert_one(new_doctor)
#     return {"message": "تم إرسال طلب التسجيل بنجاح ✅ بانتظار موافقة الإدارة", "cv_url": f"/{file_path}"}


# ============= تسجيل الدخول =============
#
#----------------------------------------
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
#
#----------------------------------------
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





async def login_doctor(request_data: LoginDoctorModel, request: Request):
    # 1️⃣ Check if doctor exists by username or email
    doctor =await  doctors_collection.find_one({
        "$or": [{"username": request_data.username}, {"email": request_data.email}]
    })

    if not doctor:
        # Doctor not found
        raise HTTPException(
            status_code=404,
            detail="Doctor not found / Username or email does not exist"
        )

    # 2️⃣ Verify password
    if not bcrypt_context.verify(request_data.password, doctor["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password / Password is invalid"
        )

    # 3️⃣ Check if account is approved
    if not doctor.get("is_approved", False):
        raise HTTPException(
            status_code=403,
            detail="Your account is not approved yet. Please wait for admin approval."
        )

    # 4️⃣ Check if account is active (optional, e.g., banned or deactivated)
    if doctor.get("is_active", True) is False:
        raise HTTPException(
            status_code=403,
            detail="Your account is deactivated or banned. Please contact support."
        )

    # 5️⃣ Generate JWT access token
    token = create_access_token(
        username=doctor["username"],
        user_id=str(doctor["_id"]),
        role=doctor["role"]
    )

    # 6️⃣ Return response
    return {
        "message": f"Welcome Doctor {doctor['first_name']} 👋",
        "access_token": token,
        "doctor_id": str(doctor["_id"]),
        "doctor_data": {
            "full_name": f"{doctor['first_name']} {doctor['last_name']}",
            "email": doctor["email"],
            "role": doctor["role"],
            "cv_url": doctor.get("cv_url")
        }
    }
#
#----------------------------------------
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

# ================== استدعاء مجموعة المرضى ==================
patients_collection = mongo_db["patients"]

# ================== جلب كل معلومات مريض ==================
async def get_patient_info(patient_id: str):
    patient = await patients_collection.find_one({"_id": ObjectId(patient_id)})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient["_id"] = str(patient["_id"])
    return patient



# ============= الحصول على بيانات المستخدم الحالي =============
async def get_current_doctor(token: str = Depends(oauth2_scheme)):
    token_value = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
    if token_value in blacklisted_tokens:
        raise HTTPException(status_code=401, detail="Token has been logged out")
    
    try:
        payload = jwt.decode(token_value, SECRET_KEY, algorithms=[ALGORITHM])
        doctor = await doctors_collection.find_one({"_id": ObjectId(payload["id"])})
        if not doctor:
            raise HTTPException(status_code=404, detail="لم يتم العثور على الدكتور")
        doctor["_id"] = str(doctor["_id"])
        return doctor
    except JWTError:
        raise HTTPException(status_code=401, detail="رمز الدخول غير صالح")

#
#----------------------------------------
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



# ============= التحقق من التوكن (تُستخدم في الشات) =============
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        doctor = doctors_collection.find_one({"_id": ObjectId(payload["id"])})
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        return {"id": str(doctor["_id"]), "role": doctor["role"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")




#
#----------------------------------------
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



        

def get_all_doctors():
    doctors = mongo_db["doctors"].find()
    result = []

    for d in doctors:
        result.append({
            "id": str(d["_id"]),
            "first_name": d.get("first_name"),
            "last_name": d.get("last_name"),
            "email": d.get("email"),
            "phone_number": d.get("phone_number"),
            "cv_url": d.get("cv_url"),
            "is_approved": d.get("is_approved", False)
        })

    return result

#
#----------------------------------------
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



def get_doctor_by_id(doctor_id: str):
    doctor = mongo_db["doctors"].find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        return None

    return {
        "id": str(doctor["_id"]),
        "first_name": doctor.get("first_name"),
        "last_name": doctor.get("last_name"),
        "email": doctor.get("email"),
        "phone_number": doctor.get("phone_number"),
        "cv_url": doctor.get("cv_url"),
        "is_approved": doctor.get("is_approved", False)
    }




#
#----------------------------------------
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



UPLOAD_PROFILE_DIR = "uploads/profile_images"
os.makedirs(UPLOAD_PROFILE_DIR, exist_ok=True)



async def update_doctor(update_data: UpdateDoctorModel, current_user, profile_image_url: Optional[str] = None):
    updates = {k: v for k, v in update_data.dict().items() if v is not None}

    if profile_image_url:
        updates["profile_image_url"] = profile_image_url

    if not updates:
        raise HTTPException(status_code=400, detail="لا يوجد بيانات لتحديثها")

    mongo_db["doctors"].update_one({"_id": ObjectId(current_user["_id"])}, {"$set": updates})
    updated_doctor = await mongo_db["doctors"].find_one({"_id": ObjectId(current_user["_id"])})
    updated_doctor["_id"] = str(updated_doctor["_id"])

    return updated_doctor















#
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################
####################################################



SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 465
SMTP_LOGIN = "9b77a8001@smtp-brevo.com"
SMTP_PASSWORD = "WSn3aDfVAKMhJwrd"
FROM_EMAIL = "عياده الامل <douhasharkawi@gmail.com>"
# ================= JWT =================
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

class DoctorController:
    def __init__(self):
        self.otp_collection = otp_collection  # تم تعريفها داخل الكلاس
        self.blacklisted_tokens = set()

    async def logout_doctor(self, token: str):
        self.blacklisted_tokens.add(token)
        return {"detail": "Logged out successfully"}

    async def startup_event(self):
        await self.otp_collection.create_index("expires", expireAfterSeconds=0)

        logging.info(" TTL index on otp_storage collection is ready.")

    def generate_otp(self):
        return str(random.randint(100000, 999999))

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

    async def verify_otp(self, email: str, otp: str):
        entry = await self.otp_collection.find_one({"email": email})
        if not entry:
            raise HTTPException(status_code=400, detail="لم يتم العثور على كود OTP")
        
        if datetime.utcnow() > entry["expires"]:
            logging.warning(f"OTP for {email} expired at {entry['expires']}")
            await self.otp_collection.delete_one({"email": email})
            raise HTTPException(status_code=400, detail="انتهت صلاحية OTP")
        
        if entry["attempts"] >= 5:
            raise HTTPException(status_code=400, detail="تم تجاوز عدد المحاولات المسموح بها")
        
        if entry["otp"] != otp:
            await self.otp_collection.update_one({"email": email}, {"$inc": {"attempts": 1}})
            raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")
        
        await self.otp_collection.update_one({"email": email}, {"$set": {"verified": True}})
        logging.info(f"OTP for {email} verified successfully (kept in DB)")
        return True

    async def send_email(self, recipient, otp_code):
        message  = MIMEText(f"""
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

    def create_access_token(self, username: str, patient_id: str, expires_delta: timedelta = timedelta(hours=2)):
        expire = datetime.utcnow() + expires_delta
        payload = {"sub": username, "id": patient_id, "role": "patient", "exp": expire}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    async def send_otp_endpoint(self, request: OTPRequest):
        doctor = await doctors_collection.find_one({"email": request.email})
        temp_doctor = await temp_doctors_collection.find_one({"email": request.email})
    
        if not doctor and not temp_doctor:
            raise HTTPException(status_code=404, detail="البريد غير مسجل")
    
        otp_code = await self.store_otp(request.email)
        await self.send_email(request.email, otp_code)
        return {"message": "تم إرسال رمز التحقق إلى البريد الإلكتروني"}

    
    async def verify_login_otp(self, request: OTPVerifyRequest):
        doctor = await doctors_collection.find_one({"email": request.email})
        if not doctor:
            raise HTTPException(status_code=404, detail="البريد غير مسجل")
        
        await self.verify_otp(request.email, request.otp)
        token = self.create_access_token(doctor["username"], str(doctor["_id"]))
        return {
            "message": f"مرحباً {doctor['first_name']}!",
            "access_token": token,
            "token_type": "bearer",
            "patient_id": str(doctor["_id"])
        }




    async def change_password_after_otp(self, email: str, new_password: str):
        # تحقق من وجود OTP مصدق
        otp_entry = await otp_collection.find_one({"email": email, "verified": True})
        if not otp_entry:
            raise HTTPException(status_code=400, detail="OTP not verified or expired")

        # تشفير الباسورد الجديد
        hashed_password = bcrypt_context.hash(new_password)

        # تحديث الباسورد في قاعدة البيانات
        result = await doctors_collection.update_one(
            {"email": email},
            {"$set": {"hashed_password": hashed_password}}
        )

        if result.modified_count == 0:
            return False

        # حذف OTP بعد نجاح التغيير
        await otp_collection.delete_one({"email": email})

        return True
doctor_controller = DoctorController()
