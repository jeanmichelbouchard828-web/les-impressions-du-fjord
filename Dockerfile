FROM python:3.12-alpine
WORKDIR /app
COPY index.html .
CMD python -m http.server ${PORT:-8080} --bind 0.0.0.0
