FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY renalwatch ./renalwatch
RUN python -m renalwatch.train_demo && useradd --uid 10001 --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "renalwatch.api:app", "--host", "0.0.0.0", "--port", "8000"]
