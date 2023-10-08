# Import necessary modules
import requests
import random
import json
import time 
import random

# URL for the Flask app
url = 'http://127.0.0.1:5000/add_transaction'

# Product ID for the product to add transactions to
product_id = "136537e9-06e7-4f1c-a427-d400df4c9b67"  # Change this to the desired product ID

# Generate random transactions data
transactions_data = []
for i in range(10):  # Generate 20 random transactions
    
    amount_credit = 0
    amount_debit = 0

    # Randomly determine if it's a credit or debit transaction
    if random.randint(0, 1):
        amount_debit = round(random.uniform(1000, 1000000), 2)
    else:
        amount_credit = round(random.uniform(100, 100000), 2)

    # Create a transaction data object
    transaction_data = {
        'product_id': product_id,
        'amount_credit': amount_credit,
        'amount_debit': amount_debit,
    }
    transactions_data.append(transaction_data)

# Send transactions data to the Flask app
for transaction in transactions_data:
    headers = {'Content-Type': 'application/json'}
    time.sleep(random.randint(7,15))
    # Send a POST request to the Flask app to add the transaction
    response = requests.post(url, data=json.dumps(transaction), headers=headers)

    # Check the response status and print appropriate messages
    if response.status_code == 201:
        print('Transaction added successfully:', transaction)
    else:
        print('Failed to add transaction:', transaction)
