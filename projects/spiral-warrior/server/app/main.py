from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.routes.discovery import router as discovery_router
from app.routes.health import router as health_router
from app.routes.login import router as login_router
from app.routes.logic import router as logic_router
from app.routes.manifests import router as manifests_router
from app.routes.profile import router as profile_router

app = FastAPI(title='Spiral Warrior Local Server', version='0.1.0')
app.include_router(health_router)
app.include_router(manifests_router)
app.include_router(login_router)
app.include_router(profile_router)
app.include_router(discovery_router)
app.include_router(logic_router)

@app.api_route(
    '/{path:path}',
    methods=[
        'GET',
        'POST',
        'PUT',
        'PATCH',
        'DELETE',
        'HEAD',
        'OPTIONS',
        'TRACE',
        'CONNECT',
    ],
)
async def catch_all(path: str):
    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "path": "/" + path,
            "message": "unimplemented local route",
        },
    )
