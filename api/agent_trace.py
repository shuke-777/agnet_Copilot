from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.database import get_db
from schemas.agent_trace import AgentRunRead, AgentStepRead


router = APIRouter(prefix="/api", tags=["agent trace"])


def get_run_or_404(db: Session, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )
    return run


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> AgentRun:
    return get_run_or_404(db, run_id)


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
