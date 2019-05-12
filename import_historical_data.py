from config import db_config, DB_TYPE, RIOT_GAMES_API_KEY, \
    AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_SQS_URL, AWS_REGION_NAME
import boto3
from botocore.exceptions import ClientError
import json
import mysql.connector
import requests
import traceback
from typing import Dict, Sequence, Tuple

REGION_PREFIXES = ('na1', 'kr', 'euw1')
RIOT_GET_MATCH_URL = 'https://{0}.api.riotgames.com/lol/match/v4/matches/{1}'
RIOT_GET_MATCHLIST_URL = 'https://{0}.api.riotgames.com/lol/match/v4/matchlists/by-account/{1}' \
                         '?queue=420&api_key=%s' % RIOT_GAMES_API_KEY

MATCHES_INSERT_STMT = (
    'INSERT INTO matches (match_id, region, game_creation, game_duration, season_id, game_version) '
    'VALUES (%s, %s, %s, %s, %s, %s)'
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

    # Loop through summoner accounts within match
    accountIdByParticipantId = {}
    if match.get('participantIdentities'):
        for participant in match.get('participantIdentities'):
            send_matchlist_message_from_account(participant)
            # Fail fast if there are no participant or account ids
            accountIdByParticipantId[participant['participantId']] = participant['player']['currentAccountId']

    # Insert match data into DB
    insert_single_match_into_db(match, accountIdByParticipantId)


def process_backlog_matches():
    print('Processing backlog matches...')
    client = connect_to_sqs()
    return


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
def insert_single_match_into_db(match: Dict, accountIdByParticipantId: Dict):
    if not match:
        return None
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    try:
        print('Inserting row into matches table...')

        # Insert into matches table
        match_id = match.get('gameId')
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
            participant_value_dict['account_id'] = accountIdByParticipantId.get(participant.get('participantId'))
            print(MATCH_PARTICIPANTS_INSERT_STMT.format(**participant_value_dict))
            cursor.execute(MATCH_PARTICIPANTS_INSERT_STMT.format(**participant_value_dict))

        connection.commit()
    except mysql.connector.Error as err:
        print('Exception encountered when attempting to insert match with id: {}. Skipping...: '
              .format(match_id), str(err))
        return None
    finally:
        cursor.close()
        connection.close()


def insert_batched_matches_into_db(matches: Sequence):
    # insert into mysql db
    return


def send_matchlist_message_from_account(account: Dict):
    # Attempt to insert account. If account_id not unique, it will fail
    try:
        return
    except mysql.connector.Error as err:
        print('Exception encountered when attempting to add {} to accounts. Skipping...: '
              .format(account.get('account_id')), str(err))

    # if yes return
    # if no,
    # 1. call riot games api
    # 2. insert account_id in mySql:accounts
    # read json, loop through 100 items in a row, add them to SQS
    return


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


def send_message_to_sqs(sqs_client, message):
    if sqs_client is None:
        return
    # Send message to SQS
    response = sqs_client.send_message(
        QueueUrl=AWS_SQS_URL,
        MessageBody=message,
        MessageGroupId='1',
    )
    print('Sent message with id: {} to SQS'.format(response.get('MessageId')))

    def get_match_values(match: Dict) -> Tuple:
        return ()


def set_participant_values(values: Dict, participant_data: Dict):
    values['match_participant_id'] = participant_data.get('participantId')
    values['match_team_id'] = participant_data.get('teamId')
    values['champion_id'] = participant_data.get('championId')
    values['spell1_id'] = participant_data.get('spell1Id')
    values['spell2_id'] = participant_data.get('spell2Id')
    # Since we're directly formatting the insert statement string, we need to add quotes for strings
    values['highest_achieved_season_tier'] = "'" + participant_data.get('highestAchievedSeasonTier') + "'"
    values['win'] = participant_data.get('stats', {}).get('win')
    values['item0_id'] = participant_data.get('stats', {}).get('item0')
    values['item1_id'] = participant_data.get('stats', {}).get('item1')
    values['item2_id'] = participant_data.get('stats', {}).get('item2')
    values['item3_id'] = participant_data.get('stats', {}).get('item3')
    values['item4_id'] = participant_data.get('stats', {}).get('item4')
    values['item5_id'] = participant_data.get('stats', {}).get('item5')
    values['item6_id'] = participant_data.get('stats', {}).get('item6')
    values['kills'] = participant_data.get('stats', {}).get('kills')
    values['deaths'] = participant_data.get('stats', {}).get('deaths')
    values['assists'] = participant_data.get('stats', {}).get('assists')
    values['largestKillingSpree'] = participant_data.get('stats', {}).get('largestKillingSpree')
    values['largestMultiKill'] = participant_data.get('stats', {}).get('largestMultiKill')
    values['killingSprees'] = participant_data.get('stats', {}).get('killingSprees')
    values['longestTimeSpentLiving'] = participant_data.get('stats', {}).get('longestTimeSpentLiving')
    values['doubleKills'] = participant_data.get('stats', {}).get('doubleKills')
    values['tripleKills'] = participant_data.get('stats', {}).get('tripleKills')
    values['quadraKills'] = participant_data.get('stats', {}).get('quadraKills')
    values['pentaKills'] = participant_data.get('stats', {}).get('pentaKills')
    values['unrealKills'] = participant_data.get('stats', {}).get('unrealKills')
    values['totalDamageDealt'] = participant_data.get('stats', {}).get('totalDamageDealt')
    values['magicDamageDealt'] = participant_data.get('stats', {}).get('magicDamageDealt')
    values['physicalDamageDealt'] = participant_data.get('stats', {}).get('physicalDamageDealt')
    values['trueDamageDealt'] = participant_data.get('stats', {}).get('trueDamageDealt')
    values['largestCriticalStrike'] = participant_data.get('stats', {}).get('largestCriticalStrike')
    values['totalDamageDealtToChampions'] = participant_data.get('stats', {}).get('totalDamageDealtToChampions')
    values['magicDamageDealtToChampions'] = participant_data.get('stats', {}).get('magicDamageDealtToChampions')
    values['physicalDamageDealtToChampions'] = participant_data.get('stats', {}).get('physicalDamageDealtToChampions')
    values['trueDamageDealtToChampions'] = participant_data.get('stats', {}).get('trueDamageDealtToChampions')
    values['totalHeal'] = participant_data.get('stats', {}).get('totalHeal')
    values['totalUnitsHealed'] = participant_data.get('stats', {}).get('totalUnitsHealed')
    values['damageSelfMitigated'] = participant_data.get('stats', {}).get('damageSelfMitigated')
    values['damageDealtToObjectives'] = participant_data.get('stats', {}).get('damageDealtToObjectives')
    values['damageDealtToTurrets'] = participant_data.get('stats', {}).get('damageDealtToTurrets')
    values['visionScore'] = participant_data.get('stats', {}).get('visionScore')
    values['timeCCingOthers'] = participant_data.get('stats', {}).get('timeCCingOthers')
    values['totalDamageTaken'] = participant_data.get('stats', {}).get('totalDamageTaken')
    values['magicalDamageTaken'] = participant_data.get('stats', {}).get('magicalDamageTaken')
    values['physicalDamageTaken'] = participant_data.get('stats', {}).get('physicalDamageTaken')
    values['trueDamageTaken'] = participant_data.get('stats', {}).get('trueDamageTaken')
    values['goldEarned'] = participant_data.get('stats', {}).get('goldEarned')
    values['goldSpent'] = participant_data.get('stats', {}).get('goldSpent')
    values['turretKills'] = participant_data.get('stats', {}).get('turretKills')
    values['inhibitorKills'] = participant_data.get('stats', {}).get('inhibitorKills')
    values['totalMinionsKilled'] = participant_data.get('stats', {}).get('totalMinionsKilled')
    values['neutralMinionsKilled'] = participant_data.get('stats', {}).get('neutralMinionsKilled')
    values['totalTimeCrowdControlDealt'] = participant_data.get('stats', {}).get('totalTimeCrowdControlDealt')
    values['champLevel'] = participant_data.get('stats', {}).get('champLevel')
    values['visionWardsBoughtInGame'] = participant_data.get('stats', {}).get('visionWardsBoughtInGame')
    values['sightWardsBoughtInGame'] = participant_data.get('stats', {}).get('sightWardsBoughtInGame')
    values['firstBloodKill'] = participant_data.get('stats', {}).get('firstBloodKill')
    values['firstBloodAssist'] = participant_data.get('stats', {}).get('firstBloodAssist')
    values['firstTowerKill'] = participant_data.get('stats', {}).get('firstTowerKill')
    values['firstTowerAssist'] = participant_data.get('stats', {}).get('firstTowerAssist')
    values['firstInhibitorKill'] = participant_data.get('stats', {}).get('firstInhibitorKill')
    values['firstInhibitorAssist'] = participant_data.get('stats', {}).get('firstInhibitorAssist')

if __name__ == '__main__':
    initialize({})
