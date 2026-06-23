# Backend Dockerfile - Python FastAPI with OpenCV and YOLO
# Using full bookworm image which includes libxcb, libglib etc.
# (avoids apt-get which fails due to Docker network/DNS issues)
FROM python:3.11-bookworm

WORKDIR /app

# Install system dependencies required by OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/backend/

# Create directories for runtime data
RUN mkdir -p /app/screenshots /app/data

# Set Python path so imports like `backend.app` resolve correctly
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run uvicorn pointing to the FastAPI app
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
