from db_config import config
from db_config import DB_TYPE
import json
import mysql.connector
import requests
import sys
import tarfile
import traceback
from typing import Callable, Dict, Tuple

DATA_DRAGON_URL_HTTP = 'https://ddragon.leagueoflegends.com/cdn/dragontail-%s.tgz'
LOCAL_FILENAME = 'data/data_dragon.tgz'
CHAMPION_JSON_PATH = 'data/%s/data/en_US/champion.json'
ITEM_JSON_PATH = 'data/%s/data/en_US/item.json'
SUMMONER_JSON_PATH = 'data/%s/data/en_US/summoner.json'
CHUNK_SIZE = 8192

def initialize_static_tables():
    print('Initializing static data tables...')
    global patch_version
    patch_version = get_patch_manual()
    if '--no-request' not in sys.argv:
        success = get_data_dragon_tarfile(patch_version)  # Load file. File will be accessible at LOCAL_FILENAME
        if not success or not tarfile.is_tarfile(LOCAL_FILENAME):
            print('No tables were initialized. Exiting...')
            return
        with tarfile.open(LOCAL_FILENAME) as tar:
            print('Extracting data from tarfile...')
            tar.extractall(path='./data')
    data = {}
    data['champion_json'] = read_json_file(CHAMPION_JSON_PATH % patch_version)
    data['item_json'] = read_json_file(ITEM_JSON_PATH % patch_version)
    data['summoner_json'] = read_json_file(SUMMONER_JSON_PATH % patch_version)
    insert_data_into_db(data)
    print('Operations finished. Exiting...')


# TODO: Implement this
def update_static_tables():
    print('Updating static data tables...')
    return None


def get_patch_manual():
    return input('Please enter desired patch version in X.Y.Z format.\n X=season, Y=major version, Z=minor version\n')


# Return True if successful. False if not.
def get_data_dragon_tarfile(patch_version):
    url = DATA_DRAGON_URL_HTTP % patch_version
    print('Retrieving tar file from Riot Games API: %s...' % url)
    try:
        with requests.get(url, timeout=(3, None), stream=True) as response:
            response.raise_for_status()
            total_length = float(response.headers.get('content-length'))
            with open(LOCAL_FILENAME, "wb") as file:
                # Iterate over chunks
                length_written = 0
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk: # filter out keep-alive new chunks
                        file.write(chunk)
                        length_written += len(chunk)
                        # If we have a content-length header, show progress bar
                        if total_length is not None and length_written % (CHUNK_SIZE * 8) == 0:
                            sys.stdout.write("\r%d%%" % int(length_written / total_length * 100))
                            sys.stdout.flush()
        print()
        return True

    except Exception as err:
        print('Exception encountered when retrieving Riot Data Dragon tar file: ', str(err))
        traceback.print_tb(err.__traceback__)
        return False


def read_json_file(path):
    try:
        print('Parsing json file: %s' % path)
        with open(path, encoding="utf8") as file:
            return json.load(file)['data']
    except Exception as err:
        print('Exception encountered when reading extracted json files: ', str(err))
        traceback.print_tb(err.__traceback__)
        return None


def insert_data_into_db(json_dicts: Dict):
    print('Opening connection to %s database...' % DB_TYPE)
    connection = mysql.connector.connect(**config)
    insert_rows(connection, json_dicts['champion_json'], get_champion_strategy, get_champion_values)
    insert_rows(connection, json_dicts['item_json'], get_item_strategy, get_item_values)
    insert_rows(connection, json_dicts['summoner_json'], get_summoner_strategy, get_summoner_values)
    connection.close()
    print('Import finished. Closing connection...')


def insert_rows(connection, data: Dict, insert_strategy: Callable[[None], str], insert_values: Callable[[Dict], Tuple]):
    cursor = connection.cursor()
    for (key, value) in data.items():
        try:
            cursor.execute(insert_strategy(), insert_values(key, value))
            connection.commit()
        except mysql.connector.Error as err:
            print('Exception encountered when reading extracted json files: ', str(err))
            traceback.print_tb(err.__traceback__)
    cursor.close()


def get_champion_strategy():
    print('Inserting row into champions table...')
    return ("INSERT IGNORE INTO champions "
            "(champion_id, patch_ver, name, title, blurb, info_attack, info_defense, info_magic, info_difficulty,"
            "resource_type, stat_hp, stat_hpperlevel, stat_mp, stat_mpperlevel, stat_movespeed, stat_armor,"
            "stat_armorperlevel, stat_spellblock, stat_spellblockperlevel, stat_attackrange, stat_hpregen,"
            "stat_hpregenperlevel, stat_mpregen, stat_mpregenperlevel, stat_crit, stat_critperlevel, stat_attackdamage,"
            "stat_attackdamageperlevel, stat_attackspeedperlevel, stat_attackspeed, is_active ) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s)")


def get_champion_values(key: str, value: Dict):
    return (value.get('key'),
            patch_version,
            value.get('name'),
            value.get('title'),
            value.get('blurb'),
            value.get('info', {}).get('attack'),
            value.get('info', {}).get('defense'),
            value.get('info', {}).get('magic'),
            value.get('info', {}).get('difficulty'),
            value.get('partype'),
            value.get('stats', {}).get('hp'),
            value.get('stats', {}).get('hpperlevel'),
            value.get('stats', {}).get('mp'),
            value.get('stats', {}).get('mpperlevel'),
            value.get('stats', {}).get('movespeed'),
            value.get('stats', {}).get('armor'),
            value.get('stats', {}).get('armorperlevel'),
            value.get('stats', {}).get('spellblock'),
            value.get('stats', {}).get('spellblockperlevel'),
            value.get('stats', {}).get('attackrange'),
            value.get('stats', {}).get('hpregen'),
            value.get('stats', {}).get('hpregenperlevel'),
            value.get('stats', {}).get('mpregen'),
            value.get('stats', {}).get('mpregenperlevel'),
            value.get('stats', {}).get('crit'),
            value.get('stats', {}).get('critperlevel'),
            value.get('stats', {}).get('attackdamage'),
            value.get('stats', {}).get('attackdamageperlevel'),
            value.get('stats', {}).get('attackspeedperlevel'),
            value.get('stats', {}).get('attackspeed'), True)


def get_item_strategy():
    print('Inserting row into items table...')
    return ("INSERT IGNORE INTO items "
            "(item_id, name, description, gold_base, gold_total, purchaseable, active_in_srmap, depth,"
            "patch_ver, is_active) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")


def get_item_values(key: str, value: Dict):
    return (key,
            value.get('name'),
            value.get('plaintext'),
            value.get('gold', {}).get('base'),
            value.get('gold', {}).get('total'),
            value.get('gold', {}).get('purchasable'),
            # map_id = 11 is summoner's rift
            bool(value.get('maps', {}).get('11')),
            value.get('depth'),
            patch_version,
            True)


def get_summoner_strategy():
    print('Inserting row into summoner_spells table...')
    return ("INSERT IGNORE INTO summoner_spells "
            "(ss_id, name, description, cooldown, patch_ver, is_active) "
            "VALUES (%s, %s, %s, %s, %s, %s)")


def get_summoner_values(key: str, value: Dict):
    return (value.get('key'),
            value.get('name'),
            value.get('description'),
            value.get('cooldown')[0],
            patch_version,
            True)


if __name__ == '__main__':
    initialize_static_tables()
