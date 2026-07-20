from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.database import get_db
from models.operation_log import OperationLog
from schemas.operation_log import OperationLogRead


router = APIRouter(prefix="/api/operation-logs", tags=["operation logs"])


@router.get("", response_model=list[OperationLogRead])
def list_operation_logs(
    operator: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    ticket_id: str | None = None,
    run_id: str | None = None,
    order_id: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[OperationLog]:
    statement = select(OperationLog)
    filters = {
        "operator": operator,
        "action": action,
        "target_type": target_type,
        "ticket_id": ticket_id,
        "run_id": run_id,
        "order_id": order_id,
        "status": status,
    }
    for field, value in filters.items():
        if value and value.strip():
            statement = statement.where(getattr(OperationLog, field) == value.strip())
    if start_time is not None:
        statement = statement.where(OperationLog.created_at >= start_time)
    if end_time is not None:
        statement = statement.where(OperationLog.created_at <= end_time)
    return list(db.scalars(statement.order_by(OperationLog.created_at.desc()).limit(limit)))
