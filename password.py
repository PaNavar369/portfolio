# setup.py
from pymongo import MongoClient
import bcrypt
from datetime import datetime

# Your connection string
MONGO_URI = "mongodb+srv://naveenpalla2000_db_user:sBfASZwVH7ptMGdV@cluster0.b8bi0rg.mongodb.net/?appName=Cluster0"

# Connect
client = MongoClient(MONGO_URI)
db = client["portfolio"]
admin_collection = db["admin"]

print("🔐 Setting up admin password")
password = input("Enter your password: ")

# Hash password
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Save to MongoDB
admin_collection.insert_one({
    "type": "admin_password",
    "password_hash": hashed.decode('utf-8'),
    "created_at": datetime.utcnow()
})

print(" Password saved successfully!")
print(f" Database: portfolio")
print(f" Collection: admin")