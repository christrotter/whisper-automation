#!/bin/bash
echo "Building and running..."

#source_directory    = "/Users/christrotter/Dropbox/Chris/Music/voice_recordings"
#source_directory    = "/Users/christrotter/Desktop/source_recordings"
#dest_directory      = "/Users/christrotter/Desktop/processed_recordings"
export SOURCE_DIR="/Users/christrotter/Desktop/source_recordings"
export DEST_DIR="/Users/christrotter/Desktop/processed_recordings"

docker-compose down
docker-compose up --detach
cd src/transcribe-director
docker build -t transcribe-director:latest .
cd ..
cd src/transcribe-worker
docker build -t transcribe-worker:latest .

#docker-compose up -f docker-compose.yml --detach
echo "doing localstack infra setup..."
SQS_RESULT=`awslocal sqs create-queue --queue-name "transcription_jobs.fifo" --attributes file://create_queue.json`
# {
#     "QueueUrl": "http://localhost:4566/000000000000/transcription_jobs.fifo"
# }
QUEUE_URL=`echo $SQS_RESULT | jq -r '.QueueUrl'`
echo "putting test sqs message in the queue..."
awslocal sqs send-message --queue-url $QUEUE_URL --message-body "this is a test message" --message-group-id 1234567890

echo "checking sqs queue for our message..."
RECEIVE_RESULT=`awslocal sqs receive-message --queue-url $QUEUE_URL --attribute-names All --message-attribute-names All --max-number-of-messages 1 --visibility-timeout 5 --receive-request-attempt-id 1234`
RECEIPT_HANDLE=`echo $RECEIVE_RESULT | jq -r '.Messages[0].ReceiptHandle'`

echo "deleting the test message..."
awslocal sqs delete-message --queue-url $QUEUE_URL --receipt-handle $RECEIPT_HANDLE
