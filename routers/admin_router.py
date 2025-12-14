# admin_router.py
from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from Controller.admin_controller import admin_controller 
from jose import jwt, JWTError
from database import patients_collection

# ----------------- Models -----------------
class AdminRegisterModel(BaseModel):
    email: EmailStr
    password: str

class AdminLoginModel(BaseModel):
    email: EmailStr
    password: str

# ----------------- Router -----------------
router = APIRouter(prefix="/admin", tags=["Admin"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")



SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

# ----------------- Token dependency -----------------
async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ----------------- Endpoints -----------------

@router.post("/register")
async def register_admin(admin: AdminRegisterModel):
    return await admin_controller.register(admin.email, admin.password)

@router.post("/login")
async def login_admin(admin: AdminLoginModel):
    return await admin_controller.login(admin.email, admin.password)

@router.get("/doctor")
async def get_users(current_admin=Depends(get_current_admin)):
    return await admin_controller.get_all_users()

@router.put("/doctor/update/{doctor_id}")
async def update_doctor_status(
    doctor_id: str,
    is_active: bool = Body(None),
    is_approved: bool = Body(None),
    current_admin=Depends(get_current_admin)
):
    return await admin_controller.update_doctor(doctor_id, is_active, is_approved)


@router.get("/patients")
async def get_all_patients():
    patients = await patients_collection.find().to_list(length=200)

    # تحويل ObjectId إلى نص
    for p in patients:
        p["_id"] = str(p["_id"])

    return patients


# ---------------- تغيير حالة المريض ----------------
@router.put("/patient/{patient_id}/toggle_active")
async def toggle_patient_active(patient_id: str, payload: dict):
    """
    تغيير حالة تفعيل المريض (نشط / غير نشط)
    payload: {"is_active": true/false}
    """
    is_active = payload.get("is_active")
    if is_active is None:
        raise HTTPException(status_code=400, detail="is_active field is required")

    updated_patient = await admin_controller.update_patient(patient_id, is_active)
    return {"message": "Patient status updated", "patient": updated_patient}



@router.delete("/doctor/{doctor_id}")
async def delete_doctor(doctor_id: str, current_admin=Depends(get_current_admin)):
    result = await admin_controller.delete_doctor(doctor_id)
    return result


    # ---------------- حذف المريض ----------------
@router.delete("/patient/{patient_id}")
async def delete_patient(patient_id: str, current_admin=Depends(get_current_admin)):
    result = await admin_controller.delete_patient(patient_id)
    return result



# ---------------- تسجيل الخروج ----------------
@router.post("/logout")
async def logout_admin(current_admin=Depends(get_current_admin)):
    """
    تسجيل الخروج: ببساطة يُعلم العميل أن يسجل الخروج
    """
    return {"message": "Logged out successfully"}
