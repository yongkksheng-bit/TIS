FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
WORKDIR /app

# Install curl for healthcheck (not in base image)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Pre-download models at build time to keep container small
# (Models are cached at HF_HOME during build, runtime reuses the volume mount)
ENV HF_HOME=/app/data/huggingface_cache
ENV HF_HUB_DISABLE_SYMLINKS=1

# Run with uvicorn, bind to all interfaces for Docker networking
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
