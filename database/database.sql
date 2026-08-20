CREATE DATABASE IF NOT EXISTS speed_detection;
USE speed_detection;

CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','operator') NOT NULL DEFAULT 'operator',
    status ENUM('active','disabled') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cameras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    camera_code VARCHAR(50) NOT NULL UNIQUE,
    camera_name VARCHAR(100) NOT NULL,
    location VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    speed_limit DECIMAL(6,2) NOT NULL,
    measurement_distance DECIMAL(8,2) NOT NULL,
    camera_token_hash VARCHAR(255) NOT NULL DEFAULT '',
    status ENUM('active','disabled') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detection_runs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    camera_id INT NOT NULL,
    video_source VARCHAR(255),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    status ENUM('running','completed','failed','stopped') NOT NULL DEFAULT 'running',
    FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vehicles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    detection_run_id BIGINT NOT NULL,
    object_id INT NOT NULL,
    vehicle_type VARCHAR(50),
    first_seen DATETIME,
    last_seen DATETIME,
    FOREIGN KEY (detection_run_id) REFERENCES detection_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id BIGINT NOT NULL,
    plate_number VARCHAR(50),
    confidence DECIMAL(5,2),
    image_path VARCHAR(500),
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS violations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    camera_id INT NOT NULL,
    detection_run_id BIGINT NOT NULL,
    vehicle_id BIGINT NOT NULL,
    plate_id BIGINT,
    speed DECIMAL(8,2) NOT NULL,
    speed_limit DECIMAL(8,2) NOT NULL,
    excess_speed DECIMAL(8,2) GENERATED ALWAYS AS (speed - speed_limit) STORED,
    evidence_path VARCHAR(500),
    violation_time DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE,
    FOREIGN KEY (detection_run_id) REFERENCES detection_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (plate_id) REFERENCES plates(id) ON DELETE SET NULL
);

INSERT IGNORE INTO admins (username, password_hash, role, status) VALUES
('admin', '$2b$12$LJ3m4ys3Lz0gYB1V8bWD9eyZkS1Tm6GtHkf9VjV.2G5Yd0IXCqOe', 'admin', 'active');
