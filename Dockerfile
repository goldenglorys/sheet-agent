FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=2.1.2\
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Set working directory
WORKDIR /app

# Copy project dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies - use --without-dev instead of --no-dev for Poetry 1.7.1
RUN poetry install --without dev --no-root

# Second stage for the runtime image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TMPDIR=/app/sandbox \
    MPLCONFIGDIR=/app/sandbox

# Create a non-root user and set up directories
RUN groupadd -r sheetagent && useradd -r -g sheetagent sheetagent && \
    mkdir -p /app/sandbox && chown -R sheetagent:sheetagent /app/sandbox

# Set working directory
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set proper ownership
RUN chown -R sheetagent:sheetagent /app

# Switch to non-root user
USER sheetagent

# Expose the port the app will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"] 