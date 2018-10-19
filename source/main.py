# System environment variables are required:
#
# DB_INSTANCE_IDENTIFIER
# (optional) INITIAL_DAYS_TO_INGEST
# (optional) LOG_GROUP
# (optional) BUCKET_NAME
#
# Notes:
# Codes are format with yapf,
# syntax and style check with flake8

from __future__ import print_function
from botocore.client import ClientError
from dateutil import parser
import sys
import os
import time
import boto3
import json

rds = boto3.client('rds')
logs = boto3.client('logs')
s3 = boto3.resource('s3')

sts = boto3.client('sts')
account_id = sts.get_caller_identity()["Account"]
region = boto3.session.Session().region_name


def download_s3_file(bucket_name, file_name):
    """
    download s3 file, if bucket is not exist, create it first.
    """

    bucket = s3.Bucket(bucket_name)

    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
    except ClientError:
        bucket.create(CreateBucketConfiguration={'LocationConstraint': region})

    s3.BucketVersioning(bucket_name).enable()

    try:
        bucket.download_file(file_name, file_name)
    except ClientError:
        print("The log state file does not exist.")


def upload_s3_file(bucket_name, file_name):
    """
    upload file to s3
    """
    bucket = s3.Bucket(bucket_name)
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
    except ClientError:
        bucket.create(CreateBucketConfiguration={'LocationConstraint': region})

    try:
        with open(file_name, 'rb') as data:
            bucket.upload_fileobj(data, file_name)
    except ClientError:
        print("The data can't be uploaded to s3.")


def manage_log_group(log_group):
    """
    create log_group if not exist
    """

    response = logs.describe_log_groups(logGroupNamePrefix=log_group)

    sum = 0
    for group in response['logGroups']:
        if log_group == group['logGroupName']:
            sum += 1

    if not sum:
        response = logs.create_log_group(logGroupName=log_group, )


def describe_log_streams(log_group, log_stream):
    """
    describe log streams
    """

    response = logs.describe_log_streams(
        logGroupName=log_group, logStreamNamePrefix=log_stream)

    return response


def manage_log_stream(log_group, log_stream, response):
    """
    create log_stream if not exist
    """

    sum = 0
    for stream in response['logStreams']:
        if log_stream == stream['logStreamName']:
            if 'uploadSequenceToken' in stream:
                sequence_token = stream['uploadSequenceToken']
            sum += 1

    if not sum:
        response = logs.create_log_stream(
            logGroupName=log_group, logStreamName=log_stream)

    try:
        sequence_token
        return sequence_token
    except NameError:
        return "None"


def lambda_handler(event, context):
    """
    This function to export rds logs to cloudwatch reguarly
    """

    DEFAULT_INITIAL_DAYS_TO_INGEST = 1
    DEFAULT_LOG_GROUP = "rds_logs"
    DEFAULT_BUCKET_NAME = "{}-rds-logs-state".format(account_id)

    # Start from 1 day ago if it hasn't been run yet
    try:
        os.environ['INITIAL_DAYS_TO_INGEST']
        INITIAL_DAYS_TO_INGEST = os.environ['INITIAL_DAYS_TO_INGEST']
    except KeyError:
        INITIAL_DAYS_TO_INGEST = DEFAULT_INITIAL_DAYS_TO_INGEST

    try:
        os.environ['LOG_GROUP']
        LOG_GROUP = os.environ['LOG_GROUP']
    except KeyError:
        LOG_GROUP = DEFAULT_LOG_GROUP

    try:
        os.environ['DB_INSTANCE_IDENTIFIER']
        DB_INSTANCE_IDENTIFIER = os.environ['DB_INSTANCE_IDENTIFIER']
    except KeyError:
        sys.exit(1)

    try:
        os.environ['BUCKET_NAME']
        BUCKET_NAME = os.environ['BUCKET_NAME']
    except KeyError:
        BUCKET_NAME = DEFAULT_BUCKET_NAME

    manage_log_group(LOG_GROUP)
    streams = describe_log_streams(LOG_GROUP, DB_INSTANCE_IDENTIFIER)

    FILE_NAME = "{}_rds_log_state".format(DB_INSTANCE_IDENTIFIER)
    download_s3_file(BUCKET_NAME, FILE_NAME)

    data = {}
    lastReadDate = int(round(time.time() * 1000)) - int(
        (1000 * 60 * 60 * 24) * float(INITIAL_DAYS_TO_INGEST))
    readState = {}

    try:
        with open(FILE_NAME) as f:
            data = json.load(f)
        f.close()
        try:
            lastReadDate = data['lastReadDate']
        except KeyError:
            pass
        try:
            readState = data['readState']
        except KeyError:
            pass
    except IOError:
        pass

    # Wait for the instance to be available
    #   -- need to possibly fix this or replace it with a custom waiter
    # client.get_waiter('db_instance_available').wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
    # Get a list of the logs that have been modified since last run
    dbLogs = rds.describe_db_log_files(
        DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
        FileLastWritten=lastReadDate,  # Base this off of last query
    )
    lastReadDate = int(round(time.time() * 1000))

    # Iterate through list of log files and print out the entries
    for logFile in dbLogs['DescribeDBLogFiles']:
        if logFile['LogFileName'] in readState:
            readMarker = readState[logFile['LogFileName']]
        else:
            readMarker = '0'

        LOG_STREAM = "{}/{}".format(DB_INSTANCE_IDENTIFIER,
                                    logFile['LogFileName'])
        sequence_token = manage_log_stream(LOG_GROUP, LOG_STREAM, streams)

        ext = ['xel', 'trc']  # Ignore binary data log files for MSSQL
        if not logFile['LogFileName'].endswith(tuple(ext)):
            # Also may need to fix this waiter
            # client.get_waiter('db_instance_available').wait(
            #     DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
            # )
            response = rds.download_db_log_file_portion(
                DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
                LogFileName=logFile['LogFileName'],
                Marker=readMarker,
            )
            if len(response['LogFileData']) > 0:
                logLines = response['LogFileData'].strip().splitlines()
                # LogFileData sends all entries as a single string.
                # Split it up into a list to be able to append text to start
                for entry in logLines:
                    date = parser.parse(':'.join(entry.split(":")[:3]))
                    timestamp = int(round(date.timestamp() * 1000))
                    if sequence_token == "None":
                        event_response = logs.put_log_events(
                            logGroupName=LOG_GROUP,
                            logStreamName=LOG_STREAM,
                            logEvents=[{
                                'timestamp': timestamp,
                                'message': entry
                            }])
                    else:
                        event_response = logs.put_log_events(
                            logGroupName=LOG_GROUP,
                            logStreamName=LOG_STREAM,
                            logEvents=[{
                                'timestamp': timestamp,
                                'message': entry
                            }],
                            sequenceToken=str(sequence_token))
                    sequence_token = event_response['nextSequenceToken']

            readState[logFile['LogFileName']] = response['Marker']

    data['lastReadDate'] = lastReadDate
    data['readState'] = readState

    with open(FILE_NAME, 'w') as f:
        json.dump(data, f)
    f.close()

    upload_s3_file(BUCKET_NAME, FILE_NAME)
