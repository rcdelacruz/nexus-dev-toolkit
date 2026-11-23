FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml
COPY . .
CMD ["gunicorn", "careslot.wsgi:application", "--bind", "0.0.0.0:8000"]
