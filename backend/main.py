from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api.routes import router
from backend.api.portfolio import router as portfolio_router
from backend.api.saved_portfolios import router as saved_router
from backend.db import Database, SCHEMA_REVISION
from backend.config import Settings
from backend.quant.market_data import MarketDataError, MarketDataService, YahooProvider


def create_app(settings=None, provider=None):
    settings = settings or Settings.from_env()
    database = Database(settings.database_url.get_secret_value()) if settings.database_url else None

    @asynccontextmanager
    async def lifespan(application):
        yield
        if database is not None:
            database.dispose()

    application = FastAPI(title='MarketLens', version='0.5.0', lifespan=lifespan,
        description='Simulation-only financial analytics. Rates are decimal fractions.')
    application.state.database = database
    application.state.market_data = MarketDataService(
        provider if provider is not None else YahooProvider(settings.market_timeout_seconds),
        settings.cache_ttl_seconds, settings.cache_max_entries)
    if settings.cors_origins:
        application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
            allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type'])

    @application.exception_handler(StaleDataError)
    async def stale_write(request, exc):
        return JSONResponse(status_code=409, content={'detail': 'Portfolio changed in another session. Reload before saving.'})

    @application.exception_handler(SQLAlchemyError)
    async def storage_error(request, exc):
        # Never expose connection credentials or SQL containing user inputs.
        return JSONResponse(status_code=503, content={'detail': 'Portfolio storage is unavailable. Check database connectivity and migrations.'})

    @application.get('/ready', tags=['Health'])
    def readiness():
        if database is None:
            return JSONResponse(status_code=503, content={'status': 'not_ready', 'database': 'not_configured'})
        try:
            with database.engine.connect() as connection:
                revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
                connection.execute(text('SELECT id FROM saved_portfolios LIMIT 0'))
                if revision != SCHEMA_REVISION:
                    raise RuntimeError('migration mismatch')
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse(status_code=503, content={'status': 'not_ready', 'database': 'unavailable_or_unmigrated'})
        return {'status': 'ready', 'database': 'ok'}

    @application.exception_handler(MarketDataError)
    async def market_error(request, exc):
        headers = {'Retry-After': '60'} if exc.status == 503 else None
        return JSONResponse(status_code=exc.status,
            content={'detail': {'code': exc.code, 'message': exc.message}}, headers=headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo arbitrary request bodies, nonfinite inputs, or exception objects.
        errors = [{'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']}
                  for error in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    application.add_api_route('/', home, methods=['GET'])
    application.add_api_route('/health', health, methods=['GET'])
    application.include_router(router)
    application.include_router(portfolio_router)
    application.include_router(saved_router)
    return application

def home():
    return {"message": "Welcome to MarketLens!"}

def health():
    return {"status": "ok"}


app = create_app()
