from config import db_config, DB_TYPE, RIOT_GAMES_API_KEY, \
    AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_SQS_URL, AWS_REGION_NAME
import boto3
from botocore.exceptions import ClientError
import json
import mysql.connector
import requests
import traceback
from typing import Dict


def initialize(params: Dict):
    if params.get('state') == 'backlog':
        process_backlog_matches()
    else:
        process_match_breadth_traversal()


def process_match_breadth_traversal():
    print('Traversing through matches and summoner accounts...')
    client = connect_to_sqs()
    receive_match_messages(client, 10)
    return


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
    response = sqs_client.delete_message_batch(
        QueueUrl=AWS_SQS_URL,
        Entries=entries
    )
    print('Successfully received message(s) and deleted from queue')
    return messages['Messages']

def read_match(match_id: int):
    # Check if in mysql
    # if no, call match api
    # if yes, exit
    return


def insert_single_match_into_db():
    # insert into mysql db
    return


def insert_batched_matches_into_db():
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
    # 1. call https://na1.api.riotgames.com/lol/match/v4/matchlists/by-account/9MGanhKuOrahIcj9UQzgaB9AtypwvRbs1OMlNSapTJd57g?queue=420&api_key={RIOT_GAMES_API_KEY}
    # 2. insert account_id in mySql:accounts
    # read json, loop through 100 items in a row, add them to SQS
    return


# Send get request to url and return json
def get(url: str):
    try:
        print('Reading response and parsing json file from {}'.format(url))
        with requests.get(url, timeout=(2, 5), encoding="utf8") as response:
            return json.load(response)
    except Exception as err:
        print('Exception encountered when serializing into JSON: ', str(err))
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


if __name__ == '__main__':
    initialize({})
