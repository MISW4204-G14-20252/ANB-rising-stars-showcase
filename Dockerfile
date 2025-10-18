# First stage: base environment
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Second stage: development environment
FROM base AS development

WORKDIR /app

COPY ./src ./src
COPY ./worker ./worker

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
