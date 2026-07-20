import sys
from pathlib import Path

from fastapi import FastAPI
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.agent_trace import router as agent_trace_router
from api.admin import router as admin_router
from api.business import router as business_router
from api.copilot import router as copilot_router
from api.dashboard import router as dashboard_router
from api.feishu import router as feishu_router
from api.operation_logs import router as operation_logs_router
from services.bootstrap import bootstrap_database
from services.redis_service import RedisService


APP_NAME = "ecommerce-after-sales-copilot"
APP_VERSION = "0.1.0"


app = FastAPI(
    title="Ecommerce After-Sales Copilot",
    version=APP_VERSION,
    description="After-sales ticket Copilot for ecommerce customer service teams.",
)


bootstrap_database()
app.include_router(agent_trace_router)
app.include_router(admin_router)
app.include_router(business_router)
app.include_router(copilot_router)
app.include_router(dashboard_router)
app.include_router(feishu_router)
app.include_router(operation_logs_router)


@app.get("/health")
def health_check() -> dict[str, str | dict[str, str]]:
    redis_service = RedisService.from_environment()
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
        "redis": redis_service.status.as_dict(),
    }
if __name__ == '__main__':
    uvicorn.run('api.main:app', host='0.0.0.0', port=8001,reload=True)
