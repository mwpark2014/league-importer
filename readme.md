League of Legends Riot Games API Data Importer

This project aims to import data from the Riot Games API for data analysis. The objective is to have a large pool of
matches to analyze data from. In order to do so, we need to first import mostly static data representing champions,
items, summoner spells, and what they do and how the affect each other. This data gets updated once every patch update.
Then we need to grab a sample size of matches. In this project, only Diamond, Master, and GrandMaster divisions will be
considered in the data analysis. Consequently, a sample of summoners and their match histories in those divisions
will be grabbed.

All DB tables are created in .sql files in ./schema.

`import_static_data.py`, `import_summoner_data.py`, and `import_match_data.py` will fail if the schema is not created
before executing

Add in the ``--no-request` param if running `python import_static_data.py` directly in order to avoid making a request
to the Riot Games "data dragon" static data endpoint. This assumes that the user has already downloaded the most current
tarfile from the "data dragon" endpoint and has extracted the contents into the `data` directory.