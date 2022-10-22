import logging
import os
import whisper

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

whisper_directory = os.environ.get('WHISPER_DIR', './whisper')

try:
    logger.info('-'*88)
    logger.info("Doing Whisper model init to reduce cache wait times...")
    logger.info('-'*88)
    logger.info("Downloading Whisper model...this takes some time... ")
    model = whisper.load_model("base", download_root=whisper_directory)
    logger.info("Whisper model downloaded to: /whisper")
except KeyboardInterrupt:
    pass
finally:
    logger.info("Exiting...")
