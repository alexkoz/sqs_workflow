#!/usr/bin/env bash
export S3_BUCKET='aws-s3-bucket-name';
export ACCESS='aws-access-key';
export SECRET='aws-secret-key';
export REGION_NAME='aws-region-name';
export AWS_PROFILE='aws-profile';
export QUEUE_LINK='sqs-queue-link';
export SIMILARITY_SCRIPT='$(pwd)/aids/dummy_similarity.py';
export ROOM_BOX_SCRIPT='$(pwd)/aids/dummy_roombox.py';
export R_MATRIX_SCRIPT='$(pwd)/aids/dummy_rmatrix.py';
export ROTATE_SCRIPT='$(pwd)/aids/dummy_rmatrix.py';
export ROTATE_EXECUTABLE='$(pwd)/aids/dummy_rmatrix.py';
export DOOR_DETECTION_SCRIPT='$(pwd)/aids/dummy_dd.py';
export SIMILARITY_EXECUTABLE='/path-to-similarity-script-python-executable';
export ROOM_BOX_EXECUTABLE='/path-to-roombox-script-python-executable';
export R_MATRIX_EXECUTABLE='/path-to-rmatrix-script-python-executable';
export DOOR_DETECTION_EXECUTABLE='/path-to-dd-script-python-executable';
export INPUT_DIRECTORY='/path-to-prepare-for-processing-input-directory';
export OUTPUT_DIRECTORY='/path-to-prepare-for-processing-output-directory';
export SLACK_URL='slack-webhook-url';
export SLACK_ID='slack-id';
export GMAIL_USER='gmail-login'
export GMAIL_PASSW='gmail-password'
export GMAIL_TO='receiver-email-address'