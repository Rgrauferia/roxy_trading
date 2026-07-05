FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    ROXY_OUTPUT_DIR=/var/data/output \
    ROXY_ALERTS_DIR=/var/data/alerts \
    ROXY_DATA_DIR=/var/data/data \
    ROXY_DB_DIR=/var/data/db \
    ROXY_ENABLE_LIVE_BROKER_EXECUTION=0

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /app

RUN mkdir -p /var/data/output /var/data/alerts /var/data/data /var/data/db

EXPOSE 3000 8765

# Production default. Local development keeps hot reload in docker-compose/Makefile.
CMD ["sh", "scripts/render_start.sh"]
