-- ============================================================
-- HỆ THỐNG AUTORIDE - SCRIPT NÂNG CẤP DỮ LIỆU (autoride_db.sql)
-- ============================================================

CREATE DATABASE IF NOT EXISTS autoride_db;
USE autoride_db;

-- 1. Bảng Cars (Quản lý xe)
CREATE TABLE IF NOT EXISTS Cars (
    car_id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    license_plate VARCHAR(20) UNIQUE NOT NULL
);

-- 2. Tái cấu trúc bảng Rentals (Quản lý hợp đồng thuê xe)
DROP TABLE IF EXISTS Inspections;
DROP TABLE IF EXISTS Rentals;

CREATE TABLE Rentals (
    rental_id INT AUTO_INCREMENT PRIMARY KEY,
    car_id INT NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    rent_date DATETIME NOT NULL,
    return_date DATETIME,
    
    -- Khóa chặt trạng thái bằng ENUM theo Activity Diagram
    status ENUM('BOOKED', 'ACTIVE', 'COMPLETED', 'CANCELLED') DEFAULT 'BOOKED',
    
    -- Các cột tài chính kiểu DECIMAL chuẩn xác, tránh sai số số thực
    security_deposit DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    late_fee DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    damage_fee DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    
    CONSTRAINT fk_rentals_cars FOREIGN KEY (car_id) REFERENCES Cars(car_id) ON DELETE RESTRICT
);

-- 3. Tạo bảng Inspections (Biên bản kiểm tra tình trạng xe)
CREATE TABLE Inspections (
    inspection_id INT AUTO_INCREMENT PRIMARY KEY,
    rental_id INT NOT NULL,
    inspection_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    damage_description TEXT,
    inspector_name VARCHAR(100) NOT NULL,
    
    CONSTRAINT fk_inspections_rentals FOREIGN KEY (rental_id) REFERENCES Rentals(rental_id) ON DELETE RESTRICT
);

-- ============================================================
-- KỊCH BẢN MÔ PHỎNG VẬN HÀNH THỰC TẾ (DML)
-- ============================================================

-- Thêm dữ liệu xe mẫu
INSERT INTO Cars (model_name, license_plate) 
VALUES ('Toyota Camry', '30F-123.45');

-- 1. Khách "Nguyen Van A" đặt và nhận xe, đóng cọc 10.000.000 VNĐ (Trạng thái ACTIVE)
INSERT INTO Rentals (car_id, customer_name, rent_date, status, security_deposit)
VALUES (1, 'Nguyen Van A', '2026-10-01 08:00:00', 'ACTIVE', 10000000.00);

-- 2. Khách trả xe: Nhân viên kiểm tra phát hiện vỡ đèn pha trái
INSERT INTO Inspections (rental_id, inspection_date, damage_description, inspector_name)
VALUES (1, '2026-10-05 17:00:00', 'Vỡ đèn pha trái', 'Tran Van Inspector');

-- 3. Cập nhật hợp đồng: Trạng thái COMPLETED, ghi nhận phí phạt đền bù 2.000.000 VNĐ
UPDATE Rentals
SET return_date = '2026-10-05 17:00:00',
    status = 'COMPLETED',
    late_fee = 0.00,
    damage_fee = 2000000.00
WHERE rental_id = 1;

-- 4. Lệnh SELECT tính toán số tiền thực tế hoàn trả cho khách
-- Công thức: Refund = Deposit - Late_Fee - Damage_Fee
SELECT 
    r.rental_id,
    r.customer_name,
    c.model_name,
    c.license_plate,
    r.security_deposit,
    r.late_fee,
    r.damage_fee,
    (r.security_deposit - r.late_fee - r.damage_fee) AS actual_refund_amount,
    r.status
FROM Rentals r
JOIN Cars c ON r.car_id = c.car_id
WHERE r.rental_id = 1;