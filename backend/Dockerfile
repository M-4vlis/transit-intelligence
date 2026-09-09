FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY pyproject.toml ./
ARG INSTALL_TARGET="."
RUN pip install --no-cache-dir "${INSTALL_TARGET}"
COPY app ./app
COPY scripts ./scripts
RUN install -d -o 65532 -g 65532 /data/archive

USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
