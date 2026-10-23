FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# One image backs three services (app / collector / dashboard); the compose
# command selects which module uvicorn serves.
COPY app.py collector.py dashboard.py ./
EXPOSE 80
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
