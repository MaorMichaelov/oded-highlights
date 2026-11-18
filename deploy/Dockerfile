# Render worker image (customer jobs). Build from the REPO ROOT:   docker build -f deploy/Dockerfile -t oded-render-worker .
# Contains: ffmpeg, python deps, the editing code (scripts/, config/styles, fonts, sfx). NO secrets, NO state/, NO YouTube credentials (those never go into an image).
# Speech-to-text models are not baked in by default (3 GB); they download on first use into the /models volume. Bake them with:  --build-arg PRELOAD_MODELS=1
FROM python:3.12-slim

ARG PRELOAD_MODELS=0
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models WORKER_WORK_DIR=/data/work WORKER_OUT_DIR=/data/out UPLOAD_DIR=/data/uploads INGEST_DIR=/data/ingest

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fontconfig ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 worker && mkdir -p /app /data/work /data/out /data/uploads /data/ingest /models && chown -R worker /app /data /models

WORKDIR /app
COPY deploy/requirements-worker.txt /app/deploy/requirements-worker.txt
RUN pip install -r /app/deploy/requirements-worker.txt

COPY scripts /app/scripts
COPY config /app/config
COPY assets/fonts /app/assets/fonts
COPY assets/sfx /app/assets/sfx
COPY assets/world_clips /app/assets/world_clips
COPY tests/synth.py /app/tests/synth.py
RUN mkdir -p /app/state && chown -R worker /app

USER worker
# optional: bake the two speech models (Hebrew + generic) so the first job does not download 3 GB
RUN if [ "$PRELOAD_MODELS" = "1" ]; then python3 -c "from faster_whisper import WhisperModel as W; W('ivrit-ai/whisper-large-v3-turbo-ct2', device='cpu', compute_type='int8'); W('deepdml/faster-whisper-large-v3-turbo-ct2', device='cpu', compute_type='int8')"; fi

HEALTHCHECK --interval=2m --timeout=10s CMD python3 -c "import sys; sys.path.insert(0,'/app/scripts'); import render_worker" || exit 1
STOPSIGNAL SIGTERM
ENTRYPOINT ["tini", "--"]
CMD ["python3", "-u", "scripts/render_worker.py"]
