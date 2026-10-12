FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HOME=/tmp
WORKDIR /app
COPY backend/requirements.txt backend/requirements-lock.txt ./backend/
RUN pip install -r backend/requirements.txt -c backend/requirements-lock.txt \
    && useradd --uid 10001 --no-create-home appuser
COPY backend ./backend
COPY alembic.ini ./
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
