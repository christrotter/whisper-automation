# for the main app
import asyncio
import os
import logging

# for whisper transcription
import whisper

# for SQS
import sys
import boto3
from botocore.exceptions import ClientError
import queue_wrapper

endpoint_url = "http://localhost:4566"
sqs = boto3.resource('sqs', endpoint_url=endpoint_url)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

logger.info("Downloading model ... ")
model = whisper.load_model("base")
logger.info("Model downloaded")

loop = asyncio.get_event_loop() # sets our infinite loop; not a great choice according to docs...

async def pullSQSMessage(queue, max_number, wait_time):
    logger.info("Pulling new SQS message.")
    """
    (from the aws docs)
    Receive a batch of messages in a single request from an SQS queue.

    :param queue: The queue from which to receive messages.
    :param max_number: The maximum number of messages to receive. The actual number
                       of messages received might be less.
    :param wait_time: The maximum time to wait (in seconds) before returning. When
                      this number is greater than zero, long polling is used. This
                      can result in reduced costs and fewer false empty responses.
    :return: The list of Message objects received. These each contain the body
             of the message and metadata and custom attributes.
    """
    try:
        messages = queue.receive_messages(
            MessageAttributeNames=['All'],
            MaxNumberOfMessages=max_number,
            WaitTimeSeconds=wait_time
        )
        for msg in messages:
            logger.info("Received message: %s: %s", msg.message_id, msg.body)
    except ClientError as error:
        logger.exception("Couldn't receive messages from queue: %s", queue)
        raise error
    else:
        return messages

async def proccessAudio():
    logger.info("Proccessing new audio")
    queue = queue_wrapper.get_queue('transcription_jobs')
    await pullSQSMessage(queue,1,15)
    with open("file.mp3") as file:
        logger.info("transcribing: " + file.name)
        result = model.transcribe(file.name)
        file.close()

async def main():
    logger.info("Starting transcription...")
    await proccessAudio()

try:
    print("(main) Starting main async task...")
    asyncio.ensure_future(main())
    print("(main) Entering infinite loop.")
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    print("(main) Closing infinite loop.")
    loop.close()
