# rds logs to cloudwatch

### Steps

* download state file from s3 bucket (<account_id>-rds-logs-state).
* If the s3 bucket is not exist, create it first, and enable versioning.
* If the state file is not exist, ignore it.
* check the state in state file and make sure only read new logs
* push the latest logs to cloudwatch (default log group is /aws/rds_logs, log stream is the database identifier)
* adjust sequence token when push the logs to cloudwatch
* write state to state file and upload to s3

# System environment variables are required:

* DB_INSTANCE_IDENTIFIER
* (optional) INITIAL_DAYS_TO_INGEST
* (optional) LOG_GROUP
* (optional) BUCKET_NAME
