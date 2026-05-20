FROM python:3.11-slim

WORKDIR /app

# Install torch CPU-only first — the default torch wheel pulls in a CUDA build
# (~700 MB). The cpu index gives a ~200 MB build that's plenty for the embedding
# model (all-MiniLM-L6-v2) which runs comfortably on CPU.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.2.2

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model so containers start without a
# first-request stall. ~90 MB; cached under /root/.cache/huggingface.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
