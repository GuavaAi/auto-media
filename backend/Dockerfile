FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/uploads

EXPOSE 8010

CMD ["bash", "-lc", "python scripts/wait_for_services.py && uvicorn app.main:app --host 0.0.0.0 --port 8010"]
