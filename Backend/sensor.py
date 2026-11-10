import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from gpiozero import MotionSensor
from gpiozero.exc import GPIODeviceError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Attendance, FaceSample, Lecturer, Session, Student

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

sensor_lock = threading.Lock()
pir = None
camera_lock = threading.Lock()
camera = None


def motion_detected():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Motion detected at {timestamp}")


def motion_stopped():
    print("No motion detected")


def connect_sensor():
    global pir
    with sensor_lock:
        if pir is not None:
            return
        pir = MotionSensor(4)
        pir.when_motion = motion_detected
        pir.when_no_motion = motion_stopped


def disconnect_sensor():
    global pir
    with sensor_lock:
        if pir is not None:
            pir.close()
            pir = None


def get_camera():
    global camera
    if Picamera2 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="picamera2 is not installed",
        )
    with camera_lock:
        if camera is None:
            camera = Picamera2()
            # Keep one camera instance shared by scan requests to avoid
            # repeatedly opening and reconfiguring the Raspberry Pi camera.
            camera.configure(camera.create_still_configuration(
                main={"size": (1280, 720), "format": "RGB888"}
            ))
            camera.start()
    return camera


def face_descriptor(image):
    cascade_paths = (
        Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"),
        Path("/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml"),
    )
    cascade_path = next((path for path in cascade_paths if path.is_file()), None)
    if cascade_path is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OpenCV Haar cascade data is missing. Install it with: "
                "sudo apt install opencv-data"
            ),
        )
    detector = cv2.CascadeClassifier(str(cascade_path))
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    if len(faces) == 0:
        return None
    # Use the largest detected face so background faces do not affect
    # attendance when several people appear in one frame.
    x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
    face = gray[y:y + height, x:x + width]
    face = cv2.resize(face, (128, 128))
    face = cv2.equalizeHist(face)
    return face.astype(np.float32) / 255.0


def face_distance(first, second):
    return float(np.mean(np.abs(first - second)))


class SensorAction(BaseModel):
    action: str


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


app = FastAPI(title="Classroom Arrival Monitor")
frontend_directory = Path(__file__).parent.parent / "FrontEnd"
session_duration = timedelta(hours=8)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
    )
    return password_hash.hex(), salt.hex()


def verify_password(password, stored_password):
    password_hash, salt = stored_password.split("$", 1)
    calculated_hash, _ = hash_password(password, bytes.fromhex(salt))
    return hmac.compare_digest(calculated_hash, password_hash)


def create_password_hash(password):
    password_hash, salt = hash_password(password)
    return f"{password_hash}${salt}"


async def require_session(
    session_token: str | None,
    database: AsyncSession,
):
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in",
        )

    session = await database.get(
        Session,
        hashlib.sha256(session_token.encode("utf-8")).hexdigest(),
    )
    if session is None or session.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired",
        )
    return session.lecturer_id


async def create_session(lecturer_id, database):
    token = secrets.token_urlsafe(32)
    database.add(
        Session(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            lecturer_id=lecturer_id,
            expires_at=datetime.utcnow() + session_duration,
        )
    )
    await database.commit()
    return token


@app.get("/", include_in_schema=False)
async def home(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    try:
        await require_session(session_token, database)
    except HTTPException:
        return RedirectResponse("/auth.html", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(frontend_directory / "index.html")


@app.get("/index.html", include_in_schema=False)
async def dashboard(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    await require_session(session_token, database)
    return FileResponse(frontend_directory / "index.html")


@app.post("/api/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    database: AsyncSession = Depends(get_db),
):
    lecturer = Lecturer(
        full_name=request.full_name.strip(),
        email=request.email.strip().lower(),
        password_hash=create_password_hash(request.password),
    )
    database.add(lecturer)
    try:
        await database.commit()
    except IntegrityError as error:
        await database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        ) from error
    return {"message": "Registration successful"}


@app.post("/api/login")
async def login(
    request: LoginRequest,
    response: Response,
    database: AsyncSession = Depends(get_db),
):
    result = await database.execute(
        select(Lecturer).where(Lecturer.email == request.email.strip().lower())
    )
    lecturer = result.scalar_one_or_none()
    if lecturer is None or not verify_password(request.password, lecturer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = await create_session(lecturer.id, database)
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=int(session_duration.total_seconds()),
    )
    return {"message": "Login successful"}


@app.post("/api/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    if session_token:
        session = await database.get(
            Session,
            hashlib.sha256(session_token.encode("utf-8")).hexdigest(),
        )
        if session:
            await database.delete(session)
            await database.commit()
    response.delete_cookie("session_token")


@app.get("/api/me")
async def current_lecturer(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    lecturer_id = await require_session(session_token, database)
    lecturer = await database.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lecturer account no longer exists",
        )
    return {"full_name": lecturer.full_name, "email": lecturer.email}


@app.get("/api/sensor")
async def get_sensor_status(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    await require_session(session_token, database)
    with sensor_lock:
        sensor = pir
        motion = sensor.motion_detected if sensor is not None else False

    return {
        "connected": sensor is not None,
        "motion": motion,
    }


@app.post("/api/sensor", status_code=status.HTTP_204_NO_CONTENT)
async def update_sensor(
    action_request: SensorAction,
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    await require_session(session_token, database)
    action = action_request.action

    try:
        if action == "connect":
            connect_sensor()
        elif action == "disconnect":
            disconnect_sensor()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be connect or disconnect",
            )
    except GPIODeviceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Sensor could not be {action}ed: {error}",
        ) from error


@app.post("/api/recognition/scan")
async def scan_for_student(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    await require_session(session_token, database)
    frame = get_camera().capture_array()
    current_face = face_descriptor(frame)
    if current_face is None:
        return {"recognized": False, "reason": "No face detected"}

    samples = (await database.execute(
        select(FaceSample, Student).join(
            Student,
            FaceSample.student_id == Student.id,
        )
    )).all()
    best_match = None
    best_distance = None
    for sample, student in samples:
        reference = cv2.imread(sample.image_path)
        if reference is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not read reference image: {sample.image_path}",
            )
        reference_face = face_descriptor(cv2.cvtColor(reference, cv2.COLOR_BGR2RGB))
        if reference_face is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No face found in reference image: {sample.image_path}",
            )
        distance = face_distance(current_face, reference_face)
        if best_distance is None or distance < best_distance:
            best_match = student
            best_distance = distance

    # The threshold rejects the closest candidate when the image difference
    # is still too large to be a reliable match.
    if best_match is None or best_distance > 0.22:
        return {"recognized": False, "reason": "Face not recognized"}

    today = datetime.utcnow().date().isoformat()
    attendance = Attendance(
        student_id=best_match.id,
        attendance_date=today,
    )
    database.add(attendance)
    try:
        await database.commit()
        already_present = False
    except IntegrityError:
        # The unique student/date constraint makes repeated scans harmless.
        await database.rollback()
        already_present = True

    return {
        "recognized": True,
        "student_id": best_match.student_id,
        "full_name": best_match.full_name,
        "already_present": already_present,
        "distance": round(best_distance, 4),
    }


@app.get("/api/attendance")
async def get_attendance(
    session_token: str | None = Cookie(default=None),
    database: AsyncSession = Depends(get_db),
):
    await require_session(session_token, database)
    today = datetime.utcnow().date().isoformat()
    rows = (await database.execute(
        select(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
        .where(Attendance.attendance_date == today)
        .order_by(Attendance.detected_at)
    )).all()
    return [
        {
            "student_id": student.student_id,
            "full_name": student.full_name,
            "detected_at": attendance.detected_at.isoformat(),
        }
        for attendance, student in rows
    ]


app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")


if __name__ == "__main__":
    try:
        connect_sensor()
    except GPIODeviceError as error:
        print(f"PIR sensor could not be initialized: {error}")
    else:
        print("PIR sensor is connected to GPIO 4 and ready.")

    print("Open http://<raspberry-pi-ip>:8000 to view the website.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
