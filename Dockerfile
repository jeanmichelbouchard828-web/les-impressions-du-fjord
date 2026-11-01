FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
# PrusaSlicer is used ONLY to preview; Bambu Studio creates machine-ready 3MF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    prusa-slicer xvfb xauth libgl1 ca-certificates curl libgtk-3-0 \
    libfuse2 libnss3 libasound2 libgbm1 libdrm2 libxkbcommon0 libpulse0 \
    libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 && \
    rm -rf /var/lib/apt/lists/*
# Pinned official Bambu Studio 2.8.2.61 with X2D preset improvements.
# SHA-256 verifies the downloaded binary before extraction.
RUN mkdir -p /opt/bambu && \
    curl -fL --retry 3 --connect-timeout 25 \
    'https://github.com/bambulab/BambuStudio/releases/download/v02.08.02.61/BambuStudio_ubuntu22.04-v02.08.02.61-20260820225108.AppImage' \
    -o /tmp/BambuStudio.AppImage && \
    echo '69426a59682574591590f51c913d3889baa19252d1c8e9fcae2497eb0ed6bf92  /tmp/BambuStudio.AppImage' | sha256sum -c - && \
    chmod 755 /tmp/BambuStudio.AppImage && \
    cd /opt/bambu && ( /tmp/BambuStudio.AppImage --appimage-extract >/tmp/bambu-extract.log 2>&1 || ( cat /tmp/bambu-extract.log; exit 1 ) ) && \
    rm -f /tmp/BambuStudio.AppImage && \
    printf '#!/bin/sh\nexec xvfb-run -a /opt/bambu/squashfs-root/AppRun "$@"\n' >/usr/local/bin/bambu-studio && \
    chmod 755 /usr/local/bin/bambu-studio
ENV BAMBU_STUDIO_CLI=/usr/local/bin/bambu-studio
# Fail deployment rather than falsely report an unusable Bambu slicer.
RUN timeout 30 /usr/local/bin/bambu-studio --help >/tmp/bambu-help.log 2>&1 && \
    grep -q -- '--slice' /tmp/bambu-help.log && rm /tmp/bambu-help.log
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py atelier3d.html ./
COPY static ./static
ENV PORT=8080
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 160 app:app
