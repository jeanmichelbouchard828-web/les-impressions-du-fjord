FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
# Debian 12 packages provide a real PrusaSlicer engine and virtual display.
RUN apt-get update && apt-get install -y --no-install-recommends \
    prusa-slicer xvfb xauth libgl1 ca-certificates && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py private_fjord.py real_slicer.py quote_estimator.py atelier3d.html ./
COPY static ./static
# Max slicing time: 115 seconds. Give Gunicorn enough time; limit concurrent jobs.
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 160 app:app
