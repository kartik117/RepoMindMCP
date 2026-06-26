FROM python:3.11-slim

WORKDIR /app

# gitpython wraps the git CLI, it doesn't reimplement it -- needs the real
# binary on PATH to actually clone anything.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "repomind.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
