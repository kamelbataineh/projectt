# appointment_controller.py
from email import parser
from fastapi import HTTPException, Header
from datetime import datetime, time, timedelta
from typing import List
from pydantic import BaseModel
from bson import ObjectId
from database import appointments_collection ,patients_collection,doctors_collection ,messages_collection
import aiosmtplib
from email.mime.text import MIMEText
import asyncio

from jose import jwt
from datetime import datetime
# -------------------- إعداد SMTP للإشعارات --------------------
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 465
SMTP_LOGIN = "9b77a8001@smtp-brevo.com"
SMTP_PASSWORD = "WSn3aDfVAKMhJwrd"
FROM_EMAIL = "عياده الامل  <douhasharkawi@gmail.com>"

# -------------------- نموذج المواعيد --------------------
class AppointmentResponse(BaseModel):
    appointment_id: str
    doctor_name: str = None
    patient_name: str = None
    date_time: str
    status: str
    reason: str = None
#
#----------------------------------------
#
#
#
#
# -------------------- دوال مساعدة --------------------
#
#
#
#
#
#----------------------------------------
#
def convert_objectid(doc):
    if not doc:
        return None
    doc = dict(doc)
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
    return doc

#
#----------------------------------------
#
#
#----------------------------------------
#


def get_user_from_token(token: str, role_required: str = None):
    SECRET_KEY = "mysecretkey"
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    if role_required and payload.get("role") != role_required:
        raise HTTPException(status_code=403, detail=f"Access denied for role: {payload.get('role')}")
    return payload

#
#----------------------------------------
#
#
#
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
#____
# -------------------- إرسال الإيميل --------------------
#
#
#
#
#
#----------------------------------------
#
# إرسال إيميل عند الموافقة
async def notify_approval_email(patient_email: str, doctor_name: str, date_time: str):
    subject = f"تمت الموافقة على موعدك مع الدكتور {doctor_name}"
    content = (
        f"مرحباً،\n\n"
        f"تمت الموافقة على موعدك بنجاح.\n"
        f"تاريخ ووقت الموعد: {date_time}\n\n"
        f"مع التحية."
    )
    asyncio.create_task(send_email_async(patient_email, subject, content))

# إرسال إيميل عند الرفض
async def notify_reject_email(patient_email: str, doctor_name: str, date_time: str):
    subject = f"تم رفض موعدك مع الدكتور {doctor_name}"
    content = (
        f"مرحباً،\n\n"
        f"تم رفض موعدك.\n"
        f"تاريخ ووقت الموعد: {date_time}\n\n"
        f"مع التحية."
    )
    asyncio.create_task(send_email_async(patient_email, subject, content))

# -------------------- إرسال إيميل عند الحجز --------------------
async def notify_booking_email(patient_email: str, doctor_name: str, date_time: str):
    subject = f"تم استلام طلب حجز موعد مع الدكتور {doctor_name}"
    content = (
        f"مرحباً،\n\n"
        f"لقد تم استلام طلب حجز موعدك وهو الآن بانتظار موافقة الطبيب.\n"
        f"موعدك المقترح: {date_time}\n\n"
        f"سوف يصلك إشعار عند الموافقة أو الرفض.\n\n"
        f"مع التحية."
    )
    asyncio.create_task(send_email_async(patient_email, subject, content))


# -------------------- إشعار عند إرجاع الموعد Pending --------------------
async def notify_revert_email(patient_email: str, doctor_name: str, date_time: str):
    subject = f"تم تعديل حالة موعدك مع الدكتور {doctor_name}"
    content = (
        f"مرحباً،\n\n"
        f"قام الطبيب بإعادة ضبط حالة الموعد إلى (بانتظار الموافقة).\n"
        f"تاريخ الموعد: {date_time}\n\n"
        f"سيتم إعلامك عند الموافقة أو الرفض.\n"
    )
    asyncio.create_task(send_email_async(patient_email, subject, content))


# -------------------- تذكير قبل الموعد بيوم --------------------
async def send_appointment_reminder(patient_email: str, doctor_name: str, date_time: str):
    subject = f"تذكير بموعدك غداً مع الدكتور {doctor_name}"
    content = (
        f"مرحباً،\n\n"
        f"هذا تذكير لك بأن لديك موعد غداً:\n"
        f"⏰ الوقت: {date_time}\n"
        f"👨‍⚕️ مع الدكتور: {doctor_name}\n\n"
        f"نتمنى لك السلامة."
    )
    asyncio.create_task(send_email_async(patient_email, subject, content))


async def send_reminders_for_tomorrow():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0)
    end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59)
   
    appointments = await appointments_collection.find({
    "status": "Confirmed",
    "date_time": {"$gte": start, "$lte": end}
        }).to_list(length=None)


    for app in appointments:
        patient = await patients_collection.find_one({"_id": ObjectId(app["patient_id"])})
        doctor = await doctors_collection.find_one({"_id": ObjectId(app["doctor_id"])})

        if not patient or not doctor:
            continue

        date_time = datetime.fromisoformat(app["date_time"])
        await send_appointment_reminder(
            patient_email=patient["email"],
            doctor_name=f"{doctor.get('first_name','')} {doctor.get('last_name','')}",
            date_time=date_time.strftime("%Y-%m-%d %H:%M")
        )


async def send_email_async(recipient: str, subject: str, content: str):
    message = MIMEText(content, "plain", "utf-8")
    message["From"] = FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    try:
        await aiosmtplib.send(
            message,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            use_tls=True,  
            username=SMTP_LOGIN,
            password=SMTP_PASSWORD,
        )
        print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"Error sending email to {recipient}: {e}")

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
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#=======
#
#
# -------------------- حجز موعد --------------------
#
#
#
#
#
#----------------------------------------
#
async def book_appointment(token: str, doctor_id: str, date_time: datetime, reason: str = None):
    payload = get_user_from_token(token, role_required="patient")
    patient_id = payload.get("id")
    patient =await patients_collection.find_one({"_id": ObjectId(patient_id)})
    doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
    # إرسال إيميل للمريض عند الحجز
    await notify_booking_email(
        patient_email=patient["email"],
        doctor_name=f"{doctor.get('first_name', '')} {doctor.get('last_name', '')}",
        date_time=date_time.strftime("%Y-%m-%d %H:%M")
    )

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    now = datetime.now()
    if date_time <= now:
        raise HTTPException(status_code=400, detail="Cannot book an appointment in the past")
    if date_time.time() < time(10, 0) or date_time.time() > time(16, 0):
        raise HTTPException(status_code=400, detail="Appointment must be within working hours (10:00 - 16:00)")
    if date_time.weekday() > 4:
        raise HTTPException(status_code=400, detail="Appointments allowed only Sunday-Thursday")
    if date_time.minute not in (0, 30):
        raise HTTPException(status_code=400, detail="Appointments must start at 00 or 30 minutes")

    # ❌ تحقق إذا المريض لديه موعد بالفعل في نفس الوقت
    existing = await appointments_collection.find_one({
    "patient_id": patient_id,
    "status": {"$ne": "Cancelled"},
    "date_time": date_time
})

    if existing:
        raise HTTPException(status_code=400, detail="You already have an appointment at this time")

    # ❌ تحقق إذا الطبيب لديه موعد في نفس الوقت
    conflict = await appointments_collection.find_one({
    "doctor_id": doctor_id,
    "status": {"$ne": "Cancelled"},
    "date_time": date_time
})

    if conflict:
        raise HTTPException(status_code=400, detail="Doctor has another appointment at this time")

    # إعداد المستند
    new_app = {
    "patient_id": str(patient["_id"]),
    "doctor_id": str(doctor["_id"]),
    "date_time": date_time,   # ✅ datetime حقيقي
    "reason": reason,
    "status": "Pending"
}

    result =await appointments_collection.insert_one(new_app)
    
    # تحويل كل ObjectId إلى string قبل الإرجاع
    response = {
        "appointment_id": str(result.inserted_id),
        "patient_id": new_app["patient_id"],
        "doctor_id": new_app["doctor_id"],
        "date_time": new_app["date_time"],
        "reason": new_app["reason"],
        "status": new_app["status"]
    }
    return response

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
async def approve_appointment(token: str, appointment_id: str, approve: bool, revert: bool = False):
    # التحقق من هوية الدكتور
    payload = get_user_from_token(token, role_required="doctor")
    doctor_id = payload.get("id")

    # جلب الموعد
    appointment = await appointments_collection.find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment["doctor_id"] != doctor_id:
        raise HTTPException(status_code=403, detail="Not allowed to modify this appointment")

    current_status = appointment["status"]

    # -------------------------------------------
    # 🔄 إرجاع الموعد إلى Pending
    # -------------------------------------------
    if revert:
        if current_status in ["Rejected", "Confirmed"]:

            await appointments_collection.update_one(
                {"_id": ObjectId(appointment_id)},
                {"$set": {"status": "Pending"}}
            )

            # إرسال الإيميل
            patient = await patients_collection.find_one({"_id": ObjectId(appointment["patient_id"])})
            doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
            raw_date = appointment["date_time"]
            clean_date = raw_date.replace("Z", "")
            date_time = datetime.fromisoformat(clean_date)

            if patient and doctor:
                await notify_revert_email(
                    patient_email=patient["email"],
                    doctor_name=f"{doctor.get('first_name','')} {doctor.get('last_name','')}",
                    date_time=date_time.strftime("%Y-%m-%d %H:%M")
                )

            return {
                "message": "Appointment returned to pending state",
                "appointment_id": appointment_id,
                "new_status": "Pending",
                "display_status": "بانتظار الموافقة"
            }
        else:
            raise HTTPException(status_code=400, detail="Only confirmed or rejected appointments can be reverted")


    # -------------------------------------------
    # ✔️ الموافقة أو الرفض
    # -------------------------------------------
    if current_status != "Pending":
        raise HTTPException(status_code=400, detail="Appointment already processed")

    new_status = "Confirmed" if approve else "Rejected"

    await appointments_collection.update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"status": new_status}}
    )

    # تجهيز معلومات الإيميل
    patient = await patients_collection.find_one({"_id": ObjectId(appointment["patient_id"])})
    doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})

    raw_date = appointment["date_time"]
    clean_date = raw_date.replace("Z", "")
    date_time = datetime.fromisoformat(clean_date)

    # -------------------------------------------
    # 📧 إرسال الإيميل الصحيح:
    # ✔️ notify_approval_email عند الموافقة
    # ✔️ notify_reject_email عند الرفض
    # -------------------------------------------
    if patient and doctor:
        if approve:
            await notify_approval_email(
                patient_email=patient["email"],
                doctor_name=f"{doctor.get('first_name','')} {doctor.get('last_name','')}",
                date_time=date_time.strftime("%Y-%m-%d %H:%M")
            )
        else:
            await notify_reject_email(
                patient_email=patient["email"],
                doctor_name=f"{doctor.get('first_name','')} {doctor.get('last_name','')}",
                date_time=date_time.strftime("%Y-%m-%d %H:%M")
            )

    status_display = "تمت الموافقة" if approve else "تم الرفض"

    return {
        "message": "Appointment updated successfully",
        "appointment_id": appointment_id,
        "new_status": new_status,
        "display_status": status_display
    }

#  #
# async def approve_appointment(token: str, appointment_id: str, approve: bool):
#     # التحقق من هوية الدكتور
#     payload = get_user_from_token(token, role_required="doctor")
#     doctor_id = payload.get("id")

#     # جلب الموعد
#     appointment = await appointments_collection.find_one({"_id": ObjectId(appointment_id)})
#     if not appointment:
#         raise HTTPException(status_code=404, detail="Appointment not found")

#     if appointment["doctor_id"] != doctor_id:
#         raise HTTPException(status_code=403, detail="Not allowed to approve this appointment")

#     if appointment["status"] != "Pending":
#         raise HTTPException(status_code=400, detail="Appointment already processed")

#     # تحديد الحالة الجديدة
#     new_status = "Confirmed" if approve else "Rejected"

#     # تحديث الموعد في MongoDB
#     await appointments_collection.update_one(
#         {"_id": ObjectId(appointment_id)},
#         {"$set": {"status": new_status}}
#     )

#     # ------------------------
#     #  تجهيز بيانات الإيميل
#     # ------------------------
#     patient = await patients_collection.find_one({"_id": ObjectId(appointment["patient_id"])})
#     doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})

#     # معالجة التاريخ String → datetime
#     raw_date = appointment["date_time"]

#     # إزالة Z إذا موجودة (بعض الأنظمة ترجع ISO مثل: "2025-11-18T13:30:00Z")
#     clean_date = raw_date.replace("Z", "")

#     # التحويل الصحيح
#     date_time = datetime.fromisoformat(clean_date)

#     # إرسال الإيميل إذا كانت البيانات كاملة
#     if patient and doctor:
#         await  notify_patient_email(
#                 patient_email=patient["email"],
#                 doctor_name=f"{doctor.get('first_name', '')} {doctor.get('last_name', '')}",
#                 date_time=date_time.strftime("%Y-%m-%d %H:%M"),
#                 approved=approve
# )


#     # نص الحالة
#     status_display = {
#         "Confirmed": "تمت الموافقة",
#         "Rejected": "تم الرفض",
#         "Completed": "تم الإنجاز",
#         "Cancelled": "تم الإلغاء"
#     }.get(new_status, new_status)

#     return {
#         "message": "Appointment updated successfully",
#         "appointment_id": appointment_id,
#         "new_status": new_status,
#         "display_status": status_display
#     }
# #
#----------------------------------------
#
#
#
#
# -------------------- مواعيد المريض --------------------
#
#
#
#
#
#----------------------------------------
#
async def get_patient_appointments(token: str) -> List[AppointmentResponse]:
    payload = get_user_from_token(token, role_required="patient")
    patient_id = payload.get("id")

    appointments = await appointments_collection.find({"patient_id": patient_id}).to_list(length=None)
    result = []
    for app in appointments:
        doctor = await doctors_collection.find_one({"_id": ObjectId(app["doctor_id"])})
        
        # تحويل تاريخ ISO string إلى datetime
        date_obj = app["date_time"] if isinstance(app["date_time"], str) else app["date_time"]

        status_text = {
            "Pending": "Waiting for doctor's approval",
            "Confirmed": "Appointment confirmed",
            "Rejected": "Appointment rejected",
            "Cancelled": "Appointment cancelled"
        }.get(app["status"], app["status"])
        
        result.append(AppointmentResponse(
            appointment_id=str(app["_id"]),
            doctor_name=f"{doctor.get('first_name','')} {doctor.get('last_name','')}" if doctor else "Unknown",
            date_time=date_obj.strftime("%Y-%m-%d %H:%M"),
            status=status_text,
            reason=app.get("reason")
        ))
    return result


#
#----------------------------------------
#
#
#
#
# -------------------- مواعيد الطبيب --------------------
#
#
#
#
#
#----------------------------------------
async def get_doctor_appointments(token: str) -> List[AppointmentResponse]:
    payload = get_user_from_token(token, role_required="doctor")
    doctor_id = payload.get("id")
    appointments = await appointments_collection.find({"doctor_id": doctor_id}).to_list(length=None)  
    result = []

    for app in appointments:
        patient =await patients_collection.find_one({"_id": ObjectId(app["patient_id"])})

        # التأكد من نوع التاريخ
        date_time_obj = app["date_time"]
        if isinstance(date_time_obj, str):
            date_time_obj = datetime.fromisoformat(date_time_obj)  # تحويل من ISO string إلى datetime

        result.append(AppointmentResponse(
            appointment_id=str(app["_id"]),
            patient_name=f"{patient.get('first_name','')} {patient.get('last_name','')}" if patient else "Unknown",
            date_time=date_time_obj.strftime("%Y-%m-%d %H:%M") if date_time_obj else "-",
            status=app.get("status", ""),
            reason=app.get("reason")
        ))
    return result

#
#----------------------------------------
#
#
#
#
# -------------------- الأوقات المتاحة للطبيب --------------------
#
#
#
#
#
#----------------------------------------
#
async def get_available_slots(doctor_id: str, date: str):
    doctor = await doctors_collection.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    start_time = time(10, 0)
    end_time = time(16, 0)
    slot_duration = timedelta(minutes=30)

    current = datetime.strptime(date, "%Y-%m-%d").replace(hour=start_time.hour, minute=start_time.minute)
    end_datetime = datetime.strptime(date, "%Y-%m-%d").replace(hour=end_time.hour, minute=end_time.minute)

    existing_appointments = await appointments_collection.find({
    "doctor_id": doctor_id,
    "status": {"$ne": "Cancelled"},
    "date_time": {"$gte": current, "$lt": end_datetime + slot_duration}
        }).to_list(length=None)

    booked_times = [app["date_time"] for app in existing_appointments]

    available_slots = []
    while current <= end_datetime:
        if all(current != bt for bt in booked_times):
            available_slots.append(current.strftime("%H:%M"))
        current += slot_duration
    return available_slots

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
async def cancel_appointment(token: str, appointment_id: str):
    payload = get_user_from_token(token, role_required="patient")
    patient_id = payload.get("id")

    appointment = await appointments_collection.find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment["patient_id"] != patient_id:
        raise HTTPException(status_code=403, detail="You cannot cancel this appointment")

    status = appointment["status"]

    if status not in ["Pending", "Confirmed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel this appointment")

    # نضع الحالة PendingCancellation إذا طلب المريض الإلغاء
    await appointments_collection.update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"status": "PendingCancellation"}}
    )

    return {"message": "Cancellation request sent, waiting for doctor's approval."}

# دالة للدكتور للموافقة على الإلغاء
async def approve_cancellation(appointment_id: str):
    appointment = await appointments_collection.find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment["status"] != "PendingCancellation":
        raise HTTPException(status_code=400, detail="No pending cancellation to approve")

    await appointments_collection.update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"status": "Cancelled"}}
    )

    return {"message": "Appointment cancelled successfully"}
#
#
#
#
#----------------------------------------
#
async def update_expired_appointments():
    now = datetime.now()
    expired = await appointments_collection.find({"status": {"$in": ["Confirmed", "Pending"]}}).to_list(length=None)
    for app in expired:
        app_time = app["date_time"]
        if isinstance(app_time, str):
            app_time = datetime.fromisoformat(app_time)
        if app_time < now:
            await  appointments_collection.update_one(
                {"_id": app["_id"]},
                {"$set": {"status": "Cancelled"}}
            )


#
#----------------------------------------
#
#
#
#
# -------------------- تعليم الموعد كمكتمل --------------------
#
#
#
#
#
#----------------------------------------
#
async def complete_appointment(token: str, appointment_id: str):
    payload = get_user_from_token(token, role_required="doctor")
    doctor_id = payload.get("id")

    appointment =await appointments_collection.find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment["doctor_id"] != doctor_id:
        raise HTTPException(status_code=403, detail="Not allowed to complete this appointment")

    if appointment["status"] != "Confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed appointments can be completed")

    await appointments_collection.update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"status": "Completed", "completed_at": datetime.now()}}
    )

    return {"message": "Appointment marked as completed", "appointment_id": appointment_id, "new_status": "Completed"}


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

async def get_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    return authorization[7:]





async def send_daily_doctor_notifications():
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59)

    doctors = await doctors_collection.find({}).to_list(length=None)
    for doctor in doctors:
        doctor_id = str(doctor["_id"])
        doctor_email = doctor.get("email")
        if not doctor_email:
            continue
    
        # المواعيد اليوم
        appointments = await appointments_collection.find({
            "doctor_id": doctor_id,
            "status": {"$in": ["Pending", "Confirmed"]},
            "date_time": {"$gte": today_start, "$lte": today_end}
        }).to_list(length=None)
    
        # الرسائل الجديدة
        new_messages = await messages_collection.find({
            "receiver_id": doctor_id,
            "seen": False
        }).to_list(length=None)
    
        content = f"مرحباً دكتور {doctor.get('first_name','')} {doctor.get('last_name','')},\n\n"
        content += f"لديك {len(appointments)} مواعيد اليوم.\n"
        content += f"لديك {len(new_messages)} رسائل جديدة لم تُقرأ.\n\n"
        content += "يرجى التحقق منها في لوحة التحكم.\nمع التحية."
    
        # 👈 هنا استبدل create_task بـ await
        await send_email_async(
            recipient=doctor_email,
            subject="تنبيه يومي: تحقق من مواعيدك ورسائلك",
            content=content
        )
    