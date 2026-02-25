FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv pip install --system --no-cache .

FROM python:3.12-slim AS runtime

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app
COPY src/ src/
COPY scripts/ scripts/

ENV PYTHONPATH=/app/src
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "polymarket_mcp"]
