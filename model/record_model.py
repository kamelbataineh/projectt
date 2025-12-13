# models/record_models.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from bson import ObjectId

# ================== نماذج Pydantic ==================
class Medication(BaseModel):
    name: str
    dose: str

class Surgery(BaseModel):
    type: str
    date: datetime

class Lifestyle(BaseModel):
    exercise: str
    stress_level: str

class BasicInfo(BaseModel):
    age: int
    gender: str

class UpdateRecord(BaseModel):
    updated_by: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    changes: str

class MedicalRecordData(BaseModel):
    basic_info: BasicInfo
    diseases: List[str] = []
    allergies: List[str] = []
    medications: List[Medication] = []
    surgeries: List[Surgery] = []
    family_history: List[str] = []
    lifestyle: Lifestyle
    current_symptoms: Optional[str] = ""
    notes: Optional[str] = ""
    update_history: List[UpdateRecord] = []
    diagnosis: str  # <-- هذا الحقل مطلوب!

class CreateMedicalRecordRequest(BaseModel):
    patient_id: str
    data: MedicalRecordData

class UpdateMedicalRecordRequest(BaseModel):
    data: MedicalRecordData
    changes_description: str

class PaginatedResponse(BaseModel):
    page: int
    limit: int
    total_records: int
    total_pages: int
    has_previous: bool
    has_next: bool
    records: List[dict]