# Run AWS Lambda function on local machine

## Python version

This lambda function is written by python 3, because it used some new features after v3.3

## Usage

* install [python-lambda-local](https://github.com/HDE/python-lambda-local)

```
pip install python-lambda-local
```

* create event test data

```
{
  "region": "ap-southeast-2"
}
```

* test locally

```
export DB_INSTANCE_IDENTIFIER="postgresqldev"
export INITIAL_DAYS_TO_INGEST=1
export LOG_GROUP="rds_logs"
python-lambda-local -l lib/ -f lambda_handler -t 300 ../source/main.py event.json
```
