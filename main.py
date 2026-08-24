from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from google.auth.transport import requests
import google.oauth2.id_token
from fastapi import Form
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import UploadFile, File
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import generate_blob_sas
from azure.storage.blob import BlobSasPermissions
import hashlib
import bcrypt
import os
import gridfs
import ssl
import certifi
from bson.errors import InvalidId

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Connection to MongoDB
MongoURI = "mongodb+srv://naveenpalla2000_db_user:VfjAViht8ZLOmZ3E@cluster0.b8bi0rg.mongodb.net/?appName=Cluster0"
client = MongoClient(
    MongoURI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)
db = client["portfolio"]

admin_collection = db["admin"]
education_collection = db["education"]
projects_collection = db["projects"]
profile_collection = db["profile"] 
content_collection = db["content"]
fs = gridfs.GridFS(db)

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.webp', '.svg'}

def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.png', '.jpg', '.jpeg', '.webp', '.svg'}:
        return 'image'
    elif ext == '.gif':
        return 'gif'
    elif ext == '.pdf':
        return 'pdf'
    return 'other'

def create_password():
    password = "Wassup"
    print(password)
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    existing = admin_collection.find_one({"type": "admin_password"})
    if existing:
        admin_collection.update_one(
            {"type": "admin_password"},
            {"$set": {
                "password_hash": hashed,
                "updated_at": datetime.utcnow()
            }}
        )
        return {"message": f"Password UPDATED to: {password}"}
    else:
        admin_collection.insert_one({
            "type": "admin_password",
            "password_hash": hashed,
            "created_at": datetime.utcnow()
        })
        return {"message": f"Password CREATED: {password}"}

# Uncomment to create password on startup
# create_password()

# ============================================================ #
# ✅ SEED DEFAULT CONTENT (MUST BE CALLED)                      #
# ============================================================ #
def seed_default_content():
    """Insert default content if it doesn't exist"""
    default_content = {
        "hero_title": "Hi, I'm Naveen Palla",
        "hero_subtitle": "IT Professional | MSc in Big Data Management & Analytics",
        "hero_description": "Data Techie and IT Professional with a Master's degree in Big Data Management & Analytics. Specializing in building scalable data pipelines, cloud-native architectures, and Full-Stack Development, I bridge the gap between raw data and business intelligence. Passionate about transforming complex data into actionable insights using Python, Spark, and modern cloud platforms.",
        "footer_name": "Naveen Palla",
        "footer_title": "IT Professional | MSc in Big Data Management & Analytics",
        "footer_email": "naveenpalla2000@gmail.com",
        "footer_phone": "+353 894898683",
        "footer_location": "Dublin, Ireland",
        "footer_copyright": "© 2024 Naveen Palla. All rights reserved."
    }
    
    for key, value in default_content.items():
        existing = content_collection.find_one({"key": key})
        if not existing:
            content_collection.insert_one({
                "key": key,
                "value": value,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            print(f"✅ Seeded default content: {key}")
        else:
            print(f"⚠️ Content already exists: {key}")

# ✅ ✅ ✅ CALL THIS FUNCTION ON STARTUP ✅ ✅ ✅
seed_default_content()

# ============================================================ #
# GET ALL CONTENT                                               #
# ============================================================ #
def get_all_content():
    """Fetch all content from database"""
    if db is None:
        return {}
    try:
        content_dict = {}
        for doc in content_collection.find():
            content_dict[doc["key"]] = doc.get("value", "")
        return content_dict
    except Exception as e:
        print(f"Error fetching content: {e}")
        return {}

@app.get("/get-content/{key}")
async def get_content(key: str):
    """Get content from database by key"""
    if db is None:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Database not connected"
            }
        )
    
    try:
        doc = content_collection.find_one({"key": key})
        if doc:
            return JSONResponse(
                content={
                    "success": True,
                    "key": key,
                    "value": doc.get("value", "")
                }
            )
        else:
            return JSONResponse(
                content={
                    "success": False,
                    "key": key,
                    "value": "",
                    "message": "Content not found"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error fetching content: {str(e)}"
            }
        )

@app.post("/update-content")
async def update_content(
    key: str = Form(...),
    value: str = Form(...)
):
    """Update or create content - REPLACES existing content"""
    if db is None:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Database not connected"
            }
        )
    
    try:
        existing = content_collection.find_one({"key": key})
        if existing:
            content_collection.delete_one({"key": key})
            print(f"🗑️ Deleted existing content: {key}")
        
        content_collection.insert_one({
            "key": key,
            "value": value,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        print(f"✅ Created new content: {key} = {value[:50]}...")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Content '{key}' updated successfully!",
                "key": key,
                "value": value
            }
        )
            
    except Exception as e:
        print(f"❌ Error updating content: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error updating content: {str(e)}"
            }
        )

# ============================================================ #
# HOME PAGE                                                     #
# ============================================================ #
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    print("route hit")
    
    # Fetch education from database
    education_list = []
    if education_collection is not None:
        education_cursor = education_collection.find().sort("end_year", -1)
        for edu in education_cursor:
            education_list.append({
                "id": str(edu["_id"]),
                "institution": edu.get("institution", ""),
                "degree": edu.get("degree", ""),
                "start_year": edu.get("start_year", 0),
                "end_year": edu.get("end_year", 0),
                "description": edu.get("description", "")
            })
    
    print(f"Rendering homepage with {len(education_list)} education entries")
    
    # Fetch projects
    project_list = []
    if projects_collection is not None:
        project_cursor = projects_collection.find().sort("created_at", -1)
        for project in project_cursor:
            project_list.append({
                "id": str(project["_id"]),
                "title": project.get("title", ""),
                "description": project.get("description", ""),
                "file_id": project.get("file_id", ""), 
                "file_type": project.get("file_type", ""),
                "file_name": project.get("file_name", ""),
                "technologies": project.get("technologies", []),
                "github_link": project.get("github_link", ""),
                "created_at": project.get("created_at", datetime.utcnow()).isoformat()
            })
    
    # ✅ Fetch content from database
    content = get_all_content()
    
    # ✅ Debug print
    print(f"📝 Content keys: {list(content.keys())}")
    print(f"📝 hero_description: {content.get('hero_description', 'NOT FOUND')[:50]}...")
    
    # Fetch profile photo
    profile_photo = None
    profile = profile_collection.find_one({"type": "profile_photo"})
    if profile and profile.get("file_id"):
        profile_photo = profile["file_id"]
    
    print("im here")
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "education": education_list,
        "projects": project_list,
        "profile_photo": profile_photo,
        "content": content
    })

@app.get("/admin.html", response_class=HTMLResponse)
async def admin_page(request: Request):
    print("Admin route hit")
    return templates.TemplateResponse("admin.html", {'request': request})

# ============================================================ #
# LOGIN ROUTE                                                   #
# ============================================================ #
@app.post('/login')
async def login(request: Request, password: str = Form(...)):
    print("login route")
    print(password)
    try:
        admin_doc = admin_collection.find_one({"type": "admin_password"})
        print(admin_doc)
        if not admin_doc:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "No password set. Please contact administrator."
                }
            )
        stored_hash = admin_doc["password_hash"]
        print(stored_hash)
        original_password = bcrypt.checkpw(password.encode('utf-8'), stored_hash)
        if original_password:
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Login successful!",
                    "redirect": "/"
                }
            )
        else:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Incorrect password! Please try again."
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Login error: {str(e)}"
            }
        )

# ============================================================ #
# UPLOAD PROFILE PHOTO                                          #
# ============================================================ #
@app.post("/upload-profile-photo")
async def upload_profile_photo(file: UploadFile = File(...)):
    print("route upload is clicked")
    if fs is None:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Database not connected"
            }
        )
    try:
        if not is_allowed_file(file.filename):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "File type not allowed. Allowed: PNG, JPG, JPEG, GIF, WEBP, SVG"
                }
            )
        contents = await file.read()
        
        existing_profile = profile_collection.find_one({"type": "profile_photo"})
        
        if existing_profile and existing_profile.get("file_id"):
            try:
                fs.delete(ObjectId(existing_profile["file_id"]))
                print(f"Deleted old profile photo: {existing_profile['file_id']}")
            except Exception as e:
                print(f"⚠️ Could not delete old photo: {e}")
        
        file_id = fs.put(
            contents,
            filename=file.filename,
            content_type=file.content_type or "image/jpeg",
            uploaded_at=datetime.utcnow()
        )
        
        if existing_profile:
            profile_collection.update_one(
                {"type": "profile_photo"},
                {"$set": {
                    "file_id": str(file_id),
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "updated_at": datetime.utcnow()
                }}
            )
        else:
            profile_collection.insert_one({
                "type": "profile_photo",
                "file_id": str(file_id),
                "filename": file.filename,
                "content_type": file.content_type,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
        return JSONResponse(
            content={
                "success": True,
                "message": "Profile photo uploaded successfully!",
                "file_id": str(file_id)
            }
        )
    except Exception as e:
        print(f" Error uploading profile photo: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error uploading photo: {str(e)}"
            }
        )

# ============================================================ #
# DEBUG FILES                                                   #
# ============================================================ #
@app.get("/debug-files")
async def debug_files():
    """Debug route to list all files in GridFS"""
    try:
        files = []
        for file_data in fs.find():
            files.append({
                "_id": str(file_data._id),
                "filename": file_data.filename,
                "content_type": file_data.content_type,
                "upload_date": file_data.upload_date.isoformat() if file_data.upload_date else None,
                "length": file_data.length
            })
        
        return {
            "total_files": len(files),
            "files": files
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================ #
# UPLOAD EDUCATION                                              #
# ============================================================ #
@app.post("/upload-education")
async def upload_education(
    institution: str = Form(...),
    degree: str = Form(...),
    start_year: int = Form(...),
    end_year: int = Form(...),
    description: str = Form("")
):
    print("upload Education route hit")
    print(degree)
    print(start_year)
    try:
        if education_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected. Please try again later."
                }
            )
        else:
            education_dict = {
                "institution": institution,
                "degree": degree,
                "start_year": start_year,
                "end_year": end_year,
                "description": description,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = education_collection.insert_one(education_dict)
            print(result)
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Education uploaded successfully!",
                    "id": str(result.inserted_id),
                    "data": {
                        "institution": institution,
                        "degree": degree,
                        "start_year": start_year,
                        "end_year": end_year,
                        "description": description
                    }
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error uploading education: {str(e)}"
            }
        )

# ============================================================ #
# GET EDUCATION                                                 #
# ============================================================ #
@app.get("/get-education")
async def get_education(request: Request):
    print("im at printing here")
    try:
        if education_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected",
                    "education": []
                }
            )
        education_cursor = education_collection.find().sort("end_year", -1)
        education_list = []
        for edu in education_cursor:
            education_list.append({
                "id": str(edu["_id"]),
                "institution": edu.get("institution", ""),
                "degree": edu.get("degree", ""),
                "start_year": edu.get("start_year", 0),
                "end_year": edu.get("end_year", 0),
                "description": edu.get("description", ""),
                "created_at": edu.get("created_at", datetime.utcnow()).isoformat() if edu.get("created_at") else ""
            })
        return JSONResponse(
            content={
                "success": True,
                "education": education_list,
                "count": len(education_list)
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error fetching education: {str(e)}",
                "education": []
            }
        )

# ============================================================ #
# DELETE EDUCATION                                              #
# ============================================================ #
@app.delete("/delete-education/{education_id}")
async def delete_education(education_id: str):
    print("delete education route hit")
    try:
        if education_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected"
                }
            )
        result = education_collection.delete_one({"_id": ObjectId(education_id)})
        if result.deleted_count > 0:
            print(f"Deleted education with ID: {education_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Education deleted successfully!"
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Education not found"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ============================================================ #
# UPLOAD PROJECT                                                #
# ============================================================ #
@app.post("/upload-project")
async def upload_project(
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(None),
    technologies: str = Form(""),
    github_link: str = Form("")
):
    print("upload project route hit")
    print(description)
    print(technologies)
    try:
        if projects_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected"
                }
            )
        print("skipped if block")
        tech_list = [tech.strip() for tech in technologies.split(",") if tech.strip()]
        
        file_id = None
        file_type = None
        file_name = None
        
        if file and file.filename:
            if not is_allowed_file(file.filename):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "File type not allowed. Allowed: PNG, JPG, GIF, PDF, WEBP, SVG"
                    }
                )
            try:
                contents = await file.read()
                file_id = fs.put(
                    contents,
                    filename=file.filename,
                    content_type=file.content_type or "application/octet-stream",
                    uploaded_at=datetime.utcnow()
                )
                file_type = get_file_type(file.filename)
                file_name = file.filename
                print(f"✅ File saved to GridFS with ID: {file_id}")
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Error uploading file: {str(e)}"
                    }
                )
        
        print("entering into database")
        project_dict = {
            "title": title,
            "description": description,
            "file_id": str(file_id) if file_id else None,
            "file_type": file_type,
            "file_name": file_name,
            "technologies": tech_list,
            "github_link": github_link,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = projects_collection.insert_one(project_dict)
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Project uploaded successfully!",
                "id": str(result.inserted_id),
                "file_id": str(file_id) if file_id else None
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error uploading project: {str(e)}"
            }
        )

# ============================================================ #
# UPDATE PROJECT                                                #
# ============================================================ #
@app.put("/update-project/{project_id}")
async def update_project(
    project_id: str,
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(None),
    technologies: str = Form(""),
    github_link: str = Form("")
):
    print("update project route hit:", project_id)
    try:
        if projects_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected"
                }
            )

        try:
            obj_id = ObjectId(project_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Invalid project id"
                }
            )

        existing_project = projects_collection.find_one({"_id": obj_id})
        if not existing_project:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Project not found"
                }
            )

        tech_list = [tech.strip() for tech in technologies.split(",") if tech.strip()]

        update_dict = {
            "title": title,
            "description": description,
            "technologies": tech_list,
            "github_link": github_link,
            "updated_at": datetime.utcnow()
        }

        if file and file.filename:
            if not is_allowed_file(file.filename):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "File type not allowed. Allowed: PNG, JPG, GIF, PDF, WEBP, SVG"
                    }
                )

            try:
                contents = await file.read()
                new_file_id = fs.put(
                    contents,
                    filename=file.filename,
                    content_type=file.content_type or "application/octet-stream",
                    uploaded_at=datetime.utcnow()
                )
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Error uploading file: {str(e)}"
                    }
                )

            old_file_id = existing_project.get("file_id")
            if old_file_id:
                try:
                    fs.delete(ObjectId(old_file_id))
                except Exception as e:
                    print(f"Warning: could not delete old file {old_file_id}: {e}")

            update_dict["file_id"] = str(new_file_id)
            update_dict["file_type"] = get_file_type(file.filename)
            update_dict["file_name"] = file.filename

        print("updating project in database")
        projects_collection.update_one(
            {"_id": obj_id},
            {"$set": update_dict}
        )

        return JSONResponse(
            content={
                "success": True,
                "message": "Project updated successfully!",
                "id": project_id
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error updating project: {str(e)}"
            }
        )

# ============================================================ #
# GET FILE                                                      #
# ============================================================ #
@app.get("/file/{file_id}")
async def get_file(file_id: str):
    """Get file from GridFS"""
    try:
        file_data = fs.get(ObjectId(file_id))
        return Response(
            content=file_data.read(),
            media_type=file_data.content_type or "application/octet-stream"
        )
    except Exception as e:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "File not found"
            }
        )

# ============================================================ #
# DELETE PROJECT                                                #
# ============================================================ #
@app.delete("/delete-project/{project_id}")
async def delete_project(project_id: str):
    try:
        if projects_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected"
                }
            )
        project = projects_collection.find_one({"_id": ObjectId(project_id)})
        
        if not project:
            print(f"❌ Project not found with ID: {project_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Project not found"
                }
            )
        
        if project.get("file_id"):
            try:
                fs.delete(ObjectId(project["file_id"]))
                print(f"✅ Deleted file from GridFS: {project['file_id']}")
            except Exception as e:
                print(f"⚠️ Could not delete file: {e}")
        
        result = projects_collection.delete_one({"_id": ObjectId(project_id)})
        if result.deleted_count > 0:
            print(f"✅ Deleted project with ID: {project_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Project deleted successfully!"
                }
            )
        else:
            print(f"❌ Failed to delete project with ID: {project_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Project not found"
                }
            )
    except Exception as e:
        print(f"❌ Error deleting project: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ============================================================ #
# GET PROJECTS (API)                                            #
# ============================================================ #
@app.get("/get-projects")
async def get_projects():
    try:
        if projects_collection is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Database not connected",
                    "projects": []
                }
            )
        
        project_cursor = projects_collection.find().sort("created_at", -1)
        project_list = []
        for project in project_cursor:
            project_list.append({
                "id": str(project["_id"]),
                "title": project.get("title", ""),
                "description": project.get("description", ""),
                "file_id": project.get("file_id", ""),
                "file_type": project.get("file_type", ""),
                "technologies": project.get("technologies", []),
                "github_link": project.get("github_link", ""),
                "created_at": project.get("created_at", datetime.utcnow()).isoformat()
            })
        return JSONResponse(
            content={
                "success": True,
                "projects": project_list,
                "count": len(project_list)
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}",
                "projects": []
            }
        )

