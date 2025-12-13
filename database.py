# database.py

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

MONGO_URL = "mongodb+srv://kamelbataineh:Kamel123@cluster0.cf0rmeu.mongodb.net/university_project?retryWrites=true&w=majority&appName=Cluster0"

try:
    # إنشاء الاتصال باستخدام Motor
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    
    # اختيار قاعدة البيانات
    mongo_db = mongo_client["university_project"]
    
    # اختيار الـ Collections
    admins_collection = mongo_db["admins"]
    doctors_collection = mongo_db["doctors"]
    appointments_collection = mongo_db["appointments"]
    patients_collection = mongo_db["patients"]
    otp_collection = mongo_db["otp_storage"]
    predictions_collection = mongo_db["predictions"]
    medical_records_collection = mongo_db["medical_records"]

    # مؤقتاً
    temp_patients_collection = mongo_db["temp_patients"]
    temp_doctors_collection = mongo_db["temp_doctors"]
    messages_collection = mongo_db["messages"]
    print("✅ Connected to MongoDB successfully!")

except ConnectionFailure as e:
    print("❌ MongoDB connection failed:", e)
except Exception as e:
    print("❌ MongoDB unknown error:", e)
