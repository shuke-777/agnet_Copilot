from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    user_id: str
    product_name: str
    amount: float
    status: str
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime


class LogisticsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    logistics_id: str
    order_id: str
    carrier: str
    tracking_no: str
    status: str
    last_event: str
    last_event_time: datetime
    is_abnormal: bool
    created_at: datetime
    updated_at: datetime


class TicketEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    operator: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1)
    from_status: str | None = Field(default=None, max_length=32)
    to_status: str | None = Field(default=None, max_length=32)


class TicketEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    ticket_id: str
    event_type: str
    operator: str
    content: str
    from_status: str | None
    to_status: str | None
    created_at: datetime


class TicketCreate(BaseModel):
    ticket_type: str = Field(min_length=1, max_length=64)
    priority: str = Field(default="normal", min_length=1, max_length=32)
    user_id: str = Field(min_length=1, max_length=64)
    order_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1)
    suggested_action: str = Field(min_length=1)
    assigned_to: str | None = Field(default=None, max_length=64)
    created_by: str = Field(default="agent", min_length=1, max_length=64)


class TicketUpdate(BaseModel):
    ticket_type: str | None = Field(default=None, min_length=1, max_length=64)
    priority: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    summary: str | None = Field(default=None, min_length=1)
    suggested_action: str | None = Field(default=None, min_length=1)
    assigned_to: str | None = Field(default=None, max_length=64)


class TicketActionRequest(BaseModel):
    action: Literal["claim", "resolve", "reopen"]
    operator: str = Field(min_length=1, max_length=64)


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    ticket_type: str
    priority: str
    status: str
    user_id: str
    order_id: str
    summary: str
    suggested_action: str
    assigned_to: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    events: list[TicketEventRead] = []


class FeishuCallbackRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    ticket_id: str = Field(min_length=1, max_length=64)
    action: Literal["claim", "resolve", "reopen"]
    operator: str = Field(min_length=1, max_length=64)


class FeishuEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    ticket_id: str
    action: str
    operator: str
    from_status: str
    to_status: str
    status: str
    payload: str | None
    created_at: datetime
    processed_at: datetime


class FeishuCallbackResponse(BaseModel):
    ticket: TicketRead
    ticket_event: TicketEventRead
    feishu_event: FeishuEventRead
