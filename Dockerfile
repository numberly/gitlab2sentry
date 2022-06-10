FROM python:3.10-slim@sha256:ca78039cbd3772addb9179953bbf8fe71b50d4824b192e901d312720f5902b22

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY gitlab2sentry/ gitlab2sentry/
COPY run.py run.py
COPY g2s.yaml g2s.yaml

CMD ["python3", "run.py"]
