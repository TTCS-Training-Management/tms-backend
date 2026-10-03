from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
import os

from avatar_service import save_and_crop_avatar

app = FastAPI(title="SCRUM-40 Upload Avatar API")

# Cấu hình static files để xem ảnh trên browser
os.makedirs("static/uploads/avatars", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/api/users/upload-avatar")
async def upload_avatar(file: UploadFile = File(...)):
    user_id = 1  # ID giả lập người dùng
    avatar_url = await save_and_crop_avatar(file, user_id)
    return {
        "message": "Tải lên ảnh đại diện thành công!",
        "avatar_url": avatar_url
    }