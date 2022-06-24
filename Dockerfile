FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

USER appuser
COPY gitlab2sentry/ gitlab2sentry/
COPY run.py run.py
COPY g2s.yaml g2s.yaml

CMD ["python3", "run.py"]
