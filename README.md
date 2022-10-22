# whisper-automation
Problem space:  You have a pile of voice recordings that you want transcribed - even mostly accurately - and doing it manually is painful.  With even a halfway good copy to start the task of 'doing something with the recordings' suddenly becomes easier.

One of my long-standing (years...) tasks is to convert all my recordings of bedtime stories to transcripts, for eventually maybe writing some children's books.  It's the audio equivalent to your digital photo folder that's impossibly huge and disorganized.

This uses [Whisper](https://github.com/openai/whisper), [Localstack](https://localstack.cloud/), and some Python applications I ~~copy-pasted~~ wrote.

## Essentially...
- Configure the source (my audio_recording.MP3 files) and destination (where the transcript files will go) directories
- Configure how many workers you want running (how baller is your rig?)
- Run `./build.sh build && ./build.sh deploy`
  - Subsequent runs: `./build.sh deploy`
  - Note that the worker container image is `3.57GB`, so it'll take a while.
- Magic happens, your CPU usage goes bananas.
- Go do other things.
- Transcript files (.txt, .vtt, .srt) start appearing in your destination dir

## Interrupted?
If you have to reboot or the process is interrupted in any way, all you lose is whatever progress has been made on the current set of files being transcribed.

- Run the deploy again (`./build.sh deploy`)
  - This brings the whole stack up with a refreshed 'files to be processed' list.
  - The workers pull from that list.
  - Transcription files magically show up.

\o/

# Architecture
<img src="images/transcriber-arch.png" width="600">

# Learnings
- Better docker stats: `docker stats --format "table {{.Name}}\t{{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"`
  - https://blog.dchidell.com/2018/01/29/better-docker-stats/
  - Which is still not great, cuz it's doing weird magic with stdout



# Other sources
- https://github.com/ahmetoner/whisper-asr-webservice
- https://sandstorm.de/de/blog/post/automate-podcast-transcripts-with-openai-whisper.html

# active issues
- ~~director can't find /source~~ can't have quotes on compose vol paths
- ~~worker can't talk to sqs~~ docker-compose networking was wonky, using links now
- ~~worker not putting files into output dir~~ i needed to add docker-compose volumes to the paths
- ~~build.sh always destroys localstack~~ had some fun with bash functions
- ~~worker build times are long~~ created a whisper_init script to pull the model into a stored cache
  - ~~The worker build takes a long time (~5m) due to having to download the language model on each RUN python main.py, if not already cached todo: can we cache that?~~
- sqs queue contents are a black box; no way to know what messages are in the queue, and what messages are locked for processing
  - need a 'sqs queue contents monitor' that doesn't actually pull messages...
  - suspect you can get metrics for this in real SQS/CloudWatch (msgs in queue, msgs w. lock)
- workers pulling same message : leaving this for now, only going to run one worker...this can be a future fix
  - it mostly works, had to un-async the 'act on the message' functions - the transcribe was blocking, but the message pull was not.
  - for some reason duplicates are happening;
    - one hour apart (processing time related, not specific timer...?...) (message visibility is two hours)
    - no actual output file issues
    - one took 30m to process, the other 61m
    - i think my minimal understanding of sqs messaging is the issue here...
    - message group id is static; in theory this means the messages need to be processed in order
    -
```
worker1
/source/120101_001.MP3
/source/120105_002.MP3 <-- dupe
/source/120108_001.MP3

2022-10-22 00:22:16,524 - __main__ - INFO - Received message to process: /source/120101_001.MP3
2022-10-22 00:22:16,528 - __main__ - INFO - Transcribing: /source/120101_001.MP3
2022-10-22 00:30:26,592 - __main__ - INFO - Transcribing completed for: /source/120101_001.MP3

2022-10-22 00:30:26,610 - __main__ - INFO - Received message to process: /source/120105_002.MP3
2022-10-22 00:30:26,611 - __main__ - INFO - Transcribing: /source/120105_002.MP3
2022-10-22 01:31:16,790 - __main__ - INFO - Transcribing completed for: /source/120105_002.MP3
why did this take 61 minutes...and received at 0030


2022-10-22 01:31:16,807 - __main__ - INFO - Received message to process: /source/120108_001.MP3
2022-10-22 01:31:16,809 - __main__ - INFO - Transcribing: /source/120108_001.MP3
2022-10-22 01:58:15,673 - __main__ - INFO - Transcribing completed for: /source/120108_001.MP3
2022-10-22 01:58:30,687 - __main__ - INFO - No messages in the queue, we are done here.

worker2
/source/120105_001.MP3
/source/120107_001.MP3
/source/120105_002.MP3 <-- dupe

2022-10-22 00:22:21,325 - __main__ - INFO - Received message to process: /source/120105_001.MP3
2022-10-22 00:22:21,328 - __main__ - INFO - Transcribing: /source/120105_001.MP3
2022-10-22 00:56:36,349 - __main__ - INFO - Transcribing completed for: /source/120105_001.MP3
2022-10-22 00:56:36,365 - __main__ - INFO - Received message to process: /source/120107_001.MP3
2022-10-22 00:56:36,367 - __main__ - INFO - Transcribing: /source/120107_001.MP3
2022-10-22 01:30:13,627 - __main__ - INFO - Transcribing completed for: /source/120107_001.MP3

2022-10-22 01:30:13,642 - __main__ - INFO - Received message to process: /source/120105_002.MP3
2022-10-22 01:30:13,643 - __main__ - INFO - Transcribing: /source/120105_002.MP3
2022-10-22 02:04:50,764 - __main__ - INFO - Transcribing completed for: /source/120105_002.MP3
but this only take 35 minutes..., and received an hour later?

2022-10-22 02:05:05,785 - __main__ - INFO - No messages in the queue, we are done here.
```
