# Public-demo image (Hugging Face Spaces / any Docker host).
# Runs the CPU-only pattern path: no Node/ComfyUI, so 3D mesh generation and
# mesh measurement are skipped gracefully — patterns and profile previews work.

FROM python:3.12-slim

# HF Spaces runs containers with uid 1000; create a matching non-root user so
# runtime writes (uploads, SQLite DB) land in user-owned paths.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . /app

# HF Spaces routes traffic to app_port (7860, declared in README frontmatter).
ENV HOST=0.0.0.0 PORT=7860
EXPOSE 7860

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
