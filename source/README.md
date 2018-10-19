# rds logs to cloudwatch

### Steps

* download state file from s3 bucket (default is <account_id>-rds-logs-state).
* If the s3 bucket is not exist, create it first, and enable versioning.
* If log group (default is **rds_logs**) is not exist, create it
* If log stream (default is DB identifier) is not exist, create it
* If the state file is not exist, ignore it.
* check the state in state file and make sure only read new logs
* push the latest logs to cloudwatch (default log group is /aws/rds_logs, log stream is the database identifier)
* adjust sequence token when push the logs to cloudwatch
* pick up the log's time as cloudwatch time
* write state (**JSON**) to state file and upload to s3

```
{
  "lastReadDate": 1539921203656,
  "readState": {
    "error/postgresql.log.2018-10-19-03": "4:3702",
    "error/postgresql.log.2018-10-19-04": "7:3702"
  }
}
```

### System environment variables are required:

* DB_INSTANCE_IDENTIFIER
* (optional) INITIAL_DAYS_TO_INGEST
* (optional) LOG_GROUP
* (optional) BUCKET_NAME
