import os
from datetime import datetime
import uuid
import requests

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user

from . import db
from .models import User, Product, Transactions
from .plivo_utils import send_sms, get_client

from sqlalchemy.exc import SQLAlchemyError

import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from reportlab.lib.pagesizes import A3
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph    
from reportlab.lib import colors
from reportlab.lib import pdfencrypt
from reportlab.lib.styles import getSampleStyleSheet

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """
    Renders the index.html page.

    Returns:
        str: Rendered HTML content.
    """
    return render_template('index.html')


@main.route('/add_product', methods=['POST'])
@login_required
def add_product():
    """
    Adds a new product based on the provided data. The product can be a credit card(CC) or a Savings Account(SB).

    Returns:
        str: JSON response with a success message or an error message.
    """
    user_id = current_user.id
    request_data = request.get_json()
    print(request_data)
    if not request_data:
        return jsonify({"error": "Invalid JSON data"}), 400

    product_type = request_data.get('product_type')
    date_of_opening = request_data.get('date_of_opening', "")
    current_balance = request_data.get('current_balance', 0)
    current_due = request_data.get('current_due', 0)
    payment_due_date = request_data.get('payment_due_date', "")

    # Create a new product
    new_product = Product(
        product_id=str(uuid.uuid4()),
        user_id=user_id,
        product_type=product_type,
        date_of_opening=datetime.strptime(date_of_opening, '%d/%m/%Y').date(),
        current_balance=current_balance,
        current_due=current_due,
        payment_due_date=datetime.strptime(payment_due_date, '%d/%m/%Y').date()
    )

    db.session.add(new_product)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    return jsonify({"message": "Product added successfully."}), 201


@main.route('/products', methods=['GET'])
@login_required
def get_products():
    """
    Retrieves all products associated with the logged-in user.

    Returns:
        str: JSON response containing the list of products or an error message.
    """
    user_id = current_user.id

    # Retrieve all products for the logged-in user
    products = Product.query.filter_by(user_id=user_id).all()

    # Convert the products to a list of dictionaries
    product_list = []
    for product in products:
        product_list.append({
            'product_id': product.product_id,
            'product_type': product.product_type,
            'date_of_opening': product.date_of_opening.strftime('%Y-%m-%d'),
            'current_balance': product.current_balance,
            'current_due': product.current_due,
            'payment_due_date': product.payment_due_date.strftime('%Y-%m-%d') if product.payment_due_date else None
        })

    return jsonify({'products': product_list}), 200


@main.route('/add_transaction', methods=['POST'])
def add_transaction():
    """
    Adds a new transaction for the provided product-id associated with the user of interest.

    Returns:
        str: JSON response with a success message or an error message.
    """
    request_data = request.get_json()

    if not request_data:
        return jsonify({"error": "Invalid JSON data"}), 400

    product_id = request_data.get('product_id')
    product = Product.query.filter_by(product_id=product_id).first()
    user_id = product.user_id
    user = User.query.filter_by(id=user_id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    amount_credit = request_data.get('amount_credit', 0.0)
    amount_debit = request_data.get('amount_debit', 0.0)

    # Validate that either credit or debit is greater than 0, not both
    if (amount_credit > 0 and amount_debit > 0) or (amount_credit == 0 and amount_debit == 0) or amount_credit<0 or amount_debit<0:
        return jsonify({"error": "Invalid transaction."}), 400

    # Update the balance based on the product type
    if product.product_type == 'CC':
        print(amount_debit, amount_credit)
        # For Credit Card, credit amount subtracts from current_due, debit amount adds to current_due
        if amount_credit > 0:
            product.current_due -= amount_credit
        elif amount_debit > 0:
            product.current_due += amount_debit
    elif product.product_type == 'SB':
        # For Savings Account, credit amount adds to current_balance, debit amount subtracts from current_balance
        if amount_credit > 0:
            product.current_balance += amount_credit
        elif amount_debit > 0:
            product.current_balance -= amount_debit

    # Update the transaction date to the current date
    transaction_date = datetime.now()

    # Update the product's new balance
    product.balance = product.current_balance if product.product_type == 'SB' else product.current_due
    product.balance = round(product.balance, 2)
    # Create a new transaction
    new_transaction = Transactions(
        transaction_id=str(uuid.uuid4()),
        product_id=product_id,
        amount_credit=amount_credit,
        amount_debit=amount_debit,
        transaction_date=transaction_date,
        balance=product.balance
    )

    db.session.add(new_transaction)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    
    try:
        type_transaction="debited" if amount_debit >0 else "credited"
        amount_transaction=amount_debit if amount_debit>0 else amount_credit
        type_balance="outstanding" if product.product_type =="CC" else "balance"
        message=f"Dear customer, your {product.product_type} {product_id} has been {type_transaction} by {amount_transaction} and your current {type_balance} is {product.balance}"
        cl=get_client()
        # print(user.id, user)
        send_sms(cl,dst_ph=user.contact_number,msg=message)
    except Exception as e:
        print(e)
        flash("Couldn't deliver SMS for the transaction")

    return jsonify({"message": "Transaction added successfully.", "new_balance": product.balance}), 201


@main.route('/transactions_get', methods=['GET'])
def get_transactions():
    # Retrieve the product ID from the request
    product_id = request.form.get('product_id')

    if not product_id:
        return jsonify({"error": "Product ID is required"}), 400

    # Retrieve all transactions for the specified product ID
    transactions = Transactions.query.filter_by(product_id=product_id).all()

    # Convert the transactions to a list of dictionaries
    transaction_list = []
    for transaction in transactions:
        transaction_list.append({
            'transaction_id': transaction.transaction_id,
            'amount_credit': transaction.amount_credit,
            'amount_debit': transaction.amount_debit,
            'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'balance': transaction.balance
        })

    return jsonify({'transactions': transaction_list}), 200


def create_pdf(transactions, filepath, dob, user_name, product_id, product_type):
    """
    Creates a PDF document containing transaction data.

    Args:
        transactions (list): List of transaction data.
        filepath (str): Path to save the PDF file.

    Returns:
        None
    """
    doc = SimpleDocTemplate(filepath, pagesize=A3, encrypt=pdfencrypt.StandardEncryption(
        dob, canPrint=1))  # Keep DOB as password for PDF
    elements = []
    heading_style = getSampleStyleSheet()["Heading1"]
    heading_text = "Statement for: "+user_name+f" for the {product_type} "+product_id
    heading_paragraph = Paragraph(heading_text, heading_style)
    elements.append(heading_paragraph)

    # Header row for the table
    col_headers = ["Transaction ID", "Amount Credit",
                   "Amount Debit", "Transaction Date", "Balance"]
    data = [col_headers]  # Start with headers

    # Add transaction data to the table
    for transaction in transactions:
        transaction_data = [
            transaction['transaction_id'],
            str(transaction['amount_credit']),
            str(transaction['amount_debit']),
            transaction['transaction_date'],
            str(round(transaction['balance'],2))
        ]
        data.append(transaction_data)

    # Create the table
    table = Table(data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ])
    table.setStyle(style)

    # Add table to elements
    elements.append(table)

    # Build PDF
    doc.build(elements)


@main.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    """
    Handles viewing transactions for a user's products.

    Returns:
        str: Rendered HTML content displaying transactions.
    """
    # Get the user's products/accounts
    user_products = Product.query.filter_by(user_id=current_user.id).all()

    transactions = []  # Initialize an empty list for transactions
    print(request.method)
    if request.method == 'POST':
        # Get the selected product_id from the form
        selected_product_id = request.form.get('product_id')

        # Get the latest 10 transactions for the selected product
        transactions = Transactions.query.filter_by(product_id=selected_product_id)\
            .order_by(Transactions.transaction_date.desc()).limit(10).all()
        transactions_list = [{'transaction_id': t.transaction_id,
                              'amount_credit': t.amount_credit, 'amount_debit': t.amount_debit,
                              'transaction_date': t.transaction_date.strftime('%Y-%m-%d %H:%M:%S'), 'balance': t.balance}
                             for t in transactions]
        return render_template('transactions.html', products=user_products, selected_product_id=selected_product_id, transactions=transactions_list)

    # Handle GET request
    return render_template('transactions.html', products=user_products, transactions=transactions)

@main.route('/pay_credit_card', methods=['GET', 'POST'])
@login_required
def pay_credit_card():
    if request.method == 'POST':
        amount_to_pay = float(request.form.get('amount_to_pay'))
        bank_account_id = request.form.get('bank_account_number')
        credit_card_number = request.form.get('credit_card_number')

        # Fetch the user's bank account and available balance
        bank_account = Product.query.filter_by(user_id=current_user.id, product_type='SB').first()
        bank_balance = bank_account.current_balance if bank_account else 0
        print("zero check")
        print(amount_to_pay, float(bank_balance))
        print(bank_account_id, credit_card_number)
        if amount_to_pay > float(bank_balance):
            flash('Balance not sufficient to process payment.')
            return redirect(url_for('main.pay_credit_card'))
        # Prepare data for the JSON request to add bank transaction
        print("first check")
        bank_transaction_data = {
            'product_id': bank_account_id,
            'amount_debit': amount_to_pay,
            'description': 'Debit for Credit Card Payment'
        }
        # Make an internal route call to add the bank transaction
        response_bank = requests.post('http://127.0.0.1:5000/add_transaction', json=bank_transaction_data)

        # Prepare data for the JSON request to add credit card transaction
        credit_card_transaction_data = {
            'product_id': credit_card_number,  # Assuming credit card number is used as the product_id
            'amount_credit': amount_to_pay,
            'description': 'Credit for Credit Card Payment'
        }

        # Make an internal route call to add the credit card transaction
        response_credit_card = requests.post('http://127.0.0.1:5000/add_transaction', json=credit_card_transaction_data)

        if response_bank.status_code == 201 and response_credit_card.status_code == 201:
            flash('Credit card bill successfully paid!')
            return redirect(url_for('main.transactions'))
        else:
            flash('Error occurred while processing the payment.')
            return redirect(url_for('main.pay_credit_card'))

    # Fetch the user's bank account and available balance
    bank_account = Product.query.filter_by(user_id=current_user.id, product_type='SB').first()
    bank_balance = bank_account.current_balance if bank_account else 0

    # Fetch the credit card details and outstanding amount
    credit_card = Product.query.filter_by(user_id=current_user.id, product_type='CC').first()
    credit_card_number = credit_card.product_id if credit_card else None
    outstanding_amount = credit_card.current_due if credit_card else 0

    return render_template('pay_credit_card.html', bank_account=bank_account, bank_balance=bank_balance,
                           credit_card_number=credit_card_number, outstanding_amount=-1*outstanding_amount)


@main.route('/createAndSendPDF', methods=['POST'])
@login_required
def create_and_send_pdf():
    """
    Creates a PDF from transaction data and sends it via SMS.

    Returns:
        str: JSON response with a success message or an error message.
    """
    try:
        # Get the transaction count and selected product ID from the request data
        # Default to 10 if not provided
        transaction_count = int(request.json.get('transaction_count', 10))
        selected_product_id = request.json.get(
            'selected_product', "")  # Default to empty if not provided

        print(transaction_count, selected_product_id)

        # Retrieve transactions based on the selected product ID and transaction count
        transactions = Transactions.query.filter_by(product_id=selected_product_id) \
            .order_by(Transactions.transaction_date.desc()).limit(transaction_count).all()

        # Prepare transaction data for PDF creation
        transactions_list = [{'transaction_id': t.transaction_id,
                              'amount_credit': t.amount_credit, 'amount_debit': t.amount_debit,
                              'transaction_date': t.transaction_date.strftime('%Y-%m-%d %H:%M:%S'), 'balance': t.balance}
                             for t in transactions]

        # Generate a unique PDF file path
        outfilepath = str(uuid.uuid4()) + ".pdf"
        user_id = current_user.id
        dob = current_user.dob
        product = Product.query.filter_by(product_id=selected_product_id).first()
        product_type = product.product_type
        # Create the PDF and upload it to S3
        try:
            create_pdf(transactions_list, outfilepath, dob, current_user.name, selected_product_id, product_type)
        except Exception as e:
            return jsonify({"message": "PDF creation failed."}), 500
        url, success = upload_to_s3(outfilepath, outfilepath)
        print(url, success)
        if success:
            try:
                # Send SMS with the PDF URL
                print(user_id)
                cl = get_client()
                message=f"Dear Customer, please find your statement for {product_type} {selected_product_id}: {url}"
                resp = send_sms(client=cl, src_ph=os.environ.get(
                    "PLIVO_NUM"), dst_ph=current_user.contact_number, msg=message)
                print(resp)
                # Sending a 200 confirmation response with a flash message
                flash(
                    f'PDF creation and SMS send request received for {transaction_count} transactions.', 'success')
            except Exception as e:
                flash(f'SMS sending failed.')
                return jsonify({"message": "SMS sending failed."}), 501

            return jsonify({"message": "PDF creation and SMS send request received."}), 200
        else:
            return jsonify({"message": "PDF upload failed."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route('/receive_sms/', methods=['GET', 'POST'])
def inbound_sms():
    """
    Handles inbound SMS messages.

    Returns:
        str: Response to the inbound SMS.
    """
    from_number = request.values.get('From')
    to_number = request.values.get('To')
    text = request.values.get('Text')
    print('Message received - From: %s, To: %s, Text: %s' %
          (from_number, to_number, text))
    return 'Message Received'


def upload_to_s3(awsfilepath, localfilepath):
    """
    Uploads a file to an Amazon S3 bucket.

    Args:
        awsfilepath (str): Path for the file in the S3 bucket.
        localfilepath (str): Local path of the file to be uploaded.

    Returns:
        str: URL of the uploaded file or an error message.
    """
    AWS_REGION = os.environ.get('AWS_REGION')
    AWS_ACCESS_ID = os.environ.get('AWS_ACCESS_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')

    try:
        # Creating a resource for 's3'
        s3_resource = boto3.resource(
            's3',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        # Upload a file to S3 bucket
        s3_resource.Bucket(S3_BUCKET).put_object(
            Key=awsfilepath,
            Body=open(localfilepath, 'rb')
        )

        # Creating a client for 's3'
        s3_client = boto3.client(
            's3',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        try:
            # Check if the file was uploaded successfully
            s3_client.head_object(Bucket=S3_BUCKET, Key=awsfilepath)
            print("File was uploaded successfully")
            # Generate the URL to get 'key-name' from 'bucket-name'
            url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': S3_BUCKET,
                    'Key': awsfilepath
                }
            )
            return url, True

        except ClientError:
            # The file wasn't found.
            return "File was not found in the bucket. Upload failed.", False
    except NoCredentialsError:
        return "No AWS credentials were found", False
