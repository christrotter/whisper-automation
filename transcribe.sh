#!/bin/bash

echo "starting dockerized transcription"
DIR=/Users/christrotter/Dropbox/Chris/Music/voice_recordings

docker run --rm -it -v $DIR:/data whisper
# so this murders the system cpu..
# also, the above just runs the whisper container interactively...
# we want it to run with 2cpus, 4gb mem
# it needs to look at the list of unprocessed files table
# clean any marked attempting and older than 24h
# mark the file it picks as attempting
#        oorrrrr....just single-thread it and wait longer...multi-threading only has value for backlogs...
# copy next file into container
# run whisper against file, '--task transcribe --language English --model small.en --output temp_files/'
# take output files and place into output dir
# update unprocessed list
# pull next...
# if killed

#whisper /data/120101_001.MP3 --task transcribe  --language English --model small.en
