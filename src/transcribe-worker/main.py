
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
from queue import Empty
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

aws_config = Config(
    region_name = 'us-east-1',
    signature_version = 'v4',
    retries = {
        'max_attempts': 10,
        'mode': 'standard'
    }
)

endpoint_url = os.environ.get("LOCALSTACK_ENDPOINT")
logger.info("Here is our endpoint url: ")
logger.info(endpoint_url)
# boto/localstack need the creds defined/set, but doesn't care what they are
sqs = boto3.resource('sqs', endpoint_url=endpoint_url, config=aws_config, aws_access_key_id = "foo", aws_secret_access_key = "foo")
queue_name = "transcription_jobs.fifo"

source_directory    = os.environ.get('SOURCE_DIR', '../../source')
dest_directory      = os.environ.get('DEST_DIR', '../../dest')

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
    logger.info("Processing SQS messages...")

    # this should be a blocking call; do not want multiples of this running!
    def transcribeFile(model, file_path):
        logger.debug("Here is our file path: " + file_path)
        with open(file_path, "r"):
            logger.info("Transcribing: %s", file_path)
            result = model.transcribe(file_path)
            saveTranscription(result, dest_directory, file_path)
            logger.info("Transcribing completed for: " + file_path)

    def receiveMessages():
        while True:
            try:
                logger.info("Iterating over %s messages...", max_number)
                try:
                    messages = queue.receive_messages(
                        MessageAttributeNames=['All'],
                        MaxNumberOfMessages=max_number,
                        WaitTimeSeconds=wait_time
                    )
                except:
                    logger.exception("Couldn't receive messages from queue: %s", queue)
                if messages == []:
                    logger.info("No messages in the queue, we are done here.")
                    break
                for msg in messages:
                    logger.debug("Received message: %s: %s (receipt: %s)", msg.message_id, msg.body, msg.receipt_handle)
                    logger.info("Received message to process: %s", msg.body)
                    message_body = str(msg.body)
                    try:
                        transcription = transcribeFile(model, message_body)
                    except:
                        logger.exception("Transcription blew up!")
                    msg.delete() # putting the receipt_handle in here didn't work, needs to be deconstructed
            except ClientError as error:
                logger.exception("Couldn't receive messages from queue: %s", queue)
                raise error

    receiveMessages()

async def main(model):
    logger.info('-'*88)
    logger.info("Starting job processing...")
    logger.info('-'*88)
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    logger.info("Connection to SQS: " + queue.url)
    jobTask = asyncio.create_task(processJob(queue,1,15,model))
    async def pull_message():
        while not jobTask.done():
            await asyncio.sleep(0)
    await pull_message()

try:
    logger.info('-'*88)
    logger.info("Starting transcribe worker...")
    logger.info('-'*88)
    logger.info("Downloading Whisper model before starting loop - this takes some time... ")
    # todo: try/catch this
    model = whisper.load_model("base")
    logger.info("Whisper model downloaded, starting event loop.")
    loop = asyncio.new_event_loop()
    asyncio.run(main(model))
except KeyboardInterrupt:
    pass
finally:
    logger.info("Exiting...")
    loop.close()
