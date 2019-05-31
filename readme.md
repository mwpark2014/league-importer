League of Legends Riot Games API Data Importer

This project aims to import match data from the Riot Games API for data analysis. The objective is to have a large
enough pool of matches to make statistically significant conclusions in a data analysis step afterwards. In order
to do so, we need to first import static data representing champions, items, summoner spells, and what they do and
how they affect each other. This data gets updated once every patch update. Then we need to grab a sample size of
matches. In this project, only Diamond, Master, and GrandMaster divisions will be considered in the data analysis.
Also, all matches will be after a set date to avoid having to import older outdated static data.

There are 3 major services involved in this process - AWS Lambda (integrated with AWS CloudWatch), AWS SQS,
and an AWS RDS MySQL instance.

The pipeline for the data import is as follows:
`import_historical_data.py` is uploaded into AWS Lambda. This Lambda instance is kicked off using a scheduler
from AWS CloudWatch. The instance kicks off every minute and grabs a match from AWS SQS (There needs to be at least
one match in SQS at the start). The match is parsed and translated to fit our DB schema before inserting rows into
the AWS RDS instance. Then the Lambda instances takes all the summoner accounts in the match and sends requests to
the Riot Games API for a list of matches filtered to specific critieria for each one. These matches are then sent to
AWS SQS to be processed eventually by a future Lambda event. 

All DB tables are created in .sql files in ./schema.

`import_static_data.py` and `import_historical_data.py` will fail if the schema is not created
before executing

Add in the `--no-request` param if running `python import_static_data.py` directly in order to avoid making a request
to the Riot Games "data dragon" static data endpoint. This assumes that the user has already downloaded the most current
tarfile from the "data dragon" endpoint and has extracted the contents into the `data` directory.

