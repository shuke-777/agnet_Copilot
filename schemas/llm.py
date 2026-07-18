from typing import Literal

from pydantic import BaseModel, Field


class IntentRecognitionResult(BaseModel):
    intent: Literal[
        "refund",
        "return",
        "freight",
        "shipping_timeliness",
        "exchange",
        "address_change",
        "cancel_order",
        "compensation",
        "logistics_delay",
        "logistics_query",
        "unknown",
    ]


class OrderExtractionResult(BaseModel):
    order_id: str | None = Field(default=None, pattern=r"^ORD-\d+$")


class QueryRewriteResult(BaseModel):
    rewritten_query: str = Field(min_length=1)


class ReplyGenerationResult(BaseModel):
    reply_draft: str = Field(min_length=1)
