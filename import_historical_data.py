import boto3
import mysql.connector
import os
import requests
import traceback
from base64 import b64decode
from botocore.exceptions import ClientError
from typing import Dict, Sequence, Tuple

kms = boto3.client('kms')


def decrypt(encrypted):
    return kms.decrypt(CiphertextBlob=b64decode(encrypted))['Plaintext'].decode("utf-8")


db_config = {
    'host': decrypt(os.environ['DB_HOST']),
    'database': decrypt(os.environ['DB_NAME']),
    'user': decrypt(os.environ['DB_USER']),
    'password': decrypt(os.environ['DB_PW']),
}
RIOT_GAMES_API_KEY = decrypt(os.environ['RIOT_GAMES_API_KEY'])
AWS_ACCESS_KEY = decrypt(os.environ['AWS_ACCESS_KEY_2'])
AWS_SECRET_KEY = decrypt(os.environ['AWS_SECRET_KEY_2'])
AWS_SQS_URL = decrypt(os.environ['AWS_SQS_URL'])
AWS_REGION_NAME = decrypt(os.environ['AWS_REGION_NAME'])

REGION_PREFIXES = ('na1', 'kr', 'euw1')
RIOT_GET_MATCH_URL = 'https://{0}.api.riotgames.com/lol/match/v4/matches/{1}'
# Only grab matches for 5v5 Ranked and matches from 5/1/19 and onward
RIOT_GET_MATCHLIST_URL = \
    'https://{0}.api.riotgames.com/lol/match/v4/matchlists/by-account/{1}?queue=420&beginTime=1556668800'

ACCOUNTS_INSERT_STMT = (
    'INSERT INTO accounts (account_id, summoner_name, summoner_id, region) '
    'VALUES (%s, %s, %s, %s)'
)
MATCHES_INSERT_STMT = (
    'INSERT INTO matches (match_id, region, game_creation, game_duration, season_id, game_version) '
    'VALUES (%s, %s, FROM_UNIXTIME(%s / 1000), %s, %s, %s)'
)
MATCH_TEAMS_INSERT_STMT = (
    'INSERT INTO match_teams (match_team_id, match_id, win, first_blood, first_tower, first_inhibitor, first_baron, '
    'first_dragon, first_riftherald, tower_kills, inhibitor_kills, baron_kills, dragon_kills, riftherald_kills) '
    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
)
# 64
MATCH_PARTICIPANTS_INSERT_STMT = (
    'INSERT INTO match_participants (match_participant_id, match_team_id, match_id, champion_id, spell1_id, spell2_id, '
    'account_id, highest_achieved_season_tier, win, item0_id, item1_id, item2_id, item3_id, item4_id, item5_id, '
    'item6_id, kills, deaths, assists, largestKillingSpree, largestMultiKill, killingSprees, longestTimeSpentLiving, '
    'doubleKills, tripleKills, quadraKills, pentaKills, unrealKills, totalDamageDealt, magicDamageDealt, '
    'physicalDamageDealt, trueDamageDealt, largestCriticalStrike, totalDamageDealtToChampions, '
    'magicDamageDealtToChampions, physicalDamageDealtToChampions, trueDamageDealtToChampions, totalHeal, '
    'totalUnitsHealed, damageSelfMitigated, damageDealtToObjectives, damageDealtToTurrets, visionScore, '
    'timeCCingOthers, totalDamageTaken, magicalDamageTaken, physicalDamageTaken, trueDamageTaken, goldEarned, '
    'goldSpent, turretKills, inhibitorKills, totalMinionsKilled, neutralMinionsKilled, totalTimeCrowdControlDealt, '
    'champLevel, visionWardsBoughtInGame, sightWardsBoughtInGame, firstBloodKill, firstBloodAssist, firstTowerKill, '
    'firstTowerAssist, firstInhibitorKill, firstInhibitorAssist, creepsPerMinDelta_id, xpPerMinDelta_id, '
    'goldPerMinDelta_id, csDiffPerMinDelta_id, xpDiffPerMinDelta_id, damageTakenPerMinDelta_id, '
    'damageTakenDiffPerMinDelta_id) '

    'VALUES ({match_participant_id}, {match_team_id}, {match_id}, {champion_id}, {spell1_id}, {spell2_id}, '
    '{account_id}, {highest_achieved_season_tier}, {win}, {item0_id}, {item1_id}, {item2_id}, {item3_id}, {item4_id}, '
    '{item5_id}, {item6_id}, {kills}, {deaths}, {assists}, {largestKillingSpree}, {largestMultiKill}, {killingSprees}, '
    '{longestTimeSpentLiving}, {doubleKills}, {tripleKills}, {quadraKills}, {pentaKills}, {unrealKills}, '
    '{totalDamageDealt}, {magicDamageDealt}, {physicalDamageDealt}, {trueDamageDealt}, {largestCriticalStrike}, '
    '{totalDamageDealtToChampions}, {magicDamageDealtToChampions}, {physicalDamageDealtToChampions}, '
    '{trueDamageDealtToChampions}, {totalHeal}, {totalUnitsHealed}, {damageSelfMitigated}, {damageDealtToObjectives}, '
    '{damageDealtToTurrets}, {visionScore}, {timeCCingOthers}, {totalDamageTaken}, {magicalDamageTaken}, '
    '{physicalDamageTaken}, {trueDamageTaken}, {goldEarned}, {goldSpent}, {turretKills}, {inhibitorKills}, '
    '{totalMinionsKilled}, {neutralMinionsKilled}, {totalTimeCrowdControlDealt}, {champLevel}, '
    '{visionWardsBoughtInGame}, {sightWardsBoughtInGame}, {firstBloodKill}, {firstBloodAssist}, {firstTowerKill}, '
    '{firstTowerAssist}, {firstInhibitorKill}, {firstInhibitorAssist}, {creepsPerMinDelta_id}, {xpPerMinDelta_id}, '
    '{goldPerMinDelta_id}, {csDiffPerMinDelta_id}, {xpDiffPerMinDelta_id}, {damageTakenPerMinDelta_id}, '
    '{damageTakenDiffPerMinDelta_id})'
)
MATCH_TIMELINES_INSERT_STMT = (
    'INSERT INTO match_timelines_stats (interval_0_10, interval_10_20, interval_20_30, interval_30_end) '
    'VALUES (%s, %s, %s, %s)'
)


def lambda_handler(event, context):
    initialize(event)
    return {
        'statusCode': 200
    }


def initialize(params: Dict):
    if params.get('state') == 'backlog':
        process_backlog_matches()
    else:
        process_match_breadth_traversal()


# Gather match data by doing a BFS
# 1. Receive one message from SQS Match Queue with match_id
# 2. Send get request to match Riot Games API with match_id
# 3. Insert match data into DB
# 4. Loop through summoner accounts within match
# 5. For each summoner account, if not previously visited, add their match list to SQS Match Queue
def process_match_breadth_traversal():
    print('Traversing through matches and summoner accounts...')
    client = connect_to_sqs()
    messages = receive_match_messages(client, 1)
    # Read first message
    if not messages:
        print('No match ids could be received. Exiting...')
        return
    match_id = messages[0].get('Body')

    # Get match data for match_id from riot games API
    match = get(RIOT_GET_MATCH_URL.format('na1', match_id))
    if not match:
        print('No matches could be retrieved from Riot API. Exiting...')
        return

    connection = mysql.connector.connect(**db_config)
    # Loop through summoner accounts within match
    accountIdByParticipantId = {}
    if match.get('participantIdentities'):
        for participant in match.get('participantIdentities'):
            send_matchlist_message_from_account(connection, client, participant['player'])
            # Fail fast if there are no participant or account ids
            accountIdByParticipantId[participant['participantId']] = participant['player']['currentAccountId']

    # Insert match data into DB
    insert_single_match_into_db(connection, match, accountIdByParticipantId)
    print('Completed all operations. Exiting...')
    connection.close()


# Process matches 20 at a time
def process_backlog_matches():
    print('Processing backlog matches...')
    client = connect_to_sqs()
    connection = mysql.connector.connect(**db_config)
    for i in range(2):
        messages = receive_match_messages(client, 10)
        match_ids = [message.get('Body') for message in messages]
        for match_id in match_ids:
            # Get match data for match_id from riot games API
            match = get(RIOT_GET_MATCH_URL.format('na1', match_id))

            # Loop through summoner accounts within match
            # Populate the account_id column
            accountIdByParticipantId = {}
            if match.get('participantIdentities'):
                for participant in match.get('participantIdentities'):
                    # Fail fast if there are no participant or account ids
                    accountIdByParticipantId[participant['participantId']] = participant['player']['currentAccountId']

            # Insert match data into DB
            insert_single_match_into_db(connection, match, accountIdByParticipantId)


# numMessages must be <= 10 due to AWS restrictions
def receive_match_messages(sqs_client, numMessages):
    if sqs_client is None:
        return
    messages = sqs_client.receive_message(
        QueueUrl=AWS_SQS_URL,
        MaxNumberOfMessages=numMessages
    )
    if not messages.get('Messages'):
        print('SQS message queue is empty.')
        return None
    # Need to delete the message(s) after receiving it from queue
    entries = [{'Id': message.get('MessageId'), 'ReceiptHandle': message.get('ReceiptHandle')}
               for message in messages['Messages']]
    sqs_client.delete_message_batch(
        QueueUrl=AWS_SQS_URL,
        Entries=entries
    )
    print('Successfully received message(s) and deleted from queue')
    return messages['Messages']


def read_match(match_id: str):
    get(RIOT_GET_MATCH_URL.format('na1', match_id))


# Insert single match row into matches table
def insert_single_match_into_db(connection, match: Dict, accountIdByParticipantId: Dict):
    if not match:
        return None
    cursor = connection.cursor()
    try:
        match_id = match.get('gameId')
        print('Inserting match id={} into matches table...'.format(match_id))

        # Insert into matches table
        match_values = (match_id, match.get('platformId'), match.get('gameCreation'),  # No MS Precision
                        match.get('gameDuration'), match.get('seasonId'), match.get('gameVersion'))
        cursor.execute(MATCHES_INSERT_STMT, match_values)

        # Insert into match_teams table
        if match.get('teams'):
            match_team_values = [(
                team.get('teamId'), match_id, team.get('win'), team.get('firstBlood'), team.get('firstTower'),
                team.get('firstInhibitor'), team.get('firstBaron'), team.get('firstDragon'),
                team.get('firstRiftHerald'), team.get('towerKills'), team.get('inhibitorKills'),
                team.get('baronKills'), team.get('dragonKills'), team.get('riftHeraldKills')
            ) for team in match['teams']]
            cursor.executemany(MATCH_TEAMS_INSERT_STMT, match_team_values)

        # Insert into match_timelines and match_participants table
        for participant in match.get('participants', []):
            participant_value_dict = {}
            # Insert into match_timelines table
            if participant.get('timeline'):
                # For each timeline stat for this particular participant
                for (key, value) in participant.get('timeline').items():
                    if (key in ('creepsPerMinDeltas', 'xpPerMinDeltas', 'goldPerMinDeltas', 'csDiffPerMinDeltas',
                                'xpDiffPerMinDeltas', 'damageTakenPerMinDeltas', 'damageTakenDiffPerMinDeltas')):
                        match_timeline_values = (
                            value.get('0-10'), value.get('10-20'), value.get('20-30'), value.get('30-end')
                        )
                        cursor.execute(MATCH_TIMELINES_INSERT_STMT, match_timeline_values)
                        # Set foreign key of match_participants table
                        participant_value_dict[key[:-1] + '_id'] = cursor.lastrowid
            set_participant_values(participant_value_dict, participant)  # Mutate participant_value_dict
            participant_value_dict['match_id'] = match_id
            # Since we're directly formatting the insert statement string, we need to add quotes for strings
            participant_value_dict['account_id'] = "'" + accountIdByParticipantId.get(
                participant.get('participantId')) + "'"
            cursor.execute(MATCH_PARTICIPANTS_INSERT_STMT.format(**participant_value_dict))
        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when attempting to insert match with id: {}. Skipping...: '
              .format(match_id), str(err))
        return None
    finally:
        cursor.close()


def insert_batched_matches_into_db(matches: Sequence):
    # insert into mysql db
    return


def send_matchlist_message_from_account(connection, sqs_client, account: Dict):
    account_id = account.get('currentAccountId')
    print('Grabbing match lists of summoner account id={}...'.format(account_id))
    cursor = connection.cursor()
    # Attempt to insert account. If account_id not unique, it will fail
    try:
        account_values = (account_id, account.get('summonerName'), account.get('summonerId'),
                          account.get('currentPlatformId'))
        cursor.execute(ACCOUNTS_INSERT_STMT, account_values)
        match_list = get(RIOT_GET_MATCHLIST_URL.format('na1', account_id))
        batch_container = []
        for match in match_list.get('matches', []):
            batch_container.append(match.get('gameId'))
            if len(batch_container) >= 10:
                send_matches_to_sqs(sqs_client, batch_container)
                batch_container.clear()
        # Send the rest that are left over
        if len(batch_container) > 0:
            send_matches_to_sqs(sqs_client, batch_container)
        connection.commit()
    except mysql.connector.IntegrityError as err:
        print('This summoner account, id: {}, has most likely already been added. Skipping...: '
              .format(account_id), str(err))
    finally:
        cursor.close()


# Send get request to url and return json
def get(url: str):
    try:
        print('Reading response and parsing json file from {}'.format(url))
        jsonResponse = requests.get(url, timeout=(2, 5), headers={'X-Riot-Token': RIOT_GAMES_API_KEY}).json()
        # Unsuccessful status code
        status = jsonResponse.get('status')
        # For Riot Games API in particular, there will be no status field for successful 200 responses
        if status and not status.get('status_code') == 200:
            print('Unsuccessful response status code {}: {}'
                  .format(status.get('status_code'), status.get('message')))
            return None
        else:
            return jsonResponse
    except Exception as err:
        print('Exception encountered in response from Riot Games API or when serializing into JSON: ', str(err))
        traceback.print_tb(err.__traceback__)
        return None


def connect_to_sqs():
    try:
        # Connect to aws sqs api
        sqs_client = boto3.client(
            'sqs',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION_NAME,
        )
        return sqs_client
    except ClientError as err:
        print('Exception encountered accessing AWS SQS: ', str(err))
        traceback.print_tb(err.__traceback__)
        return None


# Send batches of matches to AWS SQS Match Queue
def send_matches_to_sqs(sqs_client, matchIds):
    if sqs_client is None:
        return
    messages = [
        {
            'Id': str(matchId),
            'MessageBody': str(matchId),
            'MessageGroupId': '1'
        }
        for matchId in matchIds
    ]
    # Send message to SQS
    response = sqs_client.send_message_batch(
        QueueUrl=AWS_SQS_URL,
        Entries=messages,
    )
    print('Sent {} messages with to SQS'.format(len(messages)))
    # print(response)


def set_participant_values(values: Dict, participant_data: Dict):
    values['match_participant_id'] = participant_data.get('participantId')
    values['match_team_id'] = participant_data.get('teamId')
    values['champion_id'] = participant_data.get('championId')
    values['spell1_id'] = participant_data.get('spell1Id')
    values['spell2_id'] = participant_data.get('spell2Id')
    values['win'] = participant_data.get('stats', {}).get('win', 'null')
    values['item0_id'] = participant_data.get('stats', {}).get('item0', 'null')
    values['item1_id'] = participant_data.get('stats', {}).get('item1', 'null')
    values['item2_id'] = participant_data.get('stats', {}).get('item2', 'null')
    values['item3_id'] = participant_data.get('stats', {}).get('item3', 'null')
    values['item4_id'] = participant_data.get('stats', {}).get('item4', 'null')
    values['item5_id'] = participant_data.get('stats', {}).get('item5', 'null')
    values['item6_id'] = participant_data.get('stats', {}).get('item6', 'null')
    values['kills'] = participant_data.get('stats', {}).get('kills', 'null')
    values['deaths'] = participant_data.get('stats', {}).get('deaths', 'null')
    values['assists'] = participant_data.get('stats', {}).get('assists', 'null')
    values['largestKillingSpree'] = participant_data.get('stats', {}).get('largestKillingSpree', 'null')
    values['largestMultiKill'] = participant_data.get('stats', {}).get('largestMultiKill', 'null')
    values['killingSprees'] = participant_data.get('stats', {}).get('killingSprees', 'null')
    values['longestTimeSpentLiving'] = participant_data.get('stats', {}).get('longestTimeSpentLiving', 'null')
    values['doubleKills'] = participant_data.get('stats', {}).get('doubleKills', 'null')
    values['tripleKills'] = participant_data.get('stats', {}).get('tripleKills', 'null')
    values['quadraKills'] = participant_data.get('stats', {}).get('quadraKills', 'null')
    values['pentaKills'] = participant_data.get('stats', {}).get('pentaKills', 'null')
    values['unrealKills'] = participant_data.get('stats', {}).get('unrealKills', 'null')
    values['totalDamageDealt'] = participant_data.get('stats', {}).get('totalDamageDealt', 'null')
    values['magicDamageDealt'] = participant_data.get('stats', {}).get('magicDamageDealt', 'null')
    values['physicalDamageDealt'] = participant_data.get('stats', {}).get('physicalDamageDealt', 'null')
    values['trueDamageDealt'] = participant_data.get('stats', {}).get('trueDamageDealt', 'null')
    values['largestCriticalStrike'] = participant_data.get('stats', {}).get('largestCriticalStrike', 'null')
    values['totalDamageDealtToChampions'] = participant_data.get('stats', {}).get('totalDamageDealtToChampions', 'null')
    values['magicDamageDealtToChampions'] = participant_data.get('stats', {}).get('magicDamageDealtToChampions', 'null')
    values['physicalDamageDealtToChampions'] = participant_data.get('stats', {}).get('physicalDamageDealtToChampions',
                                                                                     'null')
    values['trueDamageDealtToChampions'] = participant_data.get('stats', {}).get('trueDamageDealtToChampions', 'null')
    values['totalHeal'] = participant_data.get('stats', {}).get('totalHeal', 'null')
    values['totalUnitsHealed'] = participant_data.get('stats', {}).get('totalUnitsHealed', 'null')
    values['damageSelfMitigated'] = participant_data.get('stats', {}).get('damageSelfMitigated', 'null')
    values['damageDealtToObjectives'] = participant_data.get('stats', {}).get('damageDealtToObjectives', 'null')
    values['damageDealtToTurrets'] = participant_data.get('stats', {}).get('damageDealtToTurrets', 'null')
    values['visionScore'] = participant_data.get('stats', {}).get('visionScore', 'null')
    values['timeCCingOthers'] = participant_data.get('stats', {}).get('timeCCingOthers', 'null')
    values['totalDamageTaken'] = participant_data.get('stats', {}).get('totalDamageTaken', 'null')
    values['magicalDamageTaken'] = participant_data.get('stats', {}).get('magicalDamageTaken', 'null')
    values['physicalDamageTaken'] = participant_data.get('stats', {}).get('physicalDamageTaken', 'null')
    values['trueDamageTaken'] = participant_data.get('stats', {}).get('trueDamageTaken', 'null')
    values['goldEarned'] = participant_data.get('stats', {}).get('goldEarned', 'null')
    values['goldSpent'] = participant_data.get('stats', {}).get('goldSpent', 'null')
    values['turretKills'] = participant_data.get('stats', {}).get('turretKills', 'null')
    values['inhibitorKills'] = participant_data.get('stats', {}).get('inhibitorKills', 'null')
    values['totalMinionsKilled'] = participant_data.get('stats', {}).get('totalMinionsKilled', 'null')
    values['neutralMinionsKilled'] = participant_data.get('stats', {}).get('neutralMinionsKilled', 'null')
    values['totalTimeCrowdControlDealt'] = participant_data.get('stats', {}).get('totalTimeCrowdControlDealt', 'null')
    values['champLevel'] = participant_data.get('stats', {}).get('champLevel', 'null')
    values['visionWardsBoughtInGame'] = participant_data.get('stats', {}).get('visionWardsBoughtInGame', 'null')
    values['sightWardsBoughtInGame'] = participant_data.get('stats', {}).get('sightWardsBoughtInGame', 'null')
    values['firstBloodKill'] = participant_data.get('stats', {}).get('firstBloodKill', 'null')
    values['firstBloodAssist'] = participant_data.get('stats', {}).get('firstBloodAssist', 'null')
    values['firstTowerKill'] = participant_data.get('stats', {}).get('firstTowerKill', 'null')
    values['firstTowerAssist'] = participant_data.get('stats', {}).get('firstTowerAssist', 'null')
    values['firstInhibitorKill'] = participant_data.get('stats', {}).get('firstInhibitorKill', 'null')
    values['firstInhibitorAssist'] = participant_data.get('stats', {}).get('firstInhibitorAssist', 'null')
    # Optional values
    # Since we're directly formatting the insert statement string, we need to add quotes for strings
    values['highest_achieved_season_tier'] = "'" + participant_data.get('highestAchievedSeasonTier', 'null') + "'"
    values['creepsPerMinDelta_id'] = 'null'
    values['xpPerMinDelta_id'] = 'null'
    values['goldPerMinDelta_id'] = 'null'
    values['csDiffPerMinDelta_id'] = 'null'
    values['xpDiffPerMinDelta_id'] = 'null'
    values['damageTakenPerMinDelta_id'] = 'null'
    values['damageTakenDiffPerMinDelta_id'] = 'null'

if __name__ == '__main__':
    initialize({})
