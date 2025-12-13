from typing import Optional
from Controller import patient_controller
from fastapi import APIRouter, Depends, Header, Request ,Form,UploadFile, File
from Controller.patient_controller import (
    CreatePatientRequest,
    LoginPatientRequest,
    ChangePasswordRequest,
    UpdatePatientRequest,
    get_all_doctors_info,
    get_doctor_info,
    login_patient,
    logout_patient,
    update_patient,
    get_current_patient,
    confirm_registration
,register_patient,
change_password_after_otp
)
from model.otp_model import OTPRequest, OTPVerifyRequest
from Controller.patient_controller import patient_controller

router = APIRouter(prefix="/patients", tags=["Patients Auth"])

# تسجيل مريض جديد
# تسجيل مريض جديد (يحفظ البيانات مؤقتًا ويرسل OTP)
@router.post("/register")
async def register(request: CreatePatientRequest):
    return await register_patient(request)



# تأكيد OTP والتسجيل النهائي
@router.post("/confirm_registration")
async def confirm_registration_endpoint(email: str, otp: str):
    """
    يتحقق من OTP للمريض المسجل مؤقتًا، وإذا صحيح يتم إنشاء الحساب النهائي.
    """
    return await confirm_registration(email, otp)




# تسجيل دخول المريض
@router.post("/login")
async def login(request: LoginPatientRequest, req: Request):
    return await login_patient(request, req)


# تسجيل خروج المريض
@router.post("/logout")
def logout(Authorization: str = Header(...)):
    token = Authorization.split(" ")[1]
    return   logout_patient(token)


# تغيير كلمة مرور المريض
# ================== تغيير كلمة المرور بعد OTP ==================

@router.put("/change-password-after-otp")
async def change_password_after_otp_endpoint(request_data: ChangePasswordRequest):
    return await change_password_after_otp(request_data)

# بيانات المريض الحالي
@router.get("/me")
def get_current_patient_info(current_patient: dict = Depends(get_current_patient)):
    return  {
        "id": str(current_patient["_id"]),
        "username": current_patient["username"],
        "email": current_patient["email"],
        "first_name": current_patient["first_name"],
        "last_name": current_patient["last_name"],
        "phone_number": current_patient.get("phone_number", ""),
        "role": current_patient["role"],
        "full_name": f"{current_patient['first_name']} {current_patient['last_name']}",
        "profile_image_url" : current_patient.get("profile_image_url", "")
    }


# # تحديث بيانات المريض الحالي
# @router.put("/me_update")
# async def update_patient_profile_endpoint(
#     update_data: UpdatePatientRequest,
#     current_patient: dict = Depends(get_current_patient)
# ):
#     return await update_patient_profile(update_data, current_patient)






# ================== عرض كل الدكاترة ==================
@router.get("/doctors")
async def list_doctors(current_patient: dict = Depends(get_current_patient)):
    """
    يعرض كل الدكاترة للعميل الحالي
    """
    return  await get_all_doctors_info()


# ================== عرض دكتور محدد ==================
@router.get("/doctors/{doctor_id}")
async def doctor_details(doctor_id: str, current_patient: dict = Depends(get_current_patient)):
    """
    يعرض كل بيانات الدكتور للعميل الحالي
    """
    return await get_doctor_info(doctor_id)


@router.post("/verify_otp")
async def verify_otp(request: OTPVerifyRequest):
    return await patient_controller.verify_login_otp(request)
@router.post("/send_otp")
async def send_otp(request: OTPRequest):
    return await patient_controller.send_otp_endpoint(request)






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
    current_user=Depends(get_current_patient)
):
    from Controller.doctor_controller import update_doctor
    import os

    update_data = UpdatePatientRequest(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        email=email,
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
    patient =await update_patient(update_data, current_user)

    return {
        "status": "success",
        "message": "Profile updated successfully",
        "data": patient
    }