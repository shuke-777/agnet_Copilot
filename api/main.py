from fastapi import FastAPI

from api.agent_trace import router as agent_trace_router
from api.admin import router as admin_router
from api.business import router as business_router
from api.copilot import router as copilot_router
from services.bootstrap import bootstrap_database


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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }
