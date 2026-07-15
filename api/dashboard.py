from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db
from schemas.dashboard import AgentPerformance, DashboardOverview, TicketStats
from services.dashboard_service import (
    get_agent_performance,
    get_dashboard_overview,
    get_ticket_stats,
)
from services.dashboard_cache_service import DashboardCache


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverview:
    return DashboardCache.from_environment().get_or_load_overview(lambda: get_dashboard_overview(db))


@router.get("/ticket-stats", response_model=TicketStats)
def dashboard_ticket_stats(db: Session = Depends(get_db)) -> TicketStats:
    return DashboardCache.from_environment().get_or_load_ticket_stats(lambda: get_ticket_stats(db))


@router.get("/agent-performance", response_model=AgentPerformance)
def dashboard_agent_performance(db: Session = Depends(get_db)) -> AgentPerformance:
    return DashboardCache.from_environment().get_or_load_agent_performance(lambda: get_agent_performance(db))
