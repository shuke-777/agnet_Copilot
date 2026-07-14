from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models.agent_trace import AgentRun, AgentStep
from models.business import Ticket
from models.database import get_db
from schemas.agent_trace import AgentRunRead, AgentStepRead
from services.demo_trace_service import create_demo_waterfall_run


router = APIRouter(prefix="/api", tags=["agent trace"])


def get_run_or_404(db: Session, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )
    return run


@router.get("/runs", response_model=list[AgentRunRead])
def list_agent_runs(q: str | None = None, db: Session = Depends(get_db)) -> list[AgentRun]:
    statement = select(AgentRun).options(selectinload(AgentRun.created_ticket))
    if q and q.strip():
        query = q.strip().upper()
        statement = statement.outerjoin(Ticket, Ticket.source_run_id == AgentRun.run_id).where(
            or_(
                AgentRun.run_id.ilike(f"%{query}%"),
                AgentRun.order_id.ilike(f"%{query}%"),
                Ticket.ticket_id.ilike(f"%{query}%"),
            )
        )
    return list(db.scalars(statement.order_by(AgentRun.created_at.desc())))


@router.post("/runs/demo-waterfall", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_demo_waterfall(db: Session = Depends(get_db)) -> AgentRun:
    return create_demo_waterfall_run(db)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .options(selectinload(AgentRun.created_ticket))
        .where(AgentRun.run_id == run_id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentStepRead])
def list_agent_steps(run_id: str, db: Session = Depends(get_db)) -> list[AgentStep]:
    get_run_or_404(db, run_id)
    return list(
        db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.start_time)
        )
    )
