FROM python:3.11-slim

WORKDIR /opt/greenline

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/networth/requirements.txt /tmp/networth-requirements.txt
RUN pip install --no-cache-dir -r /tmp/networth-requirements.txt

COPY services/__init__.py /opt/greenline/services/__init__.py
COPY services/networth/__init__.py /opt/greenline/services/networth/__init__.py
COPY services/networth/app /opt/greenline/services/networth/app
COPY services/networth_history/__init__.py /opt/greenline/services/networth_history/__init__.py
COPY services/networth_history/app /opt/greenline/services/networth_history/app

EXPOSE 8003
ENV PYTHONPATH=/opt/greenline/services/networth:/opt/greenline
CMD ["uvicorn", "services.networth_history.app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "1"]
