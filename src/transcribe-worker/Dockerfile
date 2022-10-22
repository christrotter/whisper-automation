FROM python:3.9.9-slim
WORKDIR /app

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get -qq update \
    && apt-get -qq install --no-install-recommends \
    ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install boto3 setuptools
RUN python3 -m pip install git+https://github.com/openai/whisper.git
RUN mkdir /source && mkdir /dest
COPY . /app
CMD [ "python", "main.py" ]
