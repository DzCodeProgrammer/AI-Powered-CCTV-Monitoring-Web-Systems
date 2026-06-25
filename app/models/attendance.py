from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    detection_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    camera_source: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
