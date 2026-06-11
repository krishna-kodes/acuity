# Build context is the backend/ directory.
FROM python:3.11-slim

WORKDIR /app

# gcc for any C-extension wheels that build from source.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# spaCy model used by the PII NER pass.
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

# Railway provides $PORT; default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
