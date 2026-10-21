from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.security.jwt import get_current_user, require_admin

router = APIRouter()

# Dữ liệu sản phẩm demo
DEMO_PRODUCTS = [
    {"id": 1, "name": "Khóa học Lập trình Python & FastAPI", "price": 1200000},
    {"id": 2, "name": "Khóa học Bảo mật Web & JWT Authentication", "price": 1500000},
    {"id": 3, "name": "Khóa học Cơ sở dữ liệu nâng cao", "price": 990000}
]


@router.get("/products", summary="Xem danh sách sản phẩm (Yêu cầu đăng nhập)")
def get_products(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    API yêu cầu người dùng phải đăng nhập (bất kể vai trò USER hay ADMIN).
    Header: Authorization: Bearer <token>
    """
    return {
        "message": "Bạn đã đăng nhập",
        "user": current_user,
        "products": DEMO_PRODUCTS
    }


from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str = "Khóa học Lập trình Web Fullstack"
    price: float = 2500000.0


@router.post("/products", status_code=201, summary="Thêm sản phẩm mới (Chỉ dành cho ADMIN)")
def create_product(
    product: ProductCreate,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """
    API tạo mới sản phẩm:
    - Bắt buộc phải có token hợp lệ
    - Quyền hạn (role) phải là ADMIN
    """
    new_product = {"id": len(DEMO_PRODUCTS) + 1, "name": product.name, "price": product.price}
    DEMO_PRODUCTS.append(new_product)
    return {
        "message": "Thêm sản phẩm mới thành công",
        "created_by": current_user.get("sub"),
        "product": new_product
    }


@router.delete("/products/{product_id}", summary="Xóa sản phẩm (Chỉ dành cho ADMIN)")
def delete_product(
    product_id: int,
    current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """
    API xóa sản phẩm:
    - Bắt buộc vai trò ADMIN
    - Nếu là USER thường sẽ bị trả về 403 Forbidden
    """
    return {
        "message": f"Xóa sản phẩm {product_id} thành công",
        "deleted_by": current_user.get("sub")
    }
