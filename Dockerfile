FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python3 -c "from routers.update import router_public; print('update OK')"
RUN python3 -c "from routers.notify import router_public; print('notify OK')"
RUN python3 -c "from routers.refund import router_public; print('refund OK')"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]