from . import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    """
    User model representing a user in the application.

    Attributes:
        id (int): Primary key for the User table.
        email (str): Email of the user (unique).
        password (str): Password of the user.
        name (str): Name of the user.
        contact_number (str): Contact number of the user.
        dob(date): Date of Birth of the user
        products (relationship): Relationship with Product table representing the products associated with the user.
    """
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    contact_number = db.Column(db.String(20))
    dob=db.Column(db.String(10), nullable=False)
    products = db.relationship('Product', backref='user', lazy=True)
    

class Product(db.Model):
    """
    Product model representing a product in the application.

    Attributes:
        product_id (str): Product ID (primary key for the Product table).
        user_id (int): User ID (foreign key referencing the User table).
        product_type (str): Type of the product (e.g., credit card, savings account).
        date_of_opening (datetime): Date of opening the product.
        current_balance (int): Current balance for the product.
        current_due (int): Current due for the product.
        payment_due_date (datetime): Payment due date for the product.
        transactions (relationship): Relationship with Transactions table representing the transactions associated with the product.
    """
    product_id = db.Column(db.String(6), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_type = db.Column(db.String(50), nullable=False)
    date_of_opening = db.Column(db.Date, nullable=False)
    current_balance = db.Column(db.Integer, default=0)
    current_due = db.Column(db.Integer, default=0)
    payment_due_date = db.Column(db.Date)
    transactions = db.relationship('Transactions', backref='product', lazy=True)


class Transactions(db.Model):
    """
    Transactions model representing a transaction in the application.

    Attributes:
        transaction_id (str): Transaction ID (primary key for the Transactions table).
        product_id (str): Product ID (foreign key referencing the Product table).
        amount_credit (float): Amount credited in the transaction.
        amount_debit (float): Amount debited in the transaction.
        transaction_date (datetime): Date and time of the transaction.
        balance (int): Balance after the transaction.
    """
    transaction_id = db.Column(db.String, primary_key=True)
    product_id = db.Column(db.String(6), db.ForeignKey('product.product_id'), nullable=False)
    amount_credit = db.Column(db.Float, nullable=False)
    amount_debit = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False)
    balance = db.Column(db.Integer, nullable=False)