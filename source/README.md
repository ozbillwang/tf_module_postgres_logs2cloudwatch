# rds logs to cloudwatch

### Steps

* download state file from s3 bucket (default is <account_id>-rds-logs-state).
* if the s3 bucket is not exist, create it first, and enable versioning.
* if the state file is not exist in s3, ignore it.
* create log group (default is **rds_logs**) if not exist
* Create log stream (example: postgresqldev/error/postgresql.log.2018-10-18-22) if not exist
* INITIAL_DAYS_TO_INGEST is used to set the history logs to go through at first run
* check the state in state file and make sure only read new logs
* push the latest logs to cloudwatch
* adjust sequence token when push the logs to cloudwatch
* pick up time in rds logs, and save as cloudwatch log time for each log
* write state (**JSON**) to state file and upload to s3

```
{
  "lastReadDate": 1539922165072,
  "readState": {
    "error/postgresql.log.2018-10-19-03": "4:4038",
    "error/postgresql.log.2018-10-19-04": "5:672"
  }
}
```

### System environment variables are required:

* DB_INSTANCE_IDENTIFIER
* (optional) INITIAL_DAYS_TO_INGEST
* (optional) LOG_GROUP
* (optional) BUCKET_NAME
