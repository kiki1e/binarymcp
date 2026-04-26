FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn httpx

COPY bridge.py .

EXPOSE 5600

CMD ["uvicorn", "bridge:app", "--host", "0.0.0.0", "--port", "5600", "--log-level", "info"]
