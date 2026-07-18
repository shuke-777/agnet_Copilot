from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.business import utc_now
from models.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_message: Mapped[str] = mapped_column(Text)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    steps: Mapped[list["AgentStep"]] = relationship(
        #是和run关联起来的。
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentStep.start_time",
    )
    created_ticket: Mapped["Ticket | None"] = relationship(
        "Ticket",
        back_populates="source_run",
        uselist=False,
        foreign_keys="Ticket.source_run_id",
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.run_id"), index=True)
    step_name: Mapped[str] = mapped_column(String(64), index=True)
    step_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    run: Mapped[AgentRun] = relationship(back_populates="steps")
