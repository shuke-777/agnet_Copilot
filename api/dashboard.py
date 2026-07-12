from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db
from schemas.dashboard import AgentPerformance, DashboardOverview, TicketStats
from services.dashboard_service import (
    get_agent_performance,
    get_dashboard_overview,
    get_ticket_stats,
)


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverview:
    return get_dashboard_overview(db)


@router.get("/ticket-stats", response_model=TicketStats)
def dashboard_ticket_stats(db: Session = Depends(get_db)) -> TicketStats:
    return get_ticket_stats(db)


@router.get("/agent-performance", response_model=AgentPerformance)
def dashboard_agent_performance(db: Session = Depends(get_db)) -> AgentPerformance:
    return get_agent_performance(db)
