from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class Order(Base):
    __tablename__ = "orders"
    #这里用2.x来定义key
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    logistics: Mapped["Logistics | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="order")


class Logistics(Base):
    __tablename__ = "logistics"

    logistics_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), unique=True)
    carrier: Mapped[str] = mapped_column(String(64))
    tracking_no: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    last_event: Mapped[str] = mapped_column(Text)
    last_event_time: Mapped[datetime] = mapped_column(DateTime)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    order: Mapped[Order] = relationship(back_populates="logistics")


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_type: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="todo", index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    source_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.run_id"), nullable=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    order: Mapped[Order] = relationship(back_populates="tickets")
    source_run: Mapped["AgentRun | None"] = relationship(
        "AgentRun",
        back_populates="created_ticket",
        foreign_keys=[source_run_id],
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketEvent.created_at",
    )
    feishu_events: Mapped[list["FeishuEvent"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="FeishuEvent.created_at",
    )

    @property
    def source_run_created_at(self) -> datetime | None:
        return self.source_run.created_at if self.source_run is not None else None


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    operator: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    ticket: Mapped[Ticket] = relationship(back_populates="events")
