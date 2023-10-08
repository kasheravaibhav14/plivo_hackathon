from flask import Blueprint, render_template, redirect, url_for, request, flash
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from flask_login import login_user, login_required, logout_user

# Create a Blueprint for authentication-related routes
auth = Blueprint('auth', __name__)

# Route for user login page
@auth.route('/login')
def login():
    return render_template('login.html')

# Route for handling user login (POST request)
@auth.route('/login', methods=['POST'])
def login_post():
    # Extract email, password, and remember from the request
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    # Fetch the user from the database based on the provided email
    user = User.query.filter_by(email=email).first()

    # Check if the user exists and the password matches
    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.')
        return redirect(url_for('auth.login'))  # Reload the page if login fails

    # Login the user and redirect to the main page
    login_user(user, remember=remember)
    return redirect(url_for('main.index'))

# Route for user signup page
@auth.route('/signup')
def signup():
    return render_template('signup.html')

# Route for handling user signup (POST request)
@auth.route('/signup', methods=['POST'])
def signup_post():
    # Extract user details from the request
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')
    contact = request.form.get('contact')
    dob=request.form.get('dob')
    print(dob, type(dob))

    # Check if the email already exists in the database
    user = User.query.filter_by(email=email).first()

    if user:
        flash('Email address already exists')
        return redirect(url_for('auth.signup'))  # Redirect to signup page if email exists

    # Create a new user with hashed password and add to the database
    new_user = User(email=email, name=name, password=generate_password_hash(password, method='sha256'), contact_number=contact, dob=dob)
    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('auth.login'))  # Redirect to login page after successful signup

# Route for user logout
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))  # Redirect to main page after logout
