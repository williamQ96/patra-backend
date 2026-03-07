# Patra backend API. Image: plalelab/patra-backend:latest
# Build/push: ./scripts/build-push-backend.sh (from repo root)
FROM python:3.12-slim

WORKDIR /app

# Build context must be project root: docker build -f api_server/Dockerfile -t plalelab/patra-backend:latest .
COPY api_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_server/ ./api_server/

EXPOSE 8000

CMD ["uvicorn", "api_server.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
