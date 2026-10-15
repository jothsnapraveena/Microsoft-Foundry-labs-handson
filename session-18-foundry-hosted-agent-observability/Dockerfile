FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY support.py assistant.py server.py ./
COPY assets ./assets
COPY data ./data
ENV PYTHONUNBUFFERED=1
EXPOSE 8088
CMD ["python", "server.py"]
