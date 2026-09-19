FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py start.sh ./
COPY static ./static
RUN mkdir -p /data /backups
ENV CRUCELINE_DB=/data/cruceline.db
ENV PORT=5055
EXPOSE 5055
CMD ["gunicorn", "--bind", "0.0.0.0:5055", "--workers", "2", "--threads", "4", "--timeout", "60", "server:app"]
