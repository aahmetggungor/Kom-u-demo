FROM python:3.12-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir pip==26.2.1 && pip install --no-cache-dir -r requirements.lock
COPY services services
COPY migrations migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home komsu && pip uninstall -y pip
USER komsu
EXPOSE 8000
CMD ["uvicorn", "komsu.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
