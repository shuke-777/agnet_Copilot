from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    run_id: str
    step_name: str
    step_type: str
    status: str
    start_time: datetime
    end_time: datetime | None
    duration_ms: int | None
    input_summary: str | None
    output_summary: str | None
    error_message: str | None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    session_id: str
    user_id: str | None
    user_message: str
    intent: str | None
    status: str
    total_duration_ms: int | None
    created_at: datetime
    finished_at: datetime | None
