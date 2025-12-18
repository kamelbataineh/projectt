# appointment_router.py
from database import appointments_collection 

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime
from Controller.appointment_controller import (
    approve_cancellation,
    book_appointment,
    cancel_appointment,
    complete_appointment,
    get_patient_appointments,
    get_doctor_appointments,
    approve_appointment,
    get_available_slots,
    get_token,
    send_reminders_for_tomorrow
)
from Controller.doctor_controller import get_all_doctors

router = APIRouter(prefix="/appointments", tags=["Appointments"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/patients/login")
from pydantic import BaseModel

class BookAppointmentRequest(BaseModel):
    doctor_id: str
    date_time: datetime
    reason: str = ""
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
@router.post("/book")
async def create_appointment(data: BookAppointmentRequest, token: str = Depends(oauth2_scheme)):
    return await book_appointment(token, data.doctor_id, data.date_time, data.reason)

#
#----------------------------------------
#
#
#
#
#  قائمة الأطباء
#
#
#
#
#
#----------------------------------------
#
@router.get("/doctors")
async def list_doctors(token: str = Depends(oauth2_scheme)):
    return  await get_all_doctors()

#
#----------------------------------------
#
#
#
#
#  إلغاء الموعد
#
#
#
#
#
#----------------------------------------
#

@router.post("/cancel/{appointment_id}")
async def cancel(appointment_id: str, token: str = Depends(oauth2_scheme)):
    return await cancel_appointment(token, appointment_id)

#
#----------------------------------------
#
#
#
#
#   مواعيد المريض  
#
#
#
#
#
#----------------------------------------
#
@router.get("/my-appointments")
async def my_appointments(token: str = Depends(oauth2_scheme)):
    return await get_patient_appointments(token)

#
#----------------------------------------
#
#
#
#
#  مواعيد الطبيب
#
#
#
#
#
#----------------------------------------
#
@router.get("/doctor-appointments")
async def doctor_appointments(token: str = Depends(oauth2_scheme)):
    return await get_doctor_appointments(token)

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
@router.post("/approve/{appointment_id}")
async def approve_route(
    appointment_id: str,
    approve: bool | None = Query(None),
    revert: bool = Query(False),
    token: str = Depends(oauth2_scheme)
):
    # إذا لا يوجد approve و revert=False، نرفع 400
    if approve is None and not revert:
        raise HTTPException(status_code=400, detail="Must provide approve or revert")
    
    # approve_appointment يجب أن تتعامل مع approve=None و revert=True
    return await approve_appointment(
        token=token,
        appointment_id=appointment_id,
        approve=approve,
        revert=revert
    )


#----------------------------------------
#
#
#
#
#  عرض الأوقات المتاحة للطبيب
#
#
#
#
#
#----------------------------------------
#
@router.get("/available-slots/{doctor_id}")
async def available_slots(doctor_id: str, date: str, token: str = Depends(oauth2_scheme)):
    # التحقق من صيغة التاريخ
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    return await  get_available_slots(doctor_id, date)

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
@router.post("/complete/{appointment_id}")
async def complete(appointment_id: str, token: str = Depends(oauth2_scheme)):
    return await  complete_appointment(token, appointment_id)




@router.post("/cancel/approve/{appointment_id}")
async def approve_cancel(appointment_id: str, token: str = Depends(get_token)):
    # تحقق من الصلاحيات إذا لازم
    return await approve_cancellation(appointment_id)



@router.delete("/delete/{appointment_id}")
async def delete_appointment(appointment_id: str):
    try:
        obj_id = ObjectId(appointment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="معرف الموعد غير صالح")

    result = await appointments_collection.delete_one({"_id": obj_id})

    if result.deleted_count == 1:
        return {"message": "تم حذف الموعد بنجاح"}
    else:
        raise HTTPException(status_code=404, detail="الموعد غير موجود")


@router.get("/send-reminders")
async def run_reminders():
    await send_reminders_for_tomorrow()
    return {"message": "Reminders sent"}
