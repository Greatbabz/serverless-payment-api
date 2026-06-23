import boto3
import json
import uuid
from datetime import datetime

# DynamoDB resource — initialised outside handler for reuse across warm invocations
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Payment-Transactions')

def lambda_handler(event, context):
    """
    Serverless Payment Processor
    - Accepts POST /payment from API Gateway
    - Writes transaction to DynamoDB
    - Queues message to SQS for async processing
    - Sends SNS email alert for payments over 100,000
    """

    # -------------------------------------------------------
    # 1. Parse incoming request
    #    Handles both API Gateway HTTP calls and Test tab calls
    # -------------------------------------------------------
    if 'body' in event:
        body = json.loads(event['body'])   # real HTTP request
    else:
        body = event                        # API Gateway Test tab

    sender    = body.get('sender')
    recipient = body.get('recipient')
    amount    = float(body.get('amount'))
    reference = body.get('reference', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()

    # -------------------------------------------------------
    # 2. Persist transaction to DynamoDB
    # -------------------------------------------------------
    table.put_item(Item={
        'TransactionID': reference,
        'Timestamp':     timestamp,
        'Sender':        sender,
        'Recipient':     recipient,
        'Amount':        str(amount),
        'Status':        'Completed'
    })

    # -------------------------------------------------------
    # 3. Send to SQS for async downstream processing
    # -------------------------------------------------------
    sqs = boto3.client('sqs')
    sqs.send_message(
        QueueUrl='https://sqs.us-east-1.amazonaws.com/070340244863/PaymentProcessingQueue',
        MessageBody=json.dumps({
            'reference': reference,
            'sender':    sender,
            'recipient': recipient,
            'amount':    amount,
            'timestamp': timestamp
        })
    )

    # -------------------------------------------------------
    # 4. SNS alert for large payments (threshold: 100,000)
    # -------------------------------------------------------
    if amount > 100000:
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:070340244863:OluTech-Alerts',
            Subject='Large Payment Alert',
            Message=(
                f'Large payment detected.\n\n'
                f'Reference: {reference}\n'
                f'Amount:    {amount}\n'
                f'Sender:    {sender}\n'
                f'Recipient: {recipient}\n'
                f'Timestamp: {timestamp}'
            )
        )

    # -------------------------------------------------------
    # 5. Return success response
    # -------------------------------------------------------
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message':   'Payment processed successfully',
            'reference': reference,
            'timestamp': timestamp,
            'status':    'Completed'
        })
    }
