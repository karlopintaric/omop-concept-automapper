FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv for faster package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with uv
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the application code
COPY . .

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create data directory for uploads
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Set entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command
CMD ["streamlit", "run", "src/frontend/main.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
