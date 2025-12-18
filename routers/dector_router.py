from fastapi import APIRouter, Depends, Form, Header, UploadFile, File
from fastapi import HTTPException, Request
from typing import Optional

from pydantic import BaseModel, EmailStr
from model.doctor_model import UpdateDoctorModel, LoginDoctorModel
from model.otp_model import OTPRequest, OTPVerifyRequest
from Controller.doctor_controller import doctor_controller, get_all_doctors, get_current_doctor, get_doctor_by_id, get_patient_info, register_doctor_temp, login_doctor, confirm_doctor_registration, update_doctor

router = APIRouter(
    prefix="/doctors",
    tags=["Doctors"]
)
class ChangePasswordAfterOTPRequest(BaseModel):
    email: EmailStr
    new_password: str
# ---------------- تسجيل دكتور مؤقت + رفع CV ----------------
@router.post("/register-temp")
async def register_temp(
    username: str = Form(...),
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    password: str = Form(...),
    phone_number: str = Form(...),
    role: str = Form(...),
    cv_file: UploadFile = File(...)
):
    return await register_doctor_temp(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        phone_number=phone_number,
        role=role,
        cv_file=cv_file
    )

# ---------------- تأكيد التسجيل عبر OTP ----------------
@router.post("/confirm-registration")
async def confirm_registration(email: str, otp: str):
    return await confirm_doctor_registration(email, otp)

# ---------------- تسجيل دخول الدكتور ----------------
@router.post("/login")
async def login(request_data: LoginDoctorModel, request: Request):
    return await login_doctor(request_data, request)

# ---------------- إرسال OTP لتسجيل الدخول ----------------
@router.post("/send-otp")
async def send_otp(request: OTPRequest):
    return await doctor_controller.send_otp_endpoint(request)

# ---------------- التحقق من OTP عند تسجيل الدخول ----------------
@router.post("/verify-login-otp")
async def verify_login_otp(request: OTPVerifyRequest):
    return await doctor_controller.verify_login_otp(request)

# ---------------- الحصول على بيانات الدكتور الحالي ----------------
@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_doctor)):
    return current_user

# ---------------- تحديث بيانات الدكتور ----------------

@router.put("/update")
async def update_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    specialization: Optional[str] = Form(None),
    years_of_experience: Optional[int] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_doctor)
):
    from Controller.doctor_controller import update_doctor
    import os

    update_data = UpdateDoctorModel(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        email=email,
        bio=bio,
        location=location,
        gender=gender,
        specialization=specialization,
        years_of_experience=years_of_experience
    )

    # حفظ الصورة على السيرفر إذا تم رفعها
    if profile_image:
        ext = profile_image.filename.split(".")[-1]
        file_path = f"uploads/profile_images/{current_user['_id']}_profile.{ext}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await profile_image.read())
        update_data.profile_image_url = file_path  # حفظ مسار الصورة

    # تحديث بيانات الدكتور
    doctor = await update_doctor(update_data, current_user)
    
    return {
        "status": "success",
        "message": "Profile updated successfully",
        "data": doctor
    }


# ---------------- الحصول على كل الدكاترة ----------------
@router.get("/all")
async def all_doctors():
    return get_all_doctors()

# ---------------- الحصول على دكتور حسب ID ----------------
@router.get("/{doctor_id}")
async def get_doctor(doctor_id: str):
    doctor = get_doctor_by_id(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor





@router.get("/patients/{patient_id}")
async def patient_details(patient_id: str, current_doctor: dict = Depends(get_current_doctor)):
    """
    يعرض كل بيانات المريض للدكتور الحالي
    """
    return await get_patient_info(patient_id)



@router.put("/change-password-after-otp")
async def change_password_after_otp(request: ChangePasswordAfterOTPRequest):
    """
    يغير الباسورد بعد التحقق من OTP
    """
    success = await doctor_controller.change_password_after_otp(
        email=request.email,
        new_password=request.new_password
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to update password")
    
    return {"detail": "Password updated successfully"}






@router.post("/logout")
async def logout(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    return await doctor_controller.logout_doctor(token)