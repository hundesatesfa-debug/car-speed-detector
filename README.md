# Vehicle Speed Detection, License Plate Recognition & Traffic Violation Management System

A complete end-to-end system that detects speeding vehicles from video footage, recognizes license plates using OCR, generates annotated evidence images, stores violations in a database, and displays everything through a web dashboard.

---

## How the System Works (Deep Walkthrough)

### High-Level Pipeline

```
Video Source (file or camera stream)
        |
        v
  [1] YOLOv11 Vehicle Detection
        |  - Runs every frame through YOLO nano model
        |  - Filters to vehicle classes only (car, motorcycle, bus, truck)
        |  - Returns bounding box + class for each vehicle
        |
        v
  [2] Persistent Object Tracking
        |  - YOLO's built-in tracker assigns stable IDs across frames
        |  - A car detected in frame 1 and frame 50 gets the same ID
        |  - This is what makes speed calculation possible
        |
        v
  [3] Position Tracking (Line-Crossing Method)
        |  - Two invisible horizontal lines drawn on the frame (Line A, Line B)
        |  - The Y-pixel distance between them represents a known real-world distance
        |  - When a vehicle's center crosses Line A -> record the frame number
        |  - When the same vehicle's center crosses Line B -> record that frame number
        |
        v
  [4] Speed Calculation
        |  - frames_taken = frame_at_B - frame_at_A
        |  - time_seconds = frames_taken / video_FPS
        |  - speed_mps = measurement_distance_meters / time_seconds
        |  - speed_kmh = speed_mps * 3.6
        |
        v
  [5] Speed Limit Comparison
        |  - If speed_kmh > camera.speed_limit -> VIOLATION
        |  - Each vehicle only triggers ONE violation per detection run
        |  - Prevents duplicate violations for the same speeding event
        |
        v
  [6] License Plate Detection + OCR
        |  - Crops the vehicle bounding box from the frame
        |  - Searches the lower 60% of the vehicle for plate-like rectangles
        |    using contour detection + aspect ratio filtering
        |  - Each candidate is enlarged 5x and processed through 5 different
        |    image preprocessing methods (see detailed section below)
        |  - EasyOCR runs on each version, allowing only A-Z and 0-9
        |  - Best result (highest confidence) is selected
        |
        v
  [7] Evidence Image Generation
        |  - Takes the full frame at the moment of violation
        |  - Draws on it: bounding box, vehicle ID, type, speed, limit, plate
        |  - Saves annotated JPEG to backend/violations/
        |
        v
  [8] Database Storage
        |  - Creates records in: vehicles -> plates -> violations
        |  - Links everything via foreign keys
        |  - Also records the detection run metadata
        |
        v
  [9] Web Dashboard
        |  - Flask serves the frontend as static files
        |  - JavaScript calls REST API endpoints with JWT auth
        |  - Displays cameras, violations, evidence images, reports
```

---

### Detailed: YOLO Detection & Tracking

**File:** `backend/services/yolo.py`

The system uses `ultralytics` to load a YOLOv11 nano model (`models/yolo11n.pt`, ~5.6MB). The model is loaded once as a singleton and reused across all frames.

```python
results = model.track(frame, persist=True, conf=0.3, classes=[2, 3, 5, 7], verbose=False)
```

Key parameters:
- `persist=True` -- tells the tracker to remember objects from the previous frame. This is what gives each vehicle a stable integer ID (object_id) that persists across the entire video.
- `conf=0.3` -- only keep detections with confidence above 30%
- `classes=[2, 3, 5, 7]` -- only detect cars (2), motorcycles (3), buses (5), trucks (7). Ignore people, traffic lights, etc.

The tracker internally uses ByteTrack or BoT-SORT (ultralytics default) to match bounding boxes between consecutive frames based on position, size, and appearance features.

**Output per frame:** A set of bounding boxes `[x1, y1, x2, y2]`, each with a stable `object_id` and `class_id`.

---

### Detailed: Speed Calculation (Line-Crossing Method)

**File:** `backend/services/speed.py`

This is a fixed-distance timing method. Two horizontal lines are defined at specific Y-pixel positions in the video frame. The real-world distance between them is configured per camera via `measurement_distance` (default: 10 meters).

**How it works step by step:**

1. Each camera has two Y-pixel thresholds: `Line A` (top, default y=200) and `Line B` (bottom, default y=400). Vehicles moving downward in the frame will cross Line A first, then Line B.

2. When a vehicle's center Y-coordinate crosses Line A for the first time, we record `start_frames[object_id] = frame_number`. We only record this once per object -- if the vehicle was already tracked past Line A, we don't reset.

3. When the same vehicle's center Y-coordinate reaches Line B, we check if it was previously recorded at Line A. If yes, we calculate:
   ```
   frames_taken = frame_number_at_B - frame_number_at_A
   time_seconds = frames_taken / video_FPS
   speed_mps = measurement_distance / time_seconds
   speed_kmh = speed_mps * 3.6
   ```

4. The speed is stored in `speeds[object_id]` and returned. The vehicle only gets one speed measurement -- subsequent crossings are ignored.

**Why this works:** If the real-world distance between Line A and Line B is 10 meters, and a car takes 0.5 seconds to travel between them, that's 20 m/s = 72 km/h.

**Calibration:** The `measurement_distance`, `line_a_y`, and `line_b_y` values must be calibrated for each camera installation to match the actual road geometry. These are stored per camera in the database.

**Limitations:** This method gives average speed between two points, not instantaneous speed. It works best when the camera angle shows vehicles moving mostly vertically in the frame.

---

### Detailed: License Plate Recognition

**File:** `backend/services/plate.py`

This is a multi-stage process: locate the plate, preprocess it, then OCR it.

**Stage 1 -- Plate Region Detection (`find_plate_candidates`):**

1. Take the vehicle bounding box crop (the full detected vehicle from the frame).
2. Focus on the lower 60% of the vehicle (plates are typically on the bumper area).
3. Convert to grayscale, apply Gaussian blur, run Canny edge detection.
4. Find contours in the edge image.
5. Filter contours by:
   - Minimum area (>= 80 pixels) -- ignore tiny noise
   - Aspect ratio between 1.5 and 6.5 -- plates are wider than tall
   - Minimum width (>= 25px) and height (>= 8px)
6. Add 10% horizontal and 20% vertical padding around each candidate.
7. Return all candidate crops.

**Stage 2 -- Multi-Version OCR (`read_plate`):**

Each plate candidate is enlarged 5x using cubic interpolation (makes small text larger for better OCR). Then 5 different image versions are created:

| Version | Processing | Why |
|---------|-----------|-----|
| `original` | Just the 5x enlarged color image | Sometimes OCR works best on raw input |
| `gray` | Grayscale conversion | Removes color noise, focuses on contrast |
| `equalized` | Histogram equalization on grayscale | Enhances contrast in low-contrast images |
| `threshold` | Adaptive Gaussian thresholding (blockSize=31, C=11) | Binarizes the image, handles uneven lighting |
| `otsu` | Otsu's auto-thresholding | Finds optimal binary threshold automatically |

**Stage 3 -- OCR Reading:**

EasyOCR runs on each of the 5 versions with:
- `allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"` -- only accept alphanumeric characters
- Results are uppercased, non-alphanumeric characters are stripped via regex
- Results shorter than 3 characters are discarded (too short to be a plate)

**Stage 4 -- Best Result Selection:**

All OCR results from all versions and all candidates are collected. The result with the highest confidence score is selected as the final plate reading. This approach maximizes the chance of getting a correct reading because different preprocessing methods work better on different plate images (lighting, angle, dirt, etc.).

---

### Detailed: Violation Handling & Deduplication

**File:** `backend/services/detection.py`

When the calculated speed exceeds the camera's speed limit:

1. A violation is only created once per vehicle per detection run. The `violations_set` dictionary tracks which object_ids have already been flagged.

2. The vehicle is inserted into the `vehicles` table (if not already tracked), and the plate is inserted into `plates` (if OCR succeeded).

3. An annotated evidence image is created with overlays: vehicle ID, type, speed, speed limit, plate number, and a large "VIOLATION" label.

4. A violation record is inserted into the `violations` table linking camera, detection run, vehicle, plate, speed, and evidence image path.

5. Detection runs in a background thread so the API responds immediately while processing continues.

---

### Detailed: Evidence Image Generation

**File:** `backend/utils/helpers.py`

Each violation produces a JPEG image showing:
- Green bounding box around the speeding vehicle
- Label above the box: `car ID:15`
- Red text below the box: `Speed: 78.0 km/h`
- Yellow text below that: `Limit: 50 km/h`
- Large red `VIOLATION` label at the top-left
- Cyan text if plate was read: `Plate: ABC1234`

Images are saved as `violation_{object_id}_{YYYYMMDD_HHMMSS}.jpg` in `backend/violations/`.

---

### Detailed: Authentication & Security

**File:** `backend/routes/auth.py`, `backend/utils/security.py`

- Passwords are hashed with bcrypt before storage. The default admin account is created on first startup with credentials `admin` / `admin`.
- Authentication uses JWT (JSON Web Tokens) with 24-hour expiry.
- All `/api/*` routes except `/api/auth/login` require a `Bearer` token in the `Authorization` header.
- The frontend stores the JWT in `localStorage` and attaches it to every API request.
- The `token_required` decorator validates the token on each protected request.
- All SQL queries use parameterized placeholders (`%s`) to prevent SQL injection.

---

### Detailed: Database Schema

**File:** `database/database.sql`

```
admins
  id, username, password_hash, role, status, created_at

cameras
  id, camera_code (unique), camera_name, location, city,
  latitude, longitude, speed_limit, measurement_distance,
  camera_token_hash, status, created_at, updated_at

detection_runs
  id, camera_id (FK->cameras), video_source,
  started_at, ended_at, status

vehicles
  id, detection_run_id (FK->detection_runs), object_id,
  vehicle_type, first_seen, last_seen

plates
  id, vehicle_id (FK->vehicles), plate_number,
  confidence, image_path, detected_at

violations
  id, camera_id (FK->cameras), detection_run_id (FK->detection_runs),
  vehicle_id (FK->vehicles), plate_id (FK->plates, nullable),
  speed, speed_limit,
  excess_speed (GENERATED ALWAYS AS speed - speed_limit),
  evidence_path, violation_time, created_at
```

**Relationships:**
- A `camera` can have many `detection_runs`
- A `detection_run` produces many `vehicles` (tracked objects)
- A `vehicle` can have one `plate` (recognized text)
- A `violation` links a camera + vehicle + plate + evidence image
- `excess_speed` is a MySQL generated column: `speed - speed_limit`

---

### Detailed: REST API

All endpoints return JSON. Protected endpoints require `Authorization: Bearer <token>`.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | No | Login, returns JWT |
| GET | `/api/auth/me` | Yes | Get current user info |
| GET | `/api/cameras` | Yes | List all cameras |
| GET | `/api/cameras/:id` | Yes | Get one camera |
| POST | `/api/cameras` | Yes | Create camera |
| PUT | `/api/cameras/:id` | Yes | Update camera |
| DELETE | `/api/cameras/:id` | Yes | Delete camera |
| POST | `/api/cameras/:id/detect` | Yes | Start detection (background) |
| GET | `/api/violations` | Yes | List violations (filterable) |
| GET | `/api/violations/:id` | Yes | Get one violation |
| GET | `/api/violations/:id/image` | Yes | Get evidence JPEG |
| GET | `/api/violations/stats` | Yes | Quick stats |
| GET | `/api/reports` | Yes | Full report data |

**Violation query parameters:** `camera_id`, `plate` (partial match), `date_from`, `date_to`

**Reports response includes:**
- Summary: total cameras, active cameras, total violations, today's violations, highest speed, average speed
- `by_camera`: violation count per camera
- `by_date`: violations grouped by date
- `by_vehicle_type`: violations grouped by vehicle type
- `top_plates`: most frequently violating plates
- `recent_violations`: last 10 violations with full details

---

### Detailed: Frontend Pages

| Page | Purpose |
|------|---------|
| `login.html` | Admin login form. Stores JWT on success. |
| `dashboard.html` | Stats cards (total cameras, active, total violations, today, highest speed) + recent violations table |
| `cameras.html` | Camera list with name, location, speed limit, status. Buttons: Detect, Activate/Deactivate, Delete |
| `add-camera.html` | Form to create camera: name, location, speed limit, measurement distance |
| `violations.html` | Full violation table with filters (camera, plate search, date range, status). Click "View" to see evidence image in modal |
| `reports.html` | Summary stats, bar charts (violations by camera, by vehicle type), top plates table, recent violations |

All pages share a sidebar navigation and require authentication (redirect to login if no token).

---

## Project Structure

```
.
├── .env                          # Environment variables (DB password, secret key)
├── plate.py                      # Original standalone plate recognition script (preserved)
├── speed.py                      # Original standalone speed detection script (preserved)
├── requirements.txt              # Python dependencies
│
├── models/
│   └── yolo11n.pt                # YOLOv11 nano model (~5.6MB)
│
├── videos/
│   └── trash.mp4                 # Test video
│
├── database/
│   └── database.sql              # Full schema definition
│
├── backend/
│   ├── __init__.py
│   ├── app.py                    # Flask application entry point
│   ├── config.py                 # Configuration (reads .env)
│   ├── database.py               # Database connection & query helpers
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py               # Login, JWT, token_required decorator
│   │   ├── cameras.py            # Camera CRUD + detect trigger
│   │   ├── violations.py         # Violation listing, filtering, images
│   │   └── reports.py            # Aggregated report data
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── yolo.py               # YOLO model singleton, detect_and_track()
│   │   ├── tracking.py           # Object tracking state (imported by detection)
│   │   ├── speed.py              # Line-crossing speed calculation
│   │   ├── plate.py              # Plate detection + EasyOCR multi-version OCR
│   │   ├── position.py           # Basic position/movement tracking
│   │   └── detection.py          # Main pipeline orchestrator
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── security.py           # bcrypt password hashing
│   │   └── helpers.py            # File utilities, evidence image generation
│   │
│   ├── uploads/                  # General upload storage
│   └── violations/               # Generated evidence JPEGs
│
├── frontend/
│   ├── index.html                # Redirects to login or dashboard
│   ├── login.html                # Login page
│   ├── css/
│   │   ├── style.css             # Global styles + layout
│   │   └── dashboard.css         # Dashboard + chart styles
│   ├── js/
│   │   ├── auth.js               # Token management, API helpers, auth guard
│   │   ├── login.js              # Login form handler
│   │   ├── dashboard.js          # Dashboard data loading
│   │   ├── cameras.js            # Camera list/add/detect/delete
│   │   ├── violations.js         # Violation list/filter/image modal
│   │   └── reports.js            # Reports + bar charts
│   └── pages/
│       ├── dashboard.html        # Dashboard with stats
│       ├── cameras.html          # Camera management
│       ├── add-camera.html       # Add new camera form
│       ├── violations.html       # Violation table with filters
│       └── reports.html          # Reports with charts
│
├── plate_debug/                  # Debug images from plate detection (preserved)
└── violations/                   # Root-level violation folder (from original scripts)
```

---

## Setup & Running

### Prerequisites
- Python 3.10+
- MySQL 8.0 running on localhost:3306
- A MySQL user with create/drop permissions

### 1. Create the Database

Run `database/database.sql` in MySQL, or let the application auto-create the default admin on first start. The database `speed_detection` must exist with the tables defined in the SQL file.

### 2. Configure Environment

Edit `.env` in the project root:
```
SECRET_KEY=your-secret-key-here
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=your-mysql-password
DATABASE_NAME=speed_detection
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Server

```bash
python -m backend.app
```

Opens at **http://localhost:5001**

### 5. Login

- Username: `admin`
- Password: `admin`

### 6. Add a Camera

Go to Cameras -> Add Camera. Set name, location, speed limit, and measurement distance.

### 7. Run Detection

Click "Detect" on a camera row. Enter the video path when prompted (e.g., `videos/trash.mp4`). The detection runs in the background. Check the server console for progress.

### 8. View Violations

After detection completes, go to Violations to see results with evidence images.

---

## Old Standalone Scripts (Preserved, Not Used by Backend)

| File | What It Does | Status |
|------|-------------|--------|
| `plate.py` | Standalone plate recognition with OpenCV GUI | Preserved as-is, not used by web app |
| `speed.py` | Standalone speed detection with MySQL insert | Preserved as-is, not used by web app |
| `backend/services/tracking.py` | Basic YOLO tracking demo | Preserved, not imported |
| `backend/services/yolo.py` (old) | Basic YOLO detection demo | Preserved, not imported |
| `backend/services/position.py` | Basic position tracking demo | Preserved, not imported |
| `backend/services/read.py` | OpenCV image reading experiment (commented out) | Preserved, not imported |
| `backend/database.py` (old) | One-shot MySQL insert test | Replaced with proper module |

These files contain the original working code that the backend services were built from. They are kept for reference but the web application uses the modular versions under `backend/services/`.

---

## Limitations

- **Speed calibration** is approximate. The line-crossing method gives average speed between two points. Accurate calibration requires precise knowledge of the real-world distance and camera angle.
- **Plate OCR** depends heavily on video resolution, angle, lighting, and plate visibility. The test video may not produce readable plates.
- **Detection runs in a background thread.** The API responds immediately with "started" -- progress is logged to the server console.
- **Single admin user.** Only one admin account is supported by default.
- **Port 5001** is used (5000 was occupied). Change in `backend/app.py` if needed.
- **No real-time streaming.** Detection processes pre-recorded video files, not live camera feeds (though the architecture supports adding live stream URLs as video sources).
