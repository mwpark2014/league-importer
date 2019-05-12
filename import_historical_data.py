from config import db_config, DB_TYPE, RIOT_GAMES_API_KEY
import boto3
import json
import mysql.connector
import requests
import traceback
from typing import Dict


# # Get the service resource
# sqs = boto3.resource('sqs')
#
# # Get queue
# queue = sqs.get_queue_by_name(QueueName='MatchQueue.fifo')
#
# # test
# response = queue.send_message(
#     MessageBody='123',
#     MessageGroupId='messageGroup1'
# )
#
# # The response is NOT a resource, but gives you a message ID and MD5
# print(response.get('MessageId'))
# print(response.get('MD5OfMessageBody'))

def send_matchlist_message_from_account(account: Dict):
    # Check if account_id in pg:accounts
    # if yes return
    # if no,
    # 1. call https://na1.api.riotgames.com/lol/match/v4/matchlists/by-account/9MGanhKuOrahIcj9UQzgaB9AtypwvRbs1OMlNSapTJd57g?queue=420&api_key={RIOT_GAMES_API_KEY}
    # 2. insert account_id in pg:accounts
    # read json, loop through 100 items in arrow, add them to SQS
    return


def read_match(match_id: int):
    # Check if in mysql
    # if no, call match api
    # if yes, exit
    return


def insert_match_into_db():
    return

# if __name__ == '__main__':
