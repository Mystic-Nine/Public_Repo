FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg/ffprobe: thumbnails, screenshots, splitting | mediainfo: /mediainfo | p7zip: zip/unzip
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg mediainfo p7zip-full libmagic1 git curl ca-certificates tzdata build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]
