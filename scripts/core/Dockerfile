FROM python:3.11-slim

WORKDIR /app

COPY core /app/core
COPY shared /app/shared

ENV PYTHONPATH=/app
ENV PHASMIDA_STATE_FILE=/app/events/nmea_state.json

CMD ["python3", "-m", "core.phasmida_core"]
