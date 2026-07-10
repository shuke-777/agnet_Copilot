from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.business import utc_now
from models.database import Base


class FeishuEvent(Base):
    __tablename__ = "feishu_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    operator: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="processed", index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    ticket: Mapped["Ticket"] = relationship(back_populates="feishu_events")
