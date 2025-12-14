# admin_controller.py
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException
from bson import ObjectId
from database import doctors_collection,patients_collection,admins_collection
import aiosmtplib
from email.mime.text import MIMEText


bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"




class AdminController:



    async def register(self, email: str, password: str):
        # تحقق من وجود Admin مسبقاً
        existing = await admins_collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Admin already exists")

        hashed_password = bcrypt_context.hash(password)
        new_admin = {
            "email": email,
            "hashed_password": hashed_password,
            "created_at": datetime.utcnow(),
            "role": "admin",
            "is_active": True
        }

        result = await admins_collection.insert_one(new_admin)
        return {"id": str(result.inserted_id), "email": email}
    


    def create_access_token(self, username: str, expires_delta: timedelta = timedelta(hours=4)):
        payload = {"sub": username, "exp": datetime.utcnow() + expires_delta}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    async def login(self, email: str, password: str):
        admin = await admins_collection.find_one({"email": email})
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        if not bcrypt_context.verify(password, admin["hashed_password"]):
            raise HTTPException(status_code=401, detail="Incorrect password")

        # إنشاء توكن JWT
        payload = {"sub": email, "exp": datetime.utcnow() + timedelta(hours=4)}
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}


    async def get_all_users(self):
        doctors = await doctors_collection.find().to_list(length=100)
        patients = await patients_collection.find().to_list(length=100)

        def serialize(user):
            user["_id"] = str(user["_id"])
            return user

        return {
            "doctors": [serialize(d) for d in doctors],
            "patients": [serialize(p) for p in patients]
        }

    async def update_doctor(self, doctor_id: str, is_active: bool = None, is_approved: bool = None):
        doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
    
        updates = {}
        if is_active is not None:
            updates["is_active"] = is_active
        if is_approved is not None:
            updates["is_approved"] = is_approved
    
        if updates:
            await doctors_collection.update_one({"_id": ObjectId(doctor_id)}, {"$set": updates})
    
        doctor_name = f"{doctor['first_name']} {doctor['last_name']}"
    
        # ✅ إرسال بريد عند الموافقة
        if is_approved:
            await send_doctor_approval_email(doctor['email'], doctor_name)

        # ✅ إرسال بريد عند التفعيل أو الإلغاء
        if is_active is not None:
            await send_doctor_activation_email(doctor['email'], doctor_name, is_active)
    
        updated_doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        updated_doctor["_id"] = str(updated_doctor["_id"])
        return updated_doctor

    async def update_patient(self, patient_id: str, is_active: bool = None):
        patient = await patients_collection.find_one({"_id": ObjectId(patient_id)})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        updates = {}
        if is_active is not None:
            updates["is_active"] = is_active

        if updates:
            await patients_collection.update_one({"_id": ObjectId(patient_id)}, {"$set": updates})

        patient_name = f"{patient['first_name']} {patient['last_name']}"

        # إرسال إيميل عند التفعيل أو الإلغاء
        if is_active is not None:
            await send_patient_activation_email(patient['email'], patient_name, is_active)

        updated_patient = await patients_collection.find_one({"_id": ObjectId(patient_id)})
        updated_patient["_id"] = str(updated_patient["_id"])
        return updated_patient
    


    async def delete_doctor(self, doctor_id: str):
        doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
    
        await doctors_collection.delete_one({"_id": ObjectId(doctor_id)})
        return {"message": f"Doctor {doctor['first_name']} {doctor['last_name']} deleted successfully"}






    
    async def delete_patient(self, patient_id: str):
        patient = await patients_collection.find_one({"_id": ObjectId(patient_id)})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        await patients_collection.delete_one({"_id": ObjectId(patient_id)})
        return {"message": f"Patient {patient['first_name']} {patient['last_name']} deleted successfully"}


admin_controller = AdminController()









SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 465
SMTP_LOGIN = "9b77a8001@smtp-brevo.com"
SMTP_PASSWORD = "WSn3aDfVAKMhJwrd"
FROM_EMAIL = "عياده الامل <douhasharkawi@gmail.com>"

async def send_doctor_approval_email(recipient_email: str, doctor_name: str):
    message = MIMEText(f"""
مرحباً {doctor_name},

✅ تم الموافقة على حسابك في عيادة الأمل.
يمكنك الآن تسجيل الدخول واستخدام حسابك.

شكراً لاختيارك عيادتنا
""", "plain", "utf-8")

    message["From"] = FROM_EMAIL
    message["To"] = recipient_email
    message["Subject"] = "تمت الموافقة على حسابك في عيادة الأمل"

    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        use_tls=True,
        username=SMTP_LOGIN,
        password=SMTP_PASSWORD
    )



async def send_doctor_activation_email(recipient_email: str, doctor_name: str, is_active: bool):
    status_text = "تم تفعيل حسابك بنجاح ✅" if is_active else "تم إلغاء تنشيط حسابك ❌"
    message = MIMEText(f"""
مرحباً {doctor_name},

{status_text} في عيادة الأمل.

لأي استفسار يرجى التواصل مع الدعم الفني:
batainehkamel2@gmail.com

شكراً لتعاونك معنا.
""", "plain", "utf-8")

    message["From"] = FROM_EMAIL
    message["To"] = recipient_email
    message["Subject"] = "تحديث حالة حسابك - عيادة الأمل"

    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        use_tls=True,
        username=SMTP_LOGIN,
        password=SMTP_PASSWORD
    )




async def send_patient_activation_email(recipient_email: str, patient_name: str, is_active: bool):
    status_text = "تم تفعيل حسابك بنجاح ✅" if is_active else "تم إلغاء تنشيط حسابك ❌"

    # إنشاء الرسالة
    body = f"""
مرحباً {patient_name},

{status_text} في عيادة الأمل.

لأي استفسار يرجى التواصل مع الدعم الفني:
batainehkamel2@gmail.com

شكراً لتعاونك معنا.
"""

    message = MIMEText(body, _subtype="plain", _charset="utf-8")  # مهم للعرض الكامل بالعربي
    message["From"] = FROM_EMAIL
    message["To"] = recipient_email
    message["Subject"] = "تحديث حالة حسابك - عيادة الأمل"

    # إرسال الإيميل
    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        use_tls=True,
        username=SMTP_LOGIN,
        password=SMTP_PASSWORD
    )





