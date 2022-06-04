FROM python:3.7-slim@sha256:f61a4c6266a902630324fc10814b1109b3f91ac86dfb25fa3fa77496e62f96f5

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY gitlab2sentry/ gitlab2sentry/
COPY run.py run.py
COPY g2s.yaml g2s.yaml

CMD ["python3", "run.py"]
