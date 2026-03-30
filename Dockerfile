FROM node:20-bookworm AS frontend-build
WORKDIR /app
COPY web-admin/package*.json ./web-admin/
RUN npm --prefix web-admin ci
COPY web-admin ./web-admin
RUN npm --prefix web-admin run build

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip \
    && python -m pip install .

COPY .env.example ./.env.example
COPY docs ./docs
COPY --from=frontend-build /app/web-admin/dist ./web-admin/dist

EXPOSE 10010

CMD ["python", "-m", "bot.main"]
