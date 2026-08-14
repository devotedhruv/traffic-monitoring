FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 tesseract-ocr tesseract-ocr-eng tesseract-ocr-nep \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config config
COPY services services
COPY src src
COPY web web
COPY run_web.py .
COPY models models
# Versioned custom weights are Git-ignored but included when present in the local build context.
COPY ml/models ml/models

EXPOSE 8000
CMD ["python", "run_web.py"]
