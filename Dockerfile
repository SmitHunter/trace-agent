# Multi-stage image: Next.js UI + FastAPI agent.

FROM node:20-alpine AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV NEXT_PUBLIC_API_URL=/backend
ENV API_INTERNAL_URL=http://127.0.0.1:8742
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/ /app/server/
WORKDIR /app/server
RUN pip install --no-cache-dir .

COPY --from=web-builder /app/web/.next/standalone /app/web-standalone
COPY --from=web-builder /app/web/.next/static /app/web-standalone/.next/static
COPY --from=web-builder /app/web/public /app/web-standalone/public
COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app
EXPOSE 3847 8742

ENV DEMO_MODE=true
ENV API_PORT=8742
ENV WEB_PORT=3847
ENV API_INTERNAL_URL=http://127.0.0.1:8742
ENV NEXT_PUBLIC_API_URL=/backend
ENV PYTHONPATH=/app/server
ENV MCP_TRANSPORT=stdio

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8742/health || exit 1

CMD ["/app/start.sh"]
