from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Lecturer(Base):
    __tablename__ = "lecturers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class Session(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)


class FaceSample(Base):
    __tablename__ = "face_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("student_id", "attendance_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        nullable=False,
    )
    attendance_date: Mapped[str] = mapped_column(String(10), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )