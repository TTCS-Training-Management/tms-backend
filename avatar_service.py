import os
import uuid
from PIL import Image
from fastapi import UploadFile, HTTPException, status

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
UPLOAD_DIR = "static/uploads/avatars"

async def save_and_crop_avatar(file: UploadFile, user_id: int) -> str:
    # 1. Kiểm tra định dạng đuôi file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File không hợp lệ. Chỉ chấp nhận định dạng JPG hoặc PNG."
        )

    # 2. Kiểm tra dung lượng (<= 2MB)
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kích thước ảnh vượt quá giới hạn 2MB."
        )

    # 3. Tạo thư mục lưu file nếu chưa có
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 4. Đọc ảnh, cắt vuông (Center Crop) và Resize 300x300
    file.file.seek(0)
    with Image.open(file.file) as img:
        width, height = img.size
        min_dim = min(width, height)

        left = (width - min_dim) / 2
        top = (height - min_dim) / 2
        right = (width + min_dim) / 2
        bottom = (height + min_dim) / 2

        img_cropped = img.crop((left, top, right, bottom))
        img_resized = img_cropped.resize((300, 300), Image.Resampling.LANCZOS)

        if img_resized.mode in ("RGBA", "P") and ext in [".jpg", ".jpeg"]:
            img_resized = img_resized.convert("RGB")

        filename = f"avatar_{user_id}_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        img_resized.save(filepath)

    return f"/static/uploads/avatars/{filename}"