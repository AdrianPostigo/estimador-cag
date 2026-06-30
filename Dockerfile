FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --upgrade pip && \
    pip install -e .

COPY . .

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]