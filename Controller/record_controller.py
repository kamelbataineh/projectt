# record_controller.py
from fastapi import HTTPException, status
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from jose import jwt, JWTError
from database import mongo_db
from model.record_model import (
    CreateMedicalRecordRequest,
    UpdateMedicalRecordRequest,
    UpdateRecord
)

class MedicalRecordController:
    def __init__(self):
        self.patients_collection = mongo_db["patients"]
        self.doctors_collection = mongo_db["doctors"]
        self.medical_records_collection = mongo_db["medical_records"]
        self.SECRET_KEY = "mysecretkey"
        self.ALGORITHM = "HS256"

    # ================== دوال مساعدة ==================
    def convert_objectid_to_str(self, document):
        """تحويل جميع حقول ObjectId إلى سلسلة نصية"""
        if document is None:
            return None
        
        document = dict(document)
        for key, value in document.items():
            if isinstance(value, ObjectId):
                document[key] = str(value)
            elif isinstance(value, dict):
                document[key] = self.convert_objectid_to_str(value)
            elif isinstance(value, list):
                document[key] = [
                    self.convert_objectid_to_str(item) if isinstance(item, dict) else item
                    for item in value
                ]
        return document

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id = payload.get("id")
            role = payload.get("role")
            
            if not user_id or not role:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
            
            return {"_id": ObjectId(user_id), "role": role}
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

    async def create_medical_record(self, request: CreateMedicalRecordRequest, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can create medical records"
            )
    
        # التحقق من وجود المريض
        patient = await self.patients_collection.find_one({"_id": ObjectId(request.patient_id)})
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
    
        # التحقق من وجود الطبيب
        doctor = await self.doctors_collection.find_one({"_id": current_user["_id"]})
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
    
        # تحويل بيانات السجل من Pydantic إلى dict
        record_data = request.data.dict()
        doctor_full_name = f"{doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()
        initial_update = {
                "updated_by": doctor_full_name or "Unknown Doctor",
                "timestamp": datetime.utcnow(),
                "changes": "Initial record creation"
            }
        
        record_data["update_history"] = [initial_update]
    
        # إنشاء المستند النهائي مع IDs
        record_document = {
            "patient_id": ObjectId(request.patient_id),
            "doctor_id": current_user["_id"],
            "data": record_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
        # حفظ السجل في قاعدة البيانات
        result = await self.medical_records_collection.insert_one(record_document)
    
        return {
            "message": "Medical record created successfully",
            "record_id": str(result.inserted_id)
        }
    


    # ================== الحصول على سجل طبي ==================
    async def get_medical_record(self, record_id: str, current_user: dict):
        try:
            obj_id = ObjectId(record_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid record ID format"
            )

        record = await self.medical_records_collection.find_one({"_id": obj_id})
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found"
            )

        # التحقق من الصلاحيات
        if current_user["role"] == "patient":
            if record["patient_id"] != current_user["_id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this record"
                )
        elif current_user["role"] == "doctor":
            # يمكن للطبيب الوصول إلى جميع السجلات
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role"
            )

        # تحويل ObjectId إلى strings
        return self.convert_objectid_to_str(record)

    # ================== تعديل سجل طبي ==================
    async def update_medical_record(self, record_id: str, request: UpdateMedicalRecordRequest, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can update medical records"
            )

        try:
            obj_id = ObjectId(record_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid record ID format"
            )

        # التحقق من وجود الطبيب
        doctor = await self.doctors_collection.find_one({"_id": current_user["_id"]})
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )

        # البحث عن السجل الطبي
        record = self.medical_records_collection.find_one({"_id": obj_id})
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found"
            )


        record = await self.get_medical_record(record_id, current_user)
        
        # تحويل كلاهما إلى string قبل المقارنة
        if str(record["doctor_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update records you created"
            )
        

        # إعداد البيانات المحدثة
        updated_data = request.data.dict()
        
        doctor_full_name = f"{doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()
        new_update = UpdateRecord(
            updated_by=doctor_full_name or "Unknown Doctor",
            changes=request.changes_description
        )

        # الحفاظ على سجل التحديث القديم وإضافة الجديد
        existing_history = record["data"].get("update_history", [])
        existing_history.append(new_update.dict())
        updated_data["update_history"] = existing_history

        # تحديث السجل
        update_result = await self.medical_records_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "data": updated_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update medical record"
            )

        return {
            "message": "Medical record updated successfully",
            "update_history": existing_history
        }

    # ================== سجلات المريض (يشوف فقط سجلاته مع Pagination) ==================
    async def get_my_medical_records(self, page: int, limit: int, current_user: dict):
        if current_user["role"] != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can access their own records"
            )
    
        patient_id = current_user["_id"]
        skip = (page - 1) * limit
    
        total_records = await self.medical_records_collection.count_documents({"patient_id": patient_id})
    
        records_cursor = self.medical_records_collection.find({"patient_id": patient_id})\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
    
        records_list = await records_cursor.to_list(length=limit)
        records = [self.convert_objectid_to_str(record) for record in records_list]
    
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
    
        return {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "records": records
        }


    # ================== كل السجلات للدكاترة مع Pagination ==================
    async def get_doctor_records(self, page: int, limit: int, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can view all medical records"
            )

        if page < 1 or limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page and limit must be positive integers"
            )

        skip = (page - 1) * limit
        
        # حساب العدد الإجمالي للسجلات
        total_records = self.medical_records_collection.count_documents({})
        
        # جلب السجلات مع pagination وترتيب تنازلي
        records_cursor = self.medical_records_collection.find()\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        # تحويل السجلات باستخدام الدالة المساعدة
        records = [self.convert_objectid_to_str(record) for record in records_cursor]
        
        # حساب عدد الصفحات
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1

        return {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "records": records
        }

    # ================== سجلات المريض المحدد للطبيب ==================
    async def get_patient_records_for_doctor(self, patient_id: str, page: int, limit: int, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can access patient records"
            )

        try:
            patient_obj_id = ObjectId(patient_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient ID format"
            )

        # التحقق من وجود المريض
       # التحقق من وجود المريض
        patient = await self.patients_collection.find_one({"_id": patient_obj_id})
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )


        skip = (page - 1) * limit
        
        # حساب العدد الإجمالي لسجلات المريض
        total_records = await self.medical_records_collection.count_documents({
            "patient_id": patient_obj_id
        })

        
        # جلب سجلات المريض مع pagination
        records_cursor = self.medical_records_collection.find({
            "patient_id": patient_obj_id
        })\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(limit)
        
        records_cursor = self.medical_records_collection.find({"patient_id": patient_obj_id})\
    .sort("created_at", -1)\
    .skip(skip)\
    .limit(limit)
        records_list = await records_cursor.to_list(length=limit)
        records = [self.convert_objectid_to_str(record) for record in records_list]
        
        total_records = await self.medical_records_collection.count_documents({"patient_id": patient_obj_id})
        

        # حساب عدد الصفحات
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1

        return {
            "patient_id": patient_id,
            "patient_name": patient.get("name", "Unknown"),
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "records": records
        }

    # ================== سجلات الطبيب (الخاصة به فقط) ==================
    # ================== سجلات الطبيب (الخاصة به فقط) ==================
    async def get_doctor_created_records(self, page: int, limit: int, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can access created records"
            )
    
        skip = (page - 1) * limit
    
        # جلب عدد السجلات
        total_records = await self.medical_records_collection.count_documents({
            "doctor_id": current_user["_id"]
        })
    
        # جلب السجلات الفعلية مع pagination
        records_cursor = self.medical_records_collection.find({
            "doctor_id": current_user["_id"]
        }).sort("created_at", -1).skip(skip).limit(limit)
    
        # تحويل cursor إلى قائمة
        records_list = await records_cursor.to_list(length=limit)
    
        # تحويل ObjectId إلى str
        records = [self.convert_objectid_to_str(record) for record in records_list]
    
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
    
        return {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "records": records
        }







    async def get_patient_by_id(self, patient_id: str, current_user: dict):
        try:
            patient = await self.patients_collection.find_one(
                {"_id": ObjectId(patient_id)}
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid patient ID")
    
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
    
        return self.convert_objectid_to_str(patient)
    




    # ================== البحث في السجلات ==================
    async def search_medical_records(self, patient_name: Optional[str], doctor_name: Optional[str], 
        page: int, limit: int, current_user: dict):
        if current_user["role"] != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can search medical records"
            )

        skip = (page - 1) * limit
        query = {}
        
        # بناء query بناءً على معايير البحث
        if patient_name:
            # البحث عن مرضى بأسماء تحتوي على النص المدخل
            patients = list(self.patients_collection.find(
                {"name": {"$regex": patient_name, "$options": "i"}}
            ))
            patient_ids = [patient["_id"] for patient in patients]
            if patient_ids:
                query["patient_id"] = {"$in": patient_ids}
            else:
                # إذا لم يتم العثور على مرضى، فلن نرجع أي نتائج
                return {
                    "page": page,
                    "limit": limit,
                    "total_records": 0,
                    "total_pages": 0,
                    "has_previous": False,
                    "has_next": False,
                    "records": []
                }
        
        if doctor_name:
            # البحث عن أطباء بأسماء تحتوي على النص المدخل
            doctors = list(self.doctors_collection.find(
                {"name": {"$regex": doctor_name, "$options": "i"}}
            ))
            doctor_ids = [doctor["_id"] for doctor in doctors]
            if doctor_ids:
                query["doctor_id"] = {"$in": doctor_ids}
            elif not patient_name:
                # إذا لم يتم العثور على أطباء ولم يكن هناك بحث عن مرضى
                return {
                    "page": page,
                    "limit": limit,
                    "total_records": 0,
                    "total_pages": 0,
                    "has_previous": False,
                    "has_next": False,
                    "records": []
                }

        # حساب العدد الإجمالي
        total_records = self.medical_records_collection.count_documents(query)
        
        # جلب النتائج
        records_cursor = self.medical_records_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        records = [self.convert_objectid_to_str(record) for record in records_cursor]
        
        # إضافة معلومات إضافية للسجلات
        for record in records:
            # الحصول على معلومات المريض
            patient = self.patients_collection.find_one({"_id": ObjectId(record["patient_id"])})
            record["patient_name"] = patient.get("name", "Unknown") if patient else "Unknown"
            
            # الحصول على معلومات الطبيب
            doctor = self.doctors_collection.find_one({"_id": ObjectId(record["doctor_id"])})
            if doctor:
                record["doctor_name"] = f"{doctor.get('first_name','')} {doctor.get('last_name','')}".strip()
            else:
                record["doctor_name"] = "Unknown Doctor"
                total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
            
        return {
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "records": records
        }