import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    classes = relationship("ClassEntity", back_populates="program")


class Instructor(Base):
    __tablename__ = "instructors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    classes = relationship("ClassEntity", back_populates="instructor")


class ClassEntity(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
    status = Column(String(50), nullable=False)
    start_date = Column(String(10), nullable=False)  # Format: YYYY-MM-DD
    end_date = Column(String(10), nullable=False)    # Format: YYYY-MM-DD
    current_students = Column(Integer, default=0)
    max_students = Column(Integer, default=30)
    completed_sessions = Column(Integer, default=0)
    total_sessions = Column(Integer, default=20)

    program = relationship("Program", back_populates="classes")
    instructor = relationship("Instructor", back_populates="classes")
