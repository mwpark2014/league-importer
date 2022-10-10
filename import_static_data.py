from config import db_config, DB_TYPE
import json
import mysql.connector
import requests
import sys
import tarfile
import traceback
from typing import Callable, Dict, Sequence

# Import static data such as items, champions, and summoner spells

DATA_DRAGON_URL_HTTP = 'https://ddragon.leagueoflegends.com/cdn/dragontail-%s.tgz'
LOCAL_FILENAME = 'data/data_dragon.tgz'
CHAMPION_JSON_PATH = 'data/%s/data/en_US/champion.json'
ITEM_JSON_PATH = 'data/%s/data/en_US/item.json'
SUMMONER_JSON_PATH = 'data/%s/data/en_US/summoner.json'
CHUNK_SIZE = 8192

# insert statements
CHAMPIONS_INSERT_STMT = (
    "INSERT IGNORE INTO champions "
    "(champion_id, patch_ver, name, title, blurb, info_attack, info_defense, info_magic, info_difficulty,"
    "resource_type, stat_hp, stat_hpperlevel, stat_mp, stat_mpperlevel, stat_movespeed, stat_armor,"
    "stat_armorperlevel, stat_spellblock, stat_spellblockperlevel, stat_attackrange, stat_hpregen,"
    "stat_hpregenperlevel, stat_mpregen, stat_mpregenperlevel, stat_crit, stat_critperlevel, stat_attackdamage,"
    "stat_attackdamageperlevel, stat_attackspeedperlevel, stat_attackspeed, is_active ) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s, %s, %s, %s, %s);"
)
ITEMS_INSERT_STMT = (
    "INSERT IGNORE INTO items "
    "(item_id, name, description, gold_base, gold_total, purchaseable, active_in_srmap, depth,"
    "patch_ver, is_active) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
SUMMONERS_INSERT_STMT = (
    "INSERT IGNORE INTO summoner_spells "
    "(ss_id, name, description, cooldown, patch_ver, is_active) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
PROPERTIES_INSERT_STMT = "INSERT INTO {} (name) VALUES (%s);"
ENTITIES_TAGS_INSERT_STMT = (
    "INSERT IGNORE INTO {0}_tag_map "
    "({0}_id, tag_id, patch_ver, is_active) "
    "VALUES (%s, %s, %s, %s);"
)
ENTITIES_STATS_INSERT_STMT = (
    "INSERT IGNORE INTO {0}_stat_map "
    "({0}_id, stat_id, value, patch_ver, is_active) "
    "VALUES (%s, %s, %s, %s, %s);"
)
ITEMS_ITEMS_INSERT_STMT = (
    "INSERT IGNORE INTO item_item_map "
    "(component_id, result_id, patch_ver, is_active) "
    "VALUES (%s, %s, %s, %s)"
)


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
            
            import os
            
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, path="./data")
    data = {}
    data['champion_json'] = read_json_file(CHAMPION_JSON_PATH % patch_version)
    data['item_json'] = read_json_file(ITEM_JSON_PATH % patch_version)
    data['summoner_json'] = read_json_file(SUMMONER_JSON_PATH % patch_version)
    insert_initial_data_into_db(data)
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
            response.raise_for_status()  # raise an exception if status not OK
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


def insert_initial_data_into_db(json_dicts: Dict):
    print('Opening connection to %s database...' % DB_TYPE)
    connection = mysql.connector.connect(**db_config)
    insert_rows(connection, json_dicts['champion_json'], CHAMPIONS_INSERT_STMT, get_champion_values, 'champions')
    insert_rows(connection, json_dicts['item_json'], ITEMS_INSERT_STMT, get_item_values, 'items')
    insert_rows(connection, json_dicts['summoner_json'], SUMMONERS_INSERT_STMT, get_summoner_values, 'summoners')
    associate_items_with_items(connection, json_dicts['item_json'])

    tagsToId = property_search_and_insert(connection, (json_dicts['champion_json'], json_dicts['item_json']), 'tags')
    associate_tags_with_entity(connection, tagsToId, json_dicts['champion_json'], 'champion', get_champion_id)
    associate_tags_with_entity(connection, tagsToId, json_dicts['item_json'], 'item', get_item_id)
    statsToId = property_search_and_insert(connection, (json_dicts['item_json'],), 'stats')
    associate_stats_with_entity(connection, statsToId, json_dicts['item_json'], 'item', get_item_id)

    connection.close()
    print('Import finished. Closing connection...')


# insert rows into each table
def insert_rows(connection, data: Dict, insert_stmt: str, get_values: Callable, table_name: str):
    print('Inserting rows into {} table...'.format(table_name))
    cursor = connection.cursor()
    all_values = [get_values(key, value) for (key, value) in data.items()]
    try:
        cursor.executemany(insert_stmt, all_values)
        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when executing a DB transaction (change rolled back): ', str(err))
    cursor.close()


# Search through a sequence of dictionaries to find uses of a specified property
# and create a table with all the possible values of that property
# @param seq_of_data Sequence of dictionaries representing entity data from Riot API
# @param property_name Property associated with entity in many to many relationship. Also the name of the table
#   the property values will be inserted into
# Return dictionary of property values with ids
def property_search_and_insert(connection, seq_of_data: Sequence, property_name: str) -> Dict:
    cursor = connection.cursor()
    property_set = set()
    # iterate over any entities containing the specified property. ex: champions, items
    for data in seq_of_data:
        for value in data.values():
            # value.get(property) expected to return list of strings
            if value.get(property_name):
                for property in value.get(property_name):
                    property_set.add(property)

    # Grab the auto_increment value before attempting to insert
    cursor.execute("SELECT AUTO_INCREMENT FROM information_schema.TABLES "
                   "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (db_config['database'], property_name))
    counter = cursor.fetchone()[0]
    # insert tag_set into tags table
    print('Inserting rows into {} table...'.format(property_name))
    property_values = [(property,) for property in property_set]
    try:
        cursor.executemany(PROPERTIES_INSERT_STMT.format(property_name), property_values)
        connection.commit()
    except mysql.connector.Error as err:
        print('Could not insert into {0} table. Skipping insert {0} step...'.format(property_name), err)
        return {}
    finally:
        cursor.close()

    property_dict = {}
    # Possible bug if this for loop executes in different order than before for the same set
    for property in property_set:
        property_dict[property] = counter
        counter += 1
    return property_dict


def associate_tags_with_entity(connection, tags: Dict, data: Dict, table: str, get_id: Callable):
    if not tags:
        return
    print('Inserting {}-tag associations...'.format(table))
    cursor = connection.cursor()
    entity_tag_values = []
    for (key, value) in data.items():
        if value.get('tags'):
            for tag in value.get('tags'):
                entity_tag_values.append((get_id(key, value), tags[tag], patch_version, True))
    try:
        cursor.executemany(ENTITIES_TAGS_INSERT_STMT.format(table), entity_tag_values)
        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when executing a DB transaction (change rolled back): ', str(err))
    cursor.close()


def associate_stats_with_entity(connection, stats: Dict, data: Dict, table: str, get_id: Callable):
    if not stats:
        return
    print('Inserting {}-stat associations...'.format(table))
    cursor = connection.cursor()
    entity_stat_values = []
    for (key, value) in data.items():
        if value.get('stats'):  # If this is not None, this should be a Dict
            for (stat_k, stat_v) in value.get('stats').items():
                entity_stat_values.append((get_id(key, value), stats[stat_k], stat_v, patch_version, True))
    try:
        cursor.executemany(ENTITIES_STATS_INSERT_STMT.format(table), entity_stat_values)
        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when executing a DB transaction (change rolled back): ', str(err))
    cursor.close()


def associate_items_with_items(connection, items: Dict):
    cursor = connection.cursor()
    item_recipe_values = []
    print('Inserting item-item associations...')
    for (key, value) in items.items():
        if value.get('into'):
            for result in value.get('into'):
                item_recipe_values.append((key, result, patch_version, True))
    try:
        cursor.executemany(ITEMS_ITEMS_INSERT_STMT, item_recipe_values)
        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when executing a DB transaction (change rolled back): ', str(err))
    cursor.close()

def get_champion_id(key, value):
    return value.get('key')


def get_item_id(key, value):
    return key


def get_champion_values(key: str, value: Dict):
    return (get_champion_id(key, value),
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


def get_item_values(key: str, value: Dict):
    return (get_item_id(key, value),
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


def get_summoner_values(key: str, value: Dict):
    return (value.get('key'),
            value.get('name'),
            value.get('description'),
            value.get('cooldown')[0],
            patch_version,
            True)


if __name__ == '__main__':
    initialize_static_tables()
