FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY pii_guard/ ./pii_guard/
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install ".[ml]"

COPY gunicorn.conf.py ./
COPY config/ ./config/
COPY data/ ./data/

ARG NER_MODEL=LLAIMlegal/ru-legal-ner
ENV HF_HOME=/app/models
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('$NER_MODEL', allow_patterns=['*.json', '*.safetensors', '*.txt'])"
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN useradd --system app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "pii_guard.main:app"]