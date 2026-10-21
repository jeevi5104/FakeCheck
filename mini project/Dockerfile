FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
ENV TESSERACT_CMD=/usr/bin/tesseract

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
