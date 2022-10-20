
"""
    transcribe-worker
    the worker app is responsible only for transcription based on what
    the message data says.  it knows only 'take this file, transcribe it
    and then send the output files here'.

    the queue style is FIFO with exactly once processing.

    it claims the message
    validates the paths
    loads the file and transcribes it
    places the output files into the output dir
    validates those files
    deletes the message

    idle state is 'subscribed to topic and waiting for messages'

"""
# for the main app
import asyncio
import os
import logging
# for whisper transcription
import whisper
from whisperUtils import exact_div, format_timestamp, optional_int, optional_float, str2bool, write_txt, write_vtt, write_srt
import ffmpeg
from typing import BinaryIO, Union
import numpy as np
# for SQS
import sys
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

my_config = Config(
    region_name = 'us-east-1',
    signature_version = 'v4',
    retries = {
        'max_attempts': 10,
        'mode': 'standard'
    }
)

endpoint_url = "http://localhost:4566"
# boto/localstack need the creds defined/set, but doesn't care what they are
sqs = boto3.resource('sqs', endpoint_url=endpoint_url, config=my_config, aws_access_key_id = "foo", aws_secret_access_key = "foo")
queue_name = "transcription_jobs.fifo"

#source_directory    = "/Users/christrotter/Desktop/source_recordings"
#dest_directory      = "/Users/christrotter/Desktop/processed_recordings"
source_directory    = os.environ.get('SOURCE_DIR', './')
dest_directory      = os.environ.get('DEST_DIR', './')

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop() # sets our infinite loop; not a great choice according to docs...

"""
    One core limitation of SQS here is the dedupe/visibility timeout windows being fixed at 5 minutes.
    I think maybe mostly mitigated by the fact that we're going to be limited in our parallelism by
    hardware constraints - even running two workers might be a deal-breaker.
"""
def saveTranscription(result, output_dir, audio_path):
    audio_basename = os.path.basename(audio_path)
    # save TXT
    with open(os.path.join(output_dir, audio_basename + ".txt"), "w", encoding="utf-8") as txt:
        write_txt(result["segments"], file=txt)
    # save VTT
    with open(os.path.join(output_dir, audio_basename + ".vtt"), "w", encoding="utf-8") as vtt:
        write_vtt(result["segments"], file=vtt)
    # save SRT
    with open(os.path.join(output_dir, audio_basename + ".srt"), "w", encoding="utf-8") as srt:
        write_srt(result["segments"], file=srt)

async def processJob(queue, max_number, wait_time, model):
    logger.debug("Pulling new SQS message.")

    # this should be a blocking call; do not want multiples of this running!
    def transcribeFile(model, file_path):
        logger.debug("Here is our file path: " + file_path)
        with open(file_path, "r"):
            logger.debug("transcribing: ")
            logger.debug(file_path)
            result = model.transcribe(file_path, verbose="true")
            saveTranscription(result, dest_directory, file_path)
            logger.info("Completed transcription for: " + file_path)

    async def receiveMessages():
        while True:
            try:
                messages = queue.receive_messages(
                    MessageAttributeNames=['All'],
                    MaxNumberOfMessages=max_number,
                    WaitTimeSeconds=wait_time
                )
                for msg in messages:
                    logger.info("Received message: %s: %s (receipt: %s)", msg.message_id, msg.body, msg.receipt_handle)
                    message_body = str(msg.body)
                    logger.debug("stringified msg body: " + message_body)
                    transcription = transcribeFile(model, message_body)

                    msg.delete() # putting the receipt_handle in here didn't work, needs to be deconstructed
            except ClientError as error:
                logger.exception("Couldn't receive messages from queue: %s", queue)
                raise error
#            else:
#                return messages
    await receiveMessages()

async def proccessAudio(model):
    print('-'*88)
    logger.info("Starting job processing...")
    print('-'*88)
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    tsk = asyncio.create_task(processJob(queue,1,15,model))
    async def pull_message():
        while not tsk.done():
            await asyncio.sleep(500)
    await pull_message()

try:
    print('-'*88)
    print("Starting transcribe worker...")
    print('-'*88)
    logger.info("Downloading Whisper model before starting loop - this takes some time... ")
    # todo: try/catch this
    model = whisper.load_model("base")
    logger.info("Whisper model downloaded.")
    asyncio.ensure_future(proccessAudio(model))
    logger.debug("Entering infinite loop.")
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    logger.debug("Closing infinite loop.")
    loop.close()
