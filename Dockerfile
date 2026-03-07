FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime libs required by opencv-python on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY config ./config
COPY src ./src
COPY yolov8n.pt ./yolov8n.pt

CMD ["python", "src/main.py"]
