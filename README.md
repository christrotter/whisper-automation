# whisper-automation
Problem space:  You have a pile of voice recordings that you want transcribed - even mostly accurately - and doing it manually is painful.  With even a halfway good copy to start the task of 'doing something with the recordings' suddenly becomes easier.

One of my long-standing (years...) tasks is to convert all my recordings of bedtime stories to transcripts, for eventually maybe writing some children's books.  It's the audio equivalent to your digital photo folder that's impossibly huge and disorganized.

This uses [Whisper](https://github.com/openai/whisper), [Localstack](https://localstack.cloud/), and some Python applications I ~~copy-pasted~~ wrote.  You supply a source directory with your audio recordings (coded for MP3, but can be anything) and a destination directory to put transcriptions into.  On each running the stack a list of files to be processed is generated (compare source files against completed transcriptions), and the workers pull from this list - one at a time - until the list is exhausted.

## Performance {#performance}
This absolutely can crush your CPU, so I broke the job processing down with horizontal scaling.  Just configure (in `docker-compose.yml`) how many worker replicas you want running, and how much CPU they each get.
> NOTE: The workers run at 'allofit' (100%) CPU during transcription.
```
e.g. you want three workers with three cores each...
  worker:
    deploy:
      resources:
        limits:
          cpus: '3'
      mode: replicated
      replicas: 3
```
This config absolutely hammers my MacBook Pro (2.6 GHz 6-Core Intel Core i7).

## Getting started
1. Configure the source (my audio_recording.MP3 files) and destination (where the transcript files will go) directories
    - `docker-compose.yml -> volumes` (*note, for both director and worker services...not sure how to DRY this*)
2. Configure how many workers you want running (how baller is your rig?)
    - `docker-compose.yml -> deploy`
    - Suggest just doing one if you are uncertain.
3. Run `./build.sh build && ./build.sh deploy`
    - Subsequent runs only need: `./build.sh deploy`
    - Note that the worker container image is `3.57GB`, so it'll take a while.
4. Magic happens, your CPU usage goes bananas.
5. Go do other things like sleep.
6. Transcript files (.txt, .vtt, .srt) start appearing in your destination dir
7. \o/

## Interrupted?
If you have to reboot or the process is interrupted in any way, all you lose is whatever progress has been made on the current set of files being transcribed.

1. Run the deploy again (`./build.sh deploy`)
2. The whole stack comes up with a refreshed 'files to be processed' list.
3. The workers pull from that list.
4. Transcription files magically show up.
5. \o/

# Architecture
<img src="images/transcriber-arch.png" width="600">

## SQS notes
I wanted to ensure that there were no duplicates created (wasted CPU time), so FIFO with content deduplication seemed the right path.
- `create_queue.json` has details on the config


# Learnings
- Better docker stats: `docker stats --format "table {{.Name}}\t{{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"`
  - https://blog.dchidell.com/2018/01/29/better-docker-stats/
  - Which is still not great, cuz it's doing weird magic with stdout
- SQS is a black box - have not found a way to 'see the queue'
- Sometimes you just need a thing to run and be done, as a tool
- Not everything needs to be an API (e.g. worker)
- Using a logger instead of print
- Bash functions are super handy, but not without limitations...
- ...so creating python code to do the model init, better than bash (not even possible in bash?)
  - i.e. a new hammer
- Using env vars with defaults
- Writing code for containers requires ensuring it works locally AND in the container
- Using the power of containers with stuff like static cache - having the model download happen in-build vs. on-run, saves a lot of time

# Other sources I want to remember
## Whisper
- https://github.com/ahmetoner/whisper-asr-webservice
- https://sandstorm.de/de/blog/post/automate-podcast-transcripts-with-openai-whisper.html
## SQS
- https://tomgregory.com/3-surprising-facts-about-aws-sqs-fifo-queues/
- https://docs.aws.amazon.com/cli/latest/reference/sqs/index.html#cli-aws-sqs
## Docker
- https://testdriven.io/blog/docker-best-practices/

# TODO: active issues
- ~~director can't find /source~~ can't have quotes on compose vol paths
- ~~worker can't talk to sqs~~ docker-compose networking was wonky, using links now
- ~~worker not putting files into output dir~~ i needed to add docker-compose volumes to the paths
- ~~build.sh always destroys localstack~~ had some fun with bash functions
- ~~worker build times are long~~ created a whisper_init script to pull the model into a stored cache
  - ~~The worker build takes a long time (~5m) due to having to download the language model on each RUN python main.py, if not already cached todo: can we cache that?~~
- add image cleanup to the build, versioning for tags
- can we get rid of the whisperUtils.py?
- add linting - hadolint, pylint
- the localstack/aws configuration is super janky...have to look into why
  - then, stop using root in the container
- moving worker from 'allofit' cpu to '1.5' dramatically slows the transcription process
  - need to experiment with this one...tried with '3'...my laptop cpu caught on fire
- sqs queue contents are a black box; no way to know what messages are in the queue, and what messages are locked for processing
  - need a 'sqs queue contents monitor' that doesn't actually pull messages...
  - suspect you can get metrics for this in real SQS/CloudWatch (msgs in queue, msgs w. lock)
- workers pulling same message : ~~leaving this for now, only going to run one worker~~...this can be a future fix
  - it mostly works, had to un-async the 'act on the message' functions - the transcribe was blocking, but the message pull was not.
  - for some reason duplicates are happening;
    - one hour apart (processing time related, not specific timer...?...) (message visibility is two hours)
    - no actual output file issues
    - one took 30m to process, the other 61m
    - i think my minimal understanding of sqs messaging is the issue here...
    - message group id is static; in theory this means the messages need to be processed in order
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
