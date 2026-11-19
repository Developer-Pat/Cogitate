FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN pip install --no-cache-dir pip setuptools wheel
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Expose port for flower
EXPOSE 5555

# Command will be overridden by docker-compose
CMD ["python", "main.py"]