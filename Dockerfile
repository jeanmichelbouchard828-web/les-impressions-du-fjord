FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
# PrusaSlicer is used ONLY to preview; Bambu Studio creates machine-ready 3MF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    prusa-slicer xvfb xauth libgl1 ca-certificates curl libgtk-3-0 \
    libfuse2 libnss3 libasound2 libgbm1 libdrm2 libxkbcommon0 libpulse0 \
    libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libwebkit2gtk-4.1-0 && \
    rm -rf /var/lib/apt/lists/*
# Prevent a live site with an AppImage that cannot load its required WebKit GTK library.
# Debian Bookworm libwebkit2gtk-4.1-0 provides libwebkit2gtk-4.1.so.0.
RUN ldconfig -p | grep -F 'libwebkit2gtk-4.1.so.0'
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
# Locate the exact X2D stock presets bundled in this pinned Bambu AppImage.
# The main X2D JSON references essential separate machine_start_gcode templates.
RUN machine="$(find /opt/bambu/squashfs-root -type f \
    -path '*/profiles/BBL/machine/Bambu Lab X2D 0.4 nozzle.json' -print -quit)" && \
    test -n "$machine" && \
    dirname "$(dirname "$machine")" > /opt/bambu/bbl-stock-profiles-path
ENV BAMBU_STUDIO_CLI=/usr/local/bin/bambu-studio
# Fail deployment rather than falsely report an unusable Bambu slicer.
RUN ( timeout 30 /usr/local/bin/bambu-studio --help >/tmp/bambu-help.log 2>&1 && \
      grep -q -- '--slice' /tmp/bambu-help.log ) || ( cat /tmp/bambu-help.log; exit 1 ); \
    rm -f /tmp/bambu-help.log
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py atelier3d.html ./
# Fail the build if the X2D machine G-code or PETG factory profile cannot be
# expanded. An inherited generic start script is unsafe for a real X2D/AMS.
RUN python -c 'from bambu_stock_profiles import original_preset; \
for_category = ("Imprimante","Impression","Filament"); \
for_id = ("stock:machine:x2d04","stock:process:020","stock:filament:PETG"); \
results = [original_preset(cat, key) for cat, key in zip(for_category, for_id)]; \
assert "M620" in results[0]["machine_start_gcode"]; \
print("Bambu original X2D machine/process/PETG ready")'
COPY static ./static
ENV PORT=8080
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 160 app:app
