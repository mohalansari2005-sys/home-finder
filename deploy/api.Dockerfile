FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Dependencies come from the pinned lock (regenerate with scripts/lock-backend.sh), so a deploy never silently
# picks up a new langchain/langgraph/fastapi release; the project itself is installed without resolving anything.
COPY backend/requirements-server.lock backend/pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-server.lock
COPY backend/homefinder ./homefinder
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
RUN pip install --no-cache-dir --no-deps .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn homefinder.server.app:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
