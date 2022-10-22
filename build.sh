#!/bin/bash
echo "Building and running..."

#export SOURCE_DIR="/Users/christrotter/Dropbox/Chris/Music/voice_recordings"
export SOURCE_DIR="/Users/christrotter/Desktop/source_recordings"
export DEST_DIR="/Users/christrotter/Desktop/processed_recordings"
export LOCALSTACK_ENDPOINT="http://0.0.0.0:4566"

QUEUE_NAME='transcription_jobs.fifo'

#################### Functions #####################
create_sqs_queue () {
    SQS_CREATE_RESULT=`awslocal sqs create-queue --queue-name $QUEUE_NAME --attributes file://create_queue.json`
    # {
    #     "QueueUrl": "http://localhost:4566/000000000000/transcription_jobs.fifo"
    # }
    QUEUE_URL=`echo $SQS_CREATE_RESULT | jq -r '.QueueUrl'`

    echo "$QUEUE_URL"
}
get_sqs_queue_url () {
    QUEUE_URL=`awslocal sqs get-queue-url --queue-name $QUEUE_NAME | jq -r '.QueueUrl'`
    echo $QUEUE_URL
}
test_sqs_queue () {
    echo "Putting test sqs message in the queue: $QUEUE_URL"
    awslocal sqs send-message --queue-url $QUEUE_URL --message-body "this is a test message" --message-group-id 1234567890
    echo "Checking sqs queue for our message..."
    RECEIVE_RESULT=`awslocal sqs receive-message --queue-url $QUEUE_URL --attribute-names All --message-attribute-names All --max-number-of-messages 1 --visibility-timeout 5 --receive-request-attempt-id 1234`
    RECEIPT_HANDLE=`echo $RECEIVE_RESULT | jq -r '.Messages[0].ReceiptHandle'`
    echo "Deleting the test message..."
    awslocal sqs delete-message --queue-url $QUEUE_URL --receipt-handle $RECEIPT_HANDLE
    echo "Done with localstack setup."
}
purge_sqs_messages () {
    echo "Purging the LocalStack SQS queue: $QUEUE_URL"
    awslocal sqs purge-queue --queue-url $QUEUE_URL
}
sqs_setup () {
    QUEUE_URL=`create_sqs_queue`
    echo "Here is our QUEUE_URL: $QUEUE_URL"
    test_sqs_queue
}
#################### End Functions #####################


if [[ $1 == "deploy" ]]; then
    echo "Refreshing LocalStack and populating SQS..."
    docker-compose down --remove-orphans
    docker-compose up --detach localstack
    sqs_setup
    docker-compose up --detach director
    docker-compose up --detach worker
fi
if [[ $1 == "build" ]]; then
    echo "Taking containers down for a build, bringing up LocalStack and SQS..."
    docker-compose down --remove-orphans
    docker-compose up --detach localstack
    sqs_setup

    echo "Building container image for the director..."
    cd src/transcribe-director
    docker build --network host -t transcribe-director:latest .
    cd ../..

    echo "Building container image for the worker..."
    cd src/transcribe-worker
    docker build --network host -t transcribe-worker:latest .
    cd ../..
fi
if [[ -z $1 ]]; then
    echo "Please specify an argument: build | deploy"
fi
