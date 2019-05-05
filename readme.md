League of Legends Riot Games API Data Importer

Add in the ``--no-request` param if running `python import_static_data.py` directly in order to avoid making a request
to the Riot Games "data dragon" static data endpoint. This assumes that the user has already downloaded the most current
tarfile from the "data dragon" endpoint and has extracted the contents into the `data` directory.