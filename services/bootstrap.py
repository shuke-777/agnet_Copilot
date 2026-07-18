from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import Logistics, Order, SessionTicketBinding, Ticket
from models.database import Base, engine
from models.feishu_event import FeishuEvent


_TRACE_MODELS = (AgentRun, AgentStep)
_FEISHU_MODELS = (FeishuEvent,)
_SESSION_BINDING_MODELS = (SessionTicketBinding,)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_agent_step_columns()
    migrate_m8_6_columns()


def migrate_agent_step_columns() -> None:
    """Apply additive SQLite columns for existing local databases without deleting traces."""
    inspector = inspect(engine)
    if "agent_steps" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("agent_steps")}
    columns = {
        "llm_provider": "VARCHAR(64)",
        "llm_model": "VARCHAR(128)",
        "input_tokens": "INTEGER",
        "output_tokens": "INTEGER",
        "fallback_reason": "TEXT",
        "cache_hit": "BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE agent_steps ADD COLUMN {column_name} {column_type}"))


def migrate_m8_6_columns() -> None:
    """Add M8.6 trace links without recreating an existing SQLite database."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    additions = {
        "tickets": {
            "source_run_id": "VARCHAR(64)",
            "approval_required": "BOOLEAN NOT NULL DEFAULT 0",
            "approval_status": "VARCHAR(32) NOT NULL DEFAULT 'not_required'",
            "approval_reason": "TEXT",
            "approval_decided_by": "VARCHAR(64)",
            "approval_decided_at": "DATETIME",
        },
        "agent_runs": {
            "order_id": "VARCHAR(64)",
            "ticket_id": "VARCHAR(64)",
            "result_payload": "TEXT",
        },
    }
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            if table_name not in tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_source_run_id ON tickets (source_run_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_approval_required ON tickets (approval_required)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_approval_status ON tickets (approval_status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_order_id ON agent_runs (order_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_ticket_id ON agent_runs (ticket_id)"))
        # Historical ticket_create steps already contain the generated ticket ID.
        connection.execute(
            text(
                "UPDATE tickets SET source_run_id = ("
                "SELECT agent_steps.run_id FROM agent_steps "
                "WHERE agent_steps.step_name = 'ticket_create' "
                "AND agent_steps.output_summary = tickets.ticket_id "
                "ORDER BY agent_steps.start_time LIMIT 1"
                ") WHERE source_run_id IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE agent_runs SET ticket_id = ("
                "SELECT tickets.ticket_id FROM tickets "
                "WHERE tickets.source_run_id = agent_runs.run_id "
                "LIMIT 1"
                ") WHERE ticket_id IS NULL"
            )
        )


def seed_demo_data(db: Session) -> None:
    demo_orders = [
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
        Order(
            order_id="ORD-1003",
            user_id="USER-003",
            product_name="宠物自动喂食器",
            amount=329.0,
            status="shipped",
            paid_at=datetime(2026, 7, 1, 9, 20, 0),
            shipped_at=datetime(2026, 7, 1, 17, 45, 0),
            delivered_at=None,
            created_at=datetime(2026, 7, 1, 9, 10, 0),
        ),
        Order(
            order_id="ORD-1004",
            user_id="USER-004",
            product_name="人体工学升降桌",
            amount=1299.0,
            status="paid",
            paid_at=datetime(2026, 7, 2, 20, 5, 0),
            shipped_at=None,
            delivered_at=None,
            created_at=datetime(2026, 7, 2, 19, 55, 0),
        ),
        Order(
            order_id="ORD-1005",
            user_id="USER-005",
            product_name="夏季防晒衣",
            amount=159.0,
            status="delivered",
            paid_at=datetime(2026, 7, 3, 12, 0, 0),
            shipped_at=datetime(2026, 7, 3, 18, 0, 0),
            delivered_at=datetime(2026, 7, 5, 11, 35, 0),
            created_at=datetime(2026, 7, 3, 11, 50, 0),
        ),
        Order(
            order_id="ORD-1006",
            user_id="USER-006",
            product_name="旗舰款扫地机器人",
            amount=4599.0,
            status="shipped",
            paid_at=datetime(2026, 7, 4, 10, 25, 0),
            shipped_at=datetime(2026, 7, 4, 19, 30, 0),
            delivered_at=None,
            created_at=datetime(2026, 7, 4, 10, 15, 0),
        ),
        Order(
            order_id="ORD-1007",
            user_id="USER-007",
            product_name="手机钢化膜",
            amount=29.9,
            status="shipped",
            paid_at=datetime(2026, 7, 5, 8, 40, 0),
            shipped_at=datetime(2026, 7, 5, 16, 10, 0),
            delivered_at=None,
            created_at=datetime(2026, 7, 5, 8, 30, 0),
        ),
        Order(
            order_id="ORD-1008",
            user_id="USER-008",
            product_name="真皮通勤双肩包",
            amount=699.0,
            status="delivered",
            paid_at=datetime(2026, 7, 6, 14, 20, 0),
            shipped_at=datetime(2026, 7, 6, 20, 30, 0),
            delivered_at=datetime(2026, 7, 8, 15, 5, 0),
            created_at=datetime(2026, 7, 6, 14, 10, 0),
        ),
        Order(
            order_id="ORD-1009",
            user_id="USER-009",
            product_name="智能运动手表",
            amount=899.0,
            status="delivered",
            paid_at=datetime(2026, 7, 7, 9, 30, 0),
            shipped_at=datetime(2026, 7, 7, 18, 20, 0),
            delivered_at=datetime(2026, 7, 9, 10, 50, 0),
            created_at=datetime(2026, 7, 7, 9, 20, 0),
        ),
        Order(
            order_id="ORD-1010",
            user_id="USER-010",
            product_name="母婴恒温水壶",
            amount=239.0,
            status="shipped",
            paid_at=datetime(2026, 7, 8, 13, 0, 0),
            shipped_at=datetime(2026, 7, 8, 21, 0, 0),
            delivered_at=None,
            created_at=datetime(2026, 7, 8, 12, 50, 0),
        ),
        Order(
            order_id="ORD-1011",
            user_id="USER-011",
            product_name="儿童学习平板",
            amount=1199.0,
            status="paid",
            paid_at=datetime(2026, 7, 9, 22, 15, 0),
            shipped_at=None,
            delivered_at=None,
            created_at=datetime(2026, 7, 9, 22, 5, 0),
        ),
        Order(
            order_id="ORD-1012",
            user_id="USER-012",
            product_name="便携咖啡机",
            amount=429.0,
            status="shipped",
            paid_at=datetime(2026, 7, 10, 15, 30, 0),
            shipped_at=datetime(2026, 7, 10, 20, 40, 0),
            delivered_at=None,
            created_at=datetime(2026, 7, 10, 15, 20, 0),
        ),
    ]
    demo_logistics = [
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
        Logistics(
            logistics_id="LOG-1003",
            order_id="ORD-1003",
            carrier="圆通速递",
            tracking_no="YTO1003003003",
            status="stalled",
            last_event="干线运输到达华东分拨中心后 96 小时未更新。",
            last_event_time=datetime(2026, 7, 3, 8, 30, 0),
            is_abnormal=True,
            created_at=datetime(2026, 7, 1, 17, 50, 0),
            updated_at=datetime(2026, 7, 7, 8, 30, 0),
        ),
        Logistics(
            logistics_id="LOG-1004",
            order_id="ORD-1004",
            carrier="仓库待发货",
            tracking_no="PENDING1004",
            status="not_shipped",
            last_event="订单已付款，仓库尚未生成物流单号。",
            last_event_time=datetime(2026, 7, 2, 20, 5, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 2, 20, 5, 0),
            updated_at=datetime(2026, 7, 2, 20, 5, 0),
        ),
        Logistics(
            logistics_id="LOG-1005",
            order_id="ORD-1005",
            carrier="韵达快递",
            tracking_no="YD1005005005",
            status="delivered",
            last_event="门店代收点已签收，签收人：前台。",
            last_event_time=datetime(2026, 7, 5, 11, 35, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 3, 18, 5, 0),
            updated_at=datetime(2026, 7, 5, 11, 35, 0),
        ),
        Logistics(
            logistics_id="LOG-1006",
            order_id="ORD-1006",
            carrier="京东物流",
            tracking_no="JD1006006006",
            status="in_transit",
            last_event="包裹已离开华北转运中心，预计次日到达。",
            last_event_time=datetime(2026, 7, 5, 9, 10, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 4, 19, 35, 0),
            updated_at=datetime(2026, 7, 5, 9, 10, 0),
        ),
        Logistics(
            logistics_id="LOG-1007",
            order_id="ORD-1007",
            carrier="申通快递",
            tracking_no="STO1007007007",
            status="in_transit",
            last_event="快件已到达同城营业部，等待派送。",
            last_event_time=datetime(2026, 7, 6, 7, 20, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 5, 16, 15, 0),
            updated_at=datetime(2026, 7, 6, 7, 20, 0),
        ),
        Logistics(
            logistics_id="LOG-1008",
            order_id="ORD-1008",
            carrier="顺丰速运",
            tracking_no="SF1008008008",
            status="delivered",
            last_event="已签收，签收人：本人。",
            last_event_time=datetime(2026, 7, 8, 15, 5, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 6, 20, 35, 0),
            updated_at=datetime(2026, 7, 8, 15, 5, 0),
        ),
        Logistics(
            logistics_id="LOG-1009",
            order_id="ORD-1009",
            carrier="中通快递",
            tracking_no="ZTO1009009009",
            status="delivered",
            last_event="已签收，签收人：本人。",
            last_event_time=datetime(2026, 7, 9, 10, 50, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 7, 18, 25, 0),
            updated_at=datetime(2026, 7, 9, 10, 50, 0),
        ),
        Logistics(
            logistics_id="LOG-1010",
            order_id="ORD-1010",
            carrier="极兔速递",
            tracking_no="JT1010010010",
            status="in_transit",
            last_event="快件已离开发件城市，运输途中暂不支持直接改派。",
            last_event_time=datetime(2026, 7, 9, 6, 45, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 8, 21, 5, 0),
            updated_at=datetime(2026, 7, 9, 6, 45, 0),
        ),
        Logistics(
            logistics_id="LOG-1011",
            order_id="ORD-1011",
            carrier="仓库待发货",
            tracking_no="PENDING1011",
            status="not_shipped",
            last_event="订单已付款，尚未出库，可核实是否允许取消。",
            last_event_time=datetime(2026, 7, 9, 22, 15, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 9, 22, 15, 0),
            updated_at=datetime(2026, 7, 9, 22, 15, 0),
        ),
        Logistics(
            logistics_id="LOG-1012",
            order_id="ORD-1012",
            carrier="德邦快递",
            tracking_no="DB1012012012",
            status="in_transit",
            last_event="快件已到达目的城市分拨中心，预计 24 小时内派送。",
            last_event_time=datetime(2026, 7, 11, 8, 25, 0),
            is_abnormal=False,
            created_at=datetime(2026, 7, 10, 20, 45, 0),
            updated_at=datetime(2026, 7, 11, 8, 25, 0),
        ),
    ]

    for order in demo_orders:
        if db.get(Order, order.order_id) is None:
            db.add(order)
    for logistics in demo_logistics:
        if db.get(Logistics, logistics.logistics_id) is None:
            db.add(logistics)
    db.commit()


def bootstrap_database() -> None:
    init_database()
    with Session(bind=engine) as db:
        seed_demo_data(db)
