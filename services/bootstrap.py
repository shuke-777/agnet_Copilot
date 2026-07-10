from datetime import datetime

from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import Logistics, Order
from models.database import Base, engine
from models.feishu_event import FeishuEvent


_TRACE_MODELS = (AgentRun, AgentStep)
_FEISHU_MODELS = (FeishuEvent,)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)


def seed_demo_data(db: Session) -> None:
    if db.get(Order, "ORD-1001") is not None:
        return

    db.add_all(
        [
            Order(
                order_id="ORD-1001",
                user_id="USER-001",
                product_name="无线蓝牙耳机",
                amount=199.0,
                status="shipped",
                paid_at=datetime(2026, 6, 20, 10, 30, 0),
                shipped_at=datetime(2026, 6, 21, 14, 0, 0),
                delivered_at=None,
                created_at=datetime(2026, 6, 20, 10, 20, 0),
            ),
            Logistics(
                logistics_id="LOG-1001",
                order_id="ORD-1001",
                carrier="顺丰速运",
                tracking_no="SF1001001001",
                status="stalled",
                last_event="物流超过 72 小时未更新，疑似运输异常。",
                last_event_time=datetime(2026, 6, 24, 9, 15, 0),
                is_abnormal=True,
                created_at=datetime(2026, 6, 21, 14, 5, 0),
                updated_at=datetime(2026, 6, 27, 9, 15, 0),
            ),
            Order(
                order_id="ORD-1002",
                user_id="USER-002",
                product_name="智能保温杯",
                amount=89.0,
                status="delivered",
                paid_at=datetime(2026, 6, 25, 11, 10, 0),
                shipped_at=datetime(2026, 6, 25, 18, 30, 0),
                delivered_at=datetime(2026, 6, 27, 16, 40, 0),
                created_at=datetime(2026, 6, 25, 11, 0, 0),
            ),
            Logistics(
                logistics_id="LOG-1002",
                order_id="ORD-1002",
                carrier="中通快递",
                tracking_no="ZTO1002002002",
                status="delivered",
                last_event="已签收，签收人：本人。",
                last_event_time=datetime(2026, 6, 27, 16, 40, 0),
                is_abnormal=False,
                created_at=datetime(2026, 6, 25, 18, 35, 0),
                updated_at=datetime(2026, 6, 27, 16, 40, 0),
            ),
        ]
    )
    db.commit()


def bootstrap_database() -> None:
    init_database()
    with Session(bind=engine) as db:
        seed_demo_data(db)
