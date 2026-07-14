from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from models.agent_trace import AgentRun, AgentStep
from models.business import Logistics, Order, Ticket
from models.database import Base, engine
from models.feishu_event import FeishuEvent


_TRACE_MODELS = (AgentRun, AgentStep)
_FEISHU_MODELS = (FeishuEvent,)


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
        "tickets": {"source_run_id": "VARCHAR(64)"},
        "agent_runs": {"order_id": "VARCHAR(64)"},
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
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_order_id ON agent_runs (order_id)"))
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
