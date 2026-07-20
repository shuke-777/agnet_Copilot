import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from models.operation_log import OperationLog


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _serialize_data(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)


def _log_file_path() -> Path:
    directory = Path(os.getenv("OPERATION_LOG_DIR", str(PROJECT_ROOT / "logs")))
    return directory / f"operation-{date.today().isoformat()}.jsonl"


def _append_jsonl(operation_log: OperationLog) -> None:
    record = {
        "log_id": operation_log.log_id,
        "operator": operation_log.operator,
        "operator_type": operation_log.operator_type,
        "action": operation_log.action,
        "target_type": operation_log.target_type,
        "target_id": operation_log.target_id,
        "ticket_id": operation_log.ticket_id,
        "run_id": operation_log.run_id,
        "order_id": operation_log.order_id,
        "source": operation_log.source,
        "status": operation_log.status,
        "summary": operation_log.summary,
        "before_data": operation_log.before_data,
        "after_data": operation_log.after_data,
        "extra_data": operation_log.extra_data,
        "created_at": operation_log.created_at.isoformat(),
    }
    try:
        path = _log_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("Unable to append operation audit log")


def record_operation_log(
    db: Session,
    *,
    operator: str,
    operator_type: str,
    action: str,
    target_type: str,
    target_id: str,
    source: str,
    status: str,
    summary: str,
    ticket_id: str | None = None,
    run_id: str | None = None,
    order_id: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> OperationLog:
    operation_log = OperationLog(
        log_id=f"OPL-{uuid4().hex[:8].upper()}",
        operator=operator,
        operator_type=operator_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ticket_id=ticket_id,
        run_id=run_id,
        order_id=order_id,
        source=source,
        status=status,
        summary=summary,
        before_data=_serialize_data(before_data),
        after_data=_serialize_data(after_data),
        extra_data=_serialize_data(extra_data),
    )
    db.add(operation_log)
    db.flush()
    _append_jsonl(operation_log)
    return operation_log
