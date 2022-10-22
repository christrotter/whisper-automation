# whisper-automation
*Problem space*:  You have a pile of voice recordings that you want transcribed - even mostly accurately - and doing it manually is painful.  With even a halfway good copy to start the task of 'doing something with the recordings' suddenly becomes easier.  So, what is our friction-reducer?

One of my long-standing (*many years*) tasks is to convert all my recordings of bedtime stories to transcripts, for eventually maybe writing some children's books.  It's the audio equivalent to your digital photo folder that's impossibly huge and disorganized and drives you immediately to procrastination in the form of la-la-la-la-I-can't-hear-you. <img src="images/awesome.png" width="20">

This uses [Whisper](https://github.com/openai/whisper), [Localstack](https://localstack.cloud/), and some Python applications I ~~copy-pasted~~ wrote.  You supply a source directory with your audio recordings (*coded for MP3, but can be anything*) and a destination directory to put transcriptions into.  On each running the stack a list of files to be processed is generated (*compare source files against completed transcriptions*), and the workers pull from this list - one at a time - until the list is exhausted.

I would say it's ~95% accurate - I was sufficiently impressed that I built this tooling.

## Getting started
1. Configure the source (*my audio_recording.MP3 files*) and destination (*where the transcript files will go*) directories
    - `docker-compose.yml -> volumes` (*note, for both director and worker services...not sure how to DRY this*)
2. Configure how many workers you want running (*how baller is your rig?*)
    - `docker-compose.yml -> deploy`
    - Suggest just doing one if you are uncertain.
3. Run `./build.sh build deploy`
    - Subsequent runs only need: `./build.sh deploy`
    - Note that the worker container image is `3.57GB` (*ffmpeg, openai dependencies, whisper model cache, etc*), so it'll take a while.
4. Magic happens, your CPU usage goes bananas.  Go do other things like sleep.
6. Check your progress: `./build.sh queue-stats` or `watch -n 15 ./build.sh queue-stats`
> There are 150 items in the queue, with 2 actively being processed.
7. Transcript files (*.txt, .vtt, .srt*) start appearing in your destination dir
8. \o/

## Interrupted?
If you have to reboot or the process is interrupted in any way, all you lose is whatever progress has been made on the current set of files being transcribed.

1. Run the deploy again (`./build.sh deploy`)
2. The whole stack comes up with a refreshed 'files to be processed' list.
3. The workers pull from that list.
4. Transcription files magically show up.
5. \o/

# Architecture
<img src="images/transcriber-arch.png" width="600">

## Performance
This absolutely can crush your CPU, so I broke the job processing down with horizontal scaling.  Just configure (in `docker-compose.yml`) how many worker replicas you want running, and how much CPU they each get.
> NOTE: The workers run at 'allofit' (*100%*) CPU during transcription.
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
This config absolutely hammers my MacBook Pro (*2.6 GHz 6-Core Intel Core i7*).

My unscientific testing results...
<table>
<tr>
<td> Worker cpu limit </td> <td> Worker count </td> <td> Time to transcribe </td>
</tr>
<tr>
<td> 1.5 </td>
<td> 3 </td>
<td> 60 minutes </td>
</tr>
<tr>
<td> 3 </td>
<td> 3 </td>
<td> 20 minutes </td>
</tr>
<tr>
<td> 4 </td>
<td> 1 </td>
<td> sub-5 minutes </td>
</tr>
<tr>
<td> 3 </td>
<td> 2 </td>
<td> sub-10 minutes </td>
</tr>
</table>

## SQS notes
I wanted to ensure that there were no duplicates created (*wasted CPU time*), so FIFO with content deduplication seemed the right path.

Key points are...
- FifoQueue: this configures the queue from default 'standard' to 'fifo'; going for 'exactly once' message processing
- ContentBasedDeduplication: with our config, it hashes the message body as a UID (*our director diff code ensures this is always going to be unique*)
- VisibilityTimeout: How long SQS prevents other consumers from picking the message up.  Set to max in case of ultra-poor performance.
- MessageRetentionPeriod: Drop message from queue after this many seconds.
- ReceiveMessageWaitTimeSeconds: Long polling, just for Jeff.

### create_queue.json
``` json
{
    "MessageRetentionPeriod": "43200",
    "FifoQueue": "true",
    "ContentBasedDeduplication": "true",
    "ReceiveMessageWaitTimeSeconds": "15",
    "VisibilityTimeout": "43200"
}
```

# Learnings
- Fixing bugs by making hidden information visible - seeing the SQS stats helped me identify that the visible timeout was too short
- Better docker stats: `docker stats --format "table {{.Name}}\t{{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"`
  - https://blog.dchidell.com/2018/01/29/better-docker-stats/
  - Which is still not great, cuz it's doing weird magic with stdout
- ~~SQS is a black box - have not found a way to 'see the queue'~~ `aws sqs get-queue-attributes`
- Sometimes you just need a thing to run and be done, as a tool
- docker-compose down nukes all your logs
- Not everything needs to be an API (*e.g. worker just pulling tasks*)
- Using a logger instead of print
- Bash functions are super handy, but not without limitations...
- ...so creating python code to do the model init, better than bash (*not even possible in bash?*)
  - i.e. a new hammer
- Using env vars with defaults
- Writing code for containers requires ensuring it works locally AND in the container
- Using the power of containers with stuff like static cache - having the model download happen in-build vs. on-run, saves a lot of time
- HTML in markdown
- The length of the file to transcribe plays an order-of-magnitude part in 'time to transcribe' it feels like

# Other sources I want to remember
## Whisper
- https://github.com/ahmetoner/whisper-asr-webservice
- https://sandstorm.de/de/blog/post/automate-podcast-transcripts-with-openai-whisper.html
## SQS
- https://tomgregory.com/3-surprising-facts-about-aws-sqs-fifo-queues/
- https://docs.aws.amazon.com/cli/latest/reference/sqs/index.html#cli-aws-sqs
- https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SetQueueAttributes.html
- https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
## Docker
- https://testdriven.io/blog/docker-best-practices/

# TODO: backlog of bugs and ideas
- ~~director can't find /source~~ can't have quotes on compose vol paths
- ~~worker can't talk to sqs~~ docker-compose networking was wonky, using links now
- ~~worker not putting files into output dir~~ i needed to add docker-compose volumes to the paths
- ~~build.sh always destroys localstack~~ had some fun with bash functions
- ~~worker build times are long~~ created a whisper_init script to pull the model into a stored cache
  - ~~The worker build takes a long time (~5m) due to having to download the language model on each RUN python main.py, if not already cached todo: can we cache that?~~
- ~~message queue returning messages to 'visible' after 30 minutes~~ (*this was the below 'dupe processing' bug*)
- add image cleanup to the build, versioning for tags
- can we get rid of the whisperUtils.py?
- add linting - hadolint, pylint
- the localstack/aws configuration is super janky...have to look into why
  - then, stop using root in the container
- moving worker from 'allofit' cpu to '1.5' dramatically slows the transcription process
  - need to experiment with this one...tried with '3'...my laptop cpu caught on fire
  - do some actual scientific testing of performance
  - 4cpu on 2 workers seems to do ok...
- ~~sqs queue contents are a black box; no way to know what messages are in the queue, and what messages are locked for processing~~
  - ~~need a 'sqs queue contents monitor' that doesn't actually pull messages...~~
  - ~~suspect you can get metrics for this in real SQS/CloudWatch (*msgs in queue, msgs w. lock*)~~
  - FIGURED IT OUT.  get-queue-attributes provides these metrics.  i added a cmd: `./build.sh queue-stats`
- ~~workers pulling same message : leaving this for now, only going to run one worker...this can be a future fix~~
  - ~~it mostly works, had to un-async the 'act on the message' functions - the transcribe was blocking, but the message pull was not.~~
  - ~~for some reason duplicates are happening;~~
    - ~~one hour apart (*processing time related, not specific timer...?...*) (*message visibility is two hours*)~~
    - ~~no actual output file issues~~
    - ~~one took 30m to process, the other 61m~~
    - ~~i think my minimal understanding of sqs messaging is the issue here...~~
    - ~~message group id is static; in theory this means the messages need to be processed in order~~
    - FIGURED IT OUT.  visibility timeout was 30m (*i.e. sqs made the messages available for re-consumption after 30m*) - but the processing time was greater than that.  maxed the value out.
