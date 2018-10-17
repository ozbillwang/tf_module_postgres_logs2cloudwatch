# System environment variables are required:
#
# DB_INSTANCE_IDENTIFIER
# (optional) INITIAL_DAYS_TO_INGEST
# (optional) LOG_GROUP

from __future__ import print_function

import sys
import os
import time
import ast
import boto3

rds = boto3.client('rds')
logs = boto3.client('logs')


def manage_log_group(log_group, log_stream):
    """
    create log_group or log_stream if not exist
    """

    response = logs.describe_log_groups(logGroupNamePrefix=log_group)

    sum = 0
    for group in response['logGroups']:
        if log_group == group['logGroupName']:
            sum += 1

    if not sum:
        response = logs.create_log_group(logGroupName=log_group, )

    response = logs.describe_log_streams(
        logGroupName=log_group, logStreamNamePrefix=log_stream)

    sum = 0
    for stream in response['logStreams']:
        if log_stream == stream['logStreamName']:
            sequence_token = stream['uploadSequenceToken']
            sum += 1

    if not sum:
        response = logs.create_log_stream(
            logGroupName=log_group, logStreamName=log_stream)

    return sequence_token

def lambda_handler(event, context):
    """
    This function to export rds logs to cloudwatch reguarly
    """

    DEFAULT_INITIAL_DAYS_TO_INGEST = 1
    DEFAULT_LOG_GROUP = "/aws/lambda/rds_logs"

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
        LOG_STREAM = DB_INSTANCE_IDENTIFIER
    except KeyError:
        sys.exit(1)

    sequence_token = manage_log_group(LOG_GROUP, LOG_STREAM)

    try:
        f = open(DB_INSTANCE_IDENTIFIER + '_rds_log_state', 'r')
        lastReadDate = int(f.readline())
        readState = f.readline()
        f.close()
        readState = ast.literal_eval(readState)
    except IOError:
        lastReadDate = int(round(time.time() * 1000)) - (
            (1000 * 60 * 60 * 24) * int(INITIAL_DAYS_TO_INGEST))
        readState = {}

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
                    message = "[{}] {}".format(
                        logFile['LogFileName'], entry)
                    response = logs.put_log_events(
                        logGroupName=LOG_GROUP,
                        logStreamName=LOG_STREAM,
                        logEvents=[{
                            'timestamp': lastReadDate,
                            'message': message
                        }],
                        sequenceToken=sequence_token)
                    sequence_token = response['nextSequenceToken']

            readState[logFile['LogFileName']] = response['Marker']

    f = open(DB_INSTANCE_IDENTIFIER + '_rds_log_state', 'w')
    f.write(str(lastReadDate))
    f.write("\n")
    f.write(str(readState))
    f.close()
