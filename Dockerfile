FROM python:3.7-slim

WORKDIR /usr/src/app

COPY . .
RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]
