FROM python:3.12-slim

WORKDIR /app

# Install system deps for crawl4ai / playwright
RUN apt-get update && apt-get install -y \
    curl wget gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers (for crawl4ai)
RUN playwright install chromium --with-deps || true

# Download TextBlob corpora
RUN python -m textblob.download_corpora || true

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
