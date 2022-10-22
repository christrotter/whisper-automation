FROM python:3.9.9-slim
WORKDIR /app

RUN python3 -m pip install boto3 setuptools

RUN mkdir /source && mkdir /dest
COPY . /app
CMD [ "python", "main.py" ]
