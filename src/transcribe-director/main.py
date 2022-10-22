

"""
    transcribe-director
    the director app is responsible for the job queue generation
    on startup it ensures the sqs queue is empty, then evaluates
    both input and output directories.
    the resulting evaluation is a job list.
    each message contains the following data
    - language
    - source filepath
    - dest filepath
    - timestamp?

    once the joblist is populated, the director goes into sleep mode,
    checking the input dir periodically.
"""

# for the main app
import asyncio
import logging
# for file activities
import os
from os import listdir
from os.path import isfile, join
from pathlib import Path
# for SQS
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
# it needs the creds defined, but doesn't care what they are
sqs             = boto3.resource('sqs', endpoint_url=endpoint_url, config=aws_config, aws_access_key_id = "foo", aws_secret_access_key = "foo")
queue_name      = "transcription_jobs.fifo"

#source_directory    = "/Users/christrotter/Dropbox/Chris/Music/voice_recordings"

source_directory    = os.environ.get('SOURCE_DIR', '../../source')
dest_directory      = os.environ.get('DEST_DIR', '../../dest')

# why are these the same? one is 'only mp3 files' the other is 'any file'
# so we'd need a param for adding the mp3 filter...but i'm not solid on what is actually needed
# so...not-dry for now...
# uhm...why do we care about the mp3 extension?  bc why create messages you can't process is why...
def getFilePathsToTranscribe():
    def getMP3FilePathList(path):
        file_list = [f for f in listdir(path) if isfile(join(path, f))]
        mp3_file_list = [file for file in file_list if file.endswith('.MP3')]
        return mp3_file_list
    def getFilePathList(path):
        file_list = [f for f in listdir(path) if isfile(join(path, f))]
        return file_list

    """
        the whole point of this is purely to compare naming...not full file+extension
        source: mp3
        dest: .txt, .srt, .vtt
        the NAME is the same, but extension changes.
        we know that the file has been transcribed because you'll see the trifecta of txt/srt/vtt files
        in the dest dir.
    """
    def getMP3FileNameList(mp3_file_list):
        mp3_filenames = []
        for file in mp3_file_list:
            filename = file.split('.')[0]
            mp3_filenames.append(filename)
        return mp3_filenames
    def getFileNameList(file_list):
        filenames = []
        for file in file_list:
            filename = file.split('.')[0]
            filenames.append(filename)
        return filenames

    source_files        = getMP3FilePathList(source_directory)
    dest_files          = getFilePathList(dest_directory)
    diff_files          = list(set(source_files) - set(dest_files))
    #logger.info(diff_files)

    source_filenames    = getMP3FileNameList(source_files)
    dest_filenames      = getFileNameList(dest_files)
    diff_filenames      = list(set(source_filenames) - set(dest_filenames)) # set handles uniqueness, e.g. cuz there's multiple transcription files here
    #logger.info(diff_filenames)

    # now we can take the filename diff and get all mp3 files matching from the source dir
    def getDiffedFiles(path, names):
        file_list = [f for f in listdir(path) if isfile(join(path, f))]
        diffed_files = []
        for file in file_list:
            if any(file.split('.')[0] == name for name in names):
                logger.debug("found a match: " + file)
                diffed_files.append(file)
        return diffed_files

    diffed_filenames = getDiffedFiles(source_directory, diff_filenames)
    return diffed_filenames

async def publish(queue, max_number, wait_time, diff_files):
    logger.debug("Pushing new SQS message.")

    async def publishMessages(file):
        while True:
            try:
                logger.debug("Publishing: " + file)
                msg_body = source_directory + "/" + file
                logger.debug("Here is our msg_body: " + msg_body)
                # MessageGroupId=1 ensures that messages get processed in order
                # this isn't a big deal in practice, but hey, order is nice.
                response = queue.send_message(
                    MessageBody=msg_body,
                    MessageGroupId="1",
                    MessageAttributes={}
                )
                return

            except ClientError as error:
                logger.exception("Couldn't publish messages to queue: %s", queue)
                raise error
    for file in diff_files:
        await publishMessages(file)

async def publishJobs(diff_files):
    logger.info("Let's create some jobs...")
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    logger.info(queue)
    logger.info("Creating task...")
    publishTask = asyncio.create_task(publish(queue,1,15,diff_files))
    async def publish_message():
        while not publishTask.done():
            logger.info("task processing...")
            await asyncio.sleep(0) # why is this here...and why zero
    await publish_message()

async def diffWatcher():
    #todo: diff watcher updates the diff list
    logger.info("We don't run this atm.")

try:
    logger.info('-'*88)
    logger.info("Starting the transcribe director app...this is a one-time run...re-run if you add new files.")
    logger.info('-'*88)
    #todo: test connections: to dirs, to sqs
    diff_list = getFilePathsToTranscribe()
    logger.info("Here is our diff list:")
    logger.info(diff_list)
    loop = asyncio.new_event_loop()
    asyncio.run(publishJobs(diff_list))
except KeyboardInterrupt:
    pass
finally:
    logger.info("Exiting...")
    loop.close()
