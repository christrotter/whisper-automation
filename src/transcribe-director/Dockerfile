FROM python:3.9.9-slim
WORKDIR /app

RUN python3 -m pip install boto3 setuptools

COPY . /app
RUN python main.py
