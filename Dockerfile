FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    mcp \
    httpx \
    fastapi \
    uvicorn \
    pydantic \
    slowapi \
    python-dotenv

COPY . .

ENV PHOENIXD_URL=http://host.docker.internal:9740
ENV PHOENIXD_PASSWORD=""
ENV MCP_TRANSPORT=sse

EXPOSE 8017 8019

CMD ["python3", "argentum.py"]
