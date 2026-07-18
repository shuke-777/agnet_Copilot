from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.agent_trace import AgentRun, AgentStep
from models.business import Logistics, Order, SessionTicketBinding, Ticket, TicketEvent
from models.database import Base, SessionLocal, engine
from models.feishu_event import FeishuEvent
from services.bootstrap import init_database, seed_demo_data


def reset_demo_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    init_database()
    with SessionLocal() as db:
        seed_demo_data(db)


def summarize_demo_database() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "orders": db.query(Order).count(),
            "logistics": db.query(Logistics).count(),
            "tickets": db.query(Ticket).count(),
            "agent_runs": db.query(AgentRun).count(),
            "agent_steps": db.query(AgentStep).count(),
            "ticket_events": db.query(TicketEvent).count(),
            "feishu_events": db.query(FeishuEvent).count(),
            "session_ticket_bindings": db.query(SessionTicketBinding).count(),
        }


def main() -> None:
    reset_demo_database()
    summary = summarize_demo_database()
    print("Demo database reset complete:")
    for table_name, count in summary.items():
        print(f"- {table_name}: {count}")


if __name__ == "__main__":
    main()
