FROM python:3.10-slim

WORKDIR /app

COPY shared /shared
RUN pip install -e /shared

COPY webui /app/webui
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt fastapi uvicorn jinja2 httpx

EXPOSE 8001

CMD ["python", "-m", "webui.main"]