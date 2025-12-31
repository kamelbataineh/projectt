# record_router.py
from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import Optional
from Controller.record_controller import MedicalRecordController
from model.record_model import (
    CreateMedicalRecordRequest,
    UpdateMedicalRecordRequest
)

router = APIRouter(prefix="/api/v1", tags=["Medical Records"])

controller = MedicalRecordController()

# ================== دالة استخراج المستخدم الحالي ==================
def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    token = authorization.split(" ")[1]
    return controller.verify_token(token)

# ================== إنشاء سجل طبي ==================
@router.post("/medical_records", status_code=status.HTTP_201_CREATED)
async def create_medical_record(
    request: CreateMedicalRecordRequest,
    current_user: dict = Depends(get_current_user)
):
    return await controller.create_medical_record(request, current_user)

# ================== الحصول على سجل طبي ==================
@router.get("/medical_records/{record_id}")
async def get_medical_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_medical_record(record_id, current_user)

# ================== تعديل سجل طبي ==================
@router.put("/medical_records/{record_id}")
async def update_medical_record(
    record_id: str,
    request: UpdateMedicalRecordRequest,
    current_user: dict = Depends(get_current_user)
):
    return await controller.update_medical_record(record_id, request, current_user)

# ================== سجلات المريض (يشوف فقط سجلاته مع Pagination) ==================
@router.get("/my_medical_records")
async def get_my_medical_records(
    page: int = 1, 
    limit: int = 10, 
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_my_medical_records(page, limit, current_user)

# ================== كل السجلات للدكاترة مع Pagination ==================
@router.get("/medical_records/doctor/all")
async def get_doctor_records(
    page: int = 1, 
    limit: int = 10, 
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_doctor_records(page, limit, current_user)

# ================== سجلات المريض المحدد للطبيب ==================
@router.get("/doctor/patients/{patient_id}/medical_records")
async def get_patient_records_for_doctor(
    patient_id: str,
    page: int = 1,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_patient_records_for_doctor(patient_id, page, limit, current_user)

# ================== سجلات الطبيب (الخاصة به فقط) ==================
@router.get("/doctor/my_created_records")
async def get_doctor_created_records(
    page: int = 1,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_doctor_created_records(page, limit, current_user)

# ================== البحث في السجلات ==================
@router.get("/medical_records/search")
async def search_medical_records(
    patient_name: Optional[str] = None,
    doctor_name: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    return await controller.search_medical_records(patient_name, doctor_name, page, limit, current_user)






@router.get("/patients/{patient_id}")
async def get_patient_by_id(
    patient_id: str,
    current_user: dict = Depends(get_current_user)
):
    return await controller.get_patient_by_id(patient_id, current_user)




# ================== حذف سجل طبي ==================
@router.delete("/medical_records/{record_id}")
async def delete_medical_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    return await controller.delete_medical_record(record_id, current_user)
