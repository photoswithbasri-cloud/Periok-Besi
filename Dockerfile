# Minimal production image for the Flask app, built for Cloud Run.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as a non-root user
RUN useradd --create-home appuser

# App code (backend/app.py serves frontend/ as static files — see backend/app.py)
COPY --chown=appuser:appuser backend/ backend/
COPY --chown=appuser:appuser frontend/ frontend/

USER appuser
WORKDIR /app/backend

# Cloud Run injects PORT at container start (and always sets it); this
# default only matters for `docker run` without an explicit -e PORT=...
ENV PORT=8080
EXPOSE 8080

# Shell form (not exec-form JSON array) so ${PORT} is expanded when the
# container starts, not baked in at build time — required since Cloud Run
# picks the actual port at runtime. Binds 0.0.0.0 so the container is
# reachable from outside itself, via gunicorn (a production WSGI server)
# rather than the Flask dev server used only for local development in
# backend/app.py's `if __name__ == "__main__"` block.
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 app:app
