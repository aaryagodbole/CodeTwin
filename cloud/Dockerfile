# CodeTwin Cloud API for self-hosting (compose.yaml). The hosted version runs the same code on Vercel.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Dependencies first, in their own layer (a code change does not reinstall them), read from pyproject.toml so the
# image, Vercel and CI install the same list with the same version caps.
COPY pyproject.toml README.md ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
      > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt "uvicorn>=0.29,<1" \
    && useradd --system --uid 10001 codetwin
COPY codetwin_cloud ./codetwin_cloud
COPY app.py ./
RUN pip install --no-deps .
USER codetwin
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --start-interval=2s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]
# --proxy-headers honours X-Forwarded-* only from FORWARDED_ALLOW_IPS (compose.yaml), which uvicorn reads itself.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
