# VIVENTIUM START
# File: telegram-bot.Dockerfile
# Purpose: Container image for Viventium Telegram bridge.
# VIVENTIUM END
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY TelegramVivBot/pyproject.toml /tmp/pyproject.toml
RUN python -c "import pathlib, tomllib; data=tomllib.loads(pathlib.Path('/tmp/pyproject.toml').read_text()); deps=data.get('project', {}).get('dependencies', []); pathlib.Path('/tmp/requirements.txt').write_text('\\n'.join(deps))"
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY TelegramVivBot /app/TelegramVivBot

WORKDIR /app/TelegramVivBot

CMD ["python", "bot.py"]
