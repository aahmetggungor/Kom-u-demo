FROM node:24-alpine AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
ENV VITE_DEMO_PASSWORD_LOGIN=true
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY services services
COPY migrations migrations
COPY alembic.ini ./
COPY scripts/render_start.py scripts/render_start.py
COPY data/render.synthetic.jsonl data/render.synthetic.jsonl
COPY --from=web /web/dist /app/web
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home komsu
USER komsu
EXPOSE 10000
CMD ["python", "scripts/render_start.py"]
