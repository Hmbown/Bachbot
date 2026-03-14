# Stage 1: Build frontend
FROM node:22-slim AS frontend
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml README.md /app/
COPY bachbot /app/bachbot
COPY data/normalized/dcml_bach_chorales /app/data/normalized/dcml_bach_chorales
COPY data/derived/dcml_bach_chorales /app/data/derived/dcml_bach_chorales
COPY data/manifests /app/data/manifests
COPY examples /app/examples
COPY --from=frontend /web/dist /app/web/dist

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD sh -c "bachbot serve --host 0.0.0.0 --port ${PORT:-8000}"
