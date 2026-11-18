# CodeTwin Cloud API for self-hosting (compose.yaml). The hosted version runs the same code on Vercel.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Dependencies first, in their own layer, so a code change does not reinstall them. Major versions are capped so
# `docker compose up --build` after `git pull` cannot pull in a breaking release.
RUN pip install "fastapi>=0.115,<1" "psycopg[binary]>=3.2,<4" "pyjwt[crypto]>=2.8,<3" "pydantic<3" "uvicorn>=0.29,<1" \
    && useradd --system --uid 10001 codetwin
COPY pyproject.toml README.md ./
COPY codetwin_cloud ./codetwin_cloud
COPY app.py ./
RUN pip install --no-deps .
USER codetwin
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --start-interval=2s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]
# --proxy-headers honours X-Forwarded-* only from FORWARDED_ALLOW_IPS (compose.yaml), which uvicorn reads itself.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
