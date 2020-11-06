FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY gitlab2sentry/ gitlab2sentry/
COPY run.py run.py
COPY g2s.yaml g2s.yaml

CMD ["python3", "run.py"]
