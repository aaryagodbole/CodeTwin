# CodeTwin Cloud API for self-hosting (compose.yaml). The hosted version runs the same code on Vercel.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY codetwin_cloud ./codetwin_cloud
COPY app.py ./
RUN pip install . "uvicorn>=0.29" && useradd --system --uid 10001 codetwin
USER codetwin
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
