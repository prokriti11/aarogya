# Runs on Render (free web service). Render sets $PORT; 7860 is the local default.
FROM python:3.11-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH EMBED_CACHE_DIR=/home/user/fastembed \
    OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
# Bake the embedding model into the image -> no download on cold start
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/home/user/fastembed')"
COPY --chown=user . .
EXPOSE 7860
# Single worker + 1 ONNX thread keeps memory inside the 512 MB free tier
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
