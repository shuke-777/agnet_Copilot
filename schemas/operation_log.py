from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    operator: str
    operator_type: str
    action: str
    target_type: str
    target_id: str
    ticket_id: str | None
    run_id: str | None
    order_id: str | None
    source: str
    status: str
    summary: str
    before_data: str | None
    after_data: str | None
    extra_data: str | None
    created_at: datetime
