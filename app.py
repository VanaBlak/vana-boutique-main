# Import necessary modules and classes from Flask and SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from config.config import Config
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError





# Create a Flask application
app = Flask(__name__)

# Set the URI for the MySQL database and disable modification tracking
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://bc84208eb7413d:93c94117@us-cluster-east-01.k8s.cleardb.net/heroku_981f35e8aa6d98f'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret'  # Set a secret key for session management

login_manager = LoginManager(app)


# Create a SQLAlchemy instance and a migration instance for the app
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define a User class that inherits from the SQLAlchemy Model
class User(db.Model, UserMixin):
    # Define columns for the User table
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    # Add this line to create a one-to-one relationship between User and Cart
    cart = db.relationship('Cart', backref='user', uselist=False)

    # Define methods for setting and checking the password using Werkzeug
    def set_password(self, password):
        self.password = password

    # Define a representation method for User instances
    def __repr__(self):
        return f'<User {self.username}>'

# Define a Product class
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)  # Assuming image URL can be nullable

   

    def __repr__(self):
        return f'<Product {self.product_name}>'

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cart_items = db.relationship('CartItem', backref='cart', lazy=True)

    def __repr__(self):
        return f'<Cart {self.id}>'

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    # Update the backref name to 'cart'
    # cart = db.relationship('Cart', backref='cart_items')
    product = db.relationship('Product', backref='cart_items')


    def __repr__(self):
        return f'<CartItem {self.id}>'



    

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        # If the user is logged in, display a personalized welcome message
        welcome_message = f'Welcome, {current_user.first_name} {current_user.last_name}!'
    else:
        # If the user is not logged in, display a default welcome message
        welcome_message = 'Welcome to Vana Boutique!'

    # Query all products from the Product table
    all_products = Product.query.all()

    return render_template('index.html', welcome_message=welcome_message, products=all_products)


@app.route('/logout')
@login_required
def logout():
    # Use Flask-Login's logout_user() function to log out the user
    logout_user()
    flash('Logout successful!', 'success')
    return redirect(url_for('login'))


@app.route('/about')
def aboutUs():
    return render_template('about.html')

@app.route('/checkout')
@login_required
def checkout():
    cart_items = current_user.cart.cart_items
    total_price = sum(cart_item.quantity * cart_item.product.price for cart_item in cart_items)
    return render_template('checkout.html', total_price=total_price)


# Inside the login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None  # Initialize error_message
    if request.method == 'POST':
        # Get user input from the form
        username = request.form['username']
        password = request.form['pass']

        # Check if the user is already authenticated
        if current_user.is_authenticated:
            flash('User is already logged in!', 'info')
            return redirect(url_for('index'))

        # Query the database to find the user with the given username
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            # If the user is found and the password is correct, log in the user
            login_user(user)

            # Check if the user has a cart, if not, create one
            if user.cart is None:
                user_cart = Cart(user=user)
                db.session.add(user_cart)
                db.session.commit()

            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            # If the user is not found or the password is incorrect, set the error message
            error_message = f'Login failed for username: {username}. Please check your credentials.'

    return render_template('login.html', error_message=error_message)




# Existing route
@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    try:
        # Get the product from the database based on product_id
        product = Product.query.get(product_id)

        # Check if the user has a cart
        if current_user.cart is None:
            # If the user doesn't have a cart, create one
            user_cart = Cart(user=current_user)
            db.session.add(user_cart)
            db.session.commit()  # Commit the cart creation

        # Check if the product is already in the user's cart
        existing_cart_item = CartItem.query.filter_by(cart=current_user.cart, product=product).first()

        if existing_cart_item:
            # If the product is already in the cart, update the quantity
            existing_cart_item.quantity += 1
        else:
            # If the product is not in the cart, create a new CartItem
            new_cart_item = CartItem(cart=current_user.cart, product=product, quantity=1)
            db.session.add(new_cart_item)

        # Commit the changes to the database
        db.session.commit()

        # Redirect to the cart page with cart details
        return redirect(url_for('cart'))
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Error adding product to cart'}), 500




# Existing route
@app.route('/cart')
@login_required
def cart():
    # Retrieve cart_items from the current user's cart
    cart_items = current_user.cart.cart_items

    # Assuming cart_items is a list of CartItem objects
    total_price = sum(cart_item.quantity * cart_item.product.price for cart_item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

    
@app.route('/remove-from-cart/<int:item_index>', methods=['POST'])
@login_required
def remove_from_cart(item_index):
    try:
        # Assuming cart_items is a list of CartItem objects
        cart_items = current_user.cart.cart_items

        # Check if the item_index is valid
        if 1 <= item_index <= len(cart_items):
            # Remove the item at the specified index (adjust for 0-based indexing)
            removed_item = cart_items.pop(item_index - 1)

            # Delete the CartItem from the database
            db.session.delete(removed_item)

            # Commit the changes to the database
            db.session.commit()

            return jsonify({'message': 'Item removed from cart successfully'})
        else:
            return jsonify({'message': 'Invalid item index'}), 400
    except SQLAlchemyError as e:
        print(f"Error: {e}")
        # Rollback changes in case of an error
        db.session.rollback()
        return jsonify({'message': 'Error removing item from cart'}), 500


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Get user input from the form
        first_name = request.form['firstname']
        last_name = request.form['lastname']
        username = request.form['username']
        password = request.form['pass']

        # Create a new user instance
        new_user = User(first_name=first_name, last_name=last_name, username=username)
        new_user.set_password(password)

        try:
            # Add the new user to the database
            db.session.add(new_user)
            db.session.commit()

            # Flash a success message
            flash('User successfully created! Please login.', 'success')

            # Redirect to the login page
            return redirect(url_for('login'))

        except Exception as e:
            # Flash an error message if there's an issue
            flash(f'Error creating user: {str(e)}', 'danger')

    return render_template('signup.html')

# Route to display products
@app.route('/products')
def products():
    # Query all products from the Product table
    all_products = Product.query.all()
    return render_template('products.html', products=all_products)

@app.route('/single-product/<int:product_id>', methods=['GET', 'POST'])
def single_product(product_id):
    # Query the product with the given product_id
    product = Product.query.get(product_id)

    if request.method == 'POST' and current_user.is_authenticated:
        # If the request is a POST and the user is authenticated, add the product to the cart
        quantity = int(request.form.get('quantity', 1))
        
        # Check if the user has a cart
        user_cart = current_user.cart

        if not user_cart:
            # If the user does not have a cart, create a new cart for the user
            user_cart = Cart(user=current_user)
            db.session.add(user_cart)
            db.session.commit()

        # Check if the product is already in the user's cart
        existing_cart_item = CartItem.query.filter_by(cart=user_cart, product=product).first()

        if existing_cart_item:
            # If the product is already in the cart, update the quantity
            existing_cart_item.quantity += quantity
        else:
            # If the product is not in the cart, create a new CartItem
            new_cart_item = CartItem(cart=user_cart, product=product, quantity=quantity)
            db.session.add(new_cart_item)

        # Commit the changes to the database
        db.session.commit()

        # Flash a success message
        flash(f'{product.product_name} added to your cart!', 'success')

        # Redirect the user back to the single product page
        return redirect(url_for('single_product', product_id=product_id))

    if product:
        return render_template('single-product.html', product=product)
    else:
        # Handle case where the product with the given ID is not found
        flash('Product not found!', 'danger')
        return redirect(url_for('products'))




# Run the application and create tables if the script is executed directly
if __name__ == '__main__':
    # Apply the migrations and create the tables within the application context
    with app.app_context():
        db.create_all()

    # Run the application in debug mode
    app.run(debug=True)
