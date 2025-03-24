from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'

# Configure MongoDB
app.config['MONGO_URI'] = 'mongodb://localhost:27017/ecommerce'
mongo = PyMongo(app)

# Configure upload folder
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Make settings available to all templates
@app.context_processor
def inject_settings():
    settings = mongo.db.settings.find_one() or {}
    return dict(
        site_settings=settings,
        now=datetime.now()
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Admin middleware
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            flash('Please log in as admin first')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_cart(user_id):
    """Fetch user's cart items from MongoDB."""
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return user.get('cart', []) if user else []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/products')
def products():
    products_list = mongo.db.products.find()
    return render_template('products.html', products=products_list)

@app.route('/productdetails/<product_id>')
def productdetails(product_id):
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    return render_template('productdetails.html', product=product)

@app.route('/cart')
def cart():
    return render_template('cart.html')

@app.route('/account')
def account():
    return render_template('account.html')

@app.route('/checkout')
def checkout():
    return render_template('checkout.html')

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        data = request.json
        order = {
            'user_id': session.get('user_id'),
            'customer_info': {
                'name': data['name'],
                'email': data['email'],
                'phone': data['phone'],
                'address': data['address'],
                'city': data['city'],
                'state': data['state'],
                'pincode': data['pincode']
            },
            'payment_info': {
                'method': data['payment_method'],
                'payment_id': data.get('payment_id', '')  # For UPI or card payments
            },
            'items': data['items'],
            'total_amount': data['total_amount'],
            'order_date': datetime.now(),
            'status': 'pending'
        }
        
        # Insert the order into MongoDB
        result = mongo.db.orders.insert_one(order)
        
        return jsonify({
            'success': True,
            'message': 'Order placed successfully!',
            'order_id': str(result.inserted_id)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Failed to place order. Please try again.'
        }), 500

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        data = request.form
        admin = mongo.db.admins.find_one({'username': data['username']})
        if admin and check_password_hash(admin['password'], data['password']):
            session['admin'] = str(admin['_id'])
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error='Invalid credentials')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    products = list(mongo.db.products.find())
    total_products = mongo.db.products.count_documents({})
    total_orders = mongo.db.orders.count_documents({})
    total_users = mongo.db.users.count_documents({})
    low_stock_products = mongo.db.products.count_documents({'stock': {'$lt': 10}})
    
    # Get recent orders and convert to list
    recent_orders = list(mongo.db.orders.find().sort('order_date', -1).limit(5))
    
    return render_template('admin/dashboard.html', 
                         products=products,
                         total_products=total_products,
                         total_orders=total_orders,
                         total_users=total_users,
                         low_stock_products=low_stock_products,
                         recent_orders=recent_orders)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    try:
        # Get orders from MongoDB and convert cursor to list
        cursor = mongo.db.orders.find().sort('order_date', -1)
        orders = []
        
        if cursor:
            for order in cursor:
                if order:  # Ensure order exists
                    # Convert ObjectId to string for JSON serialization
                    order['_id'] = str(order['_id'])
                    
                    # Ensure all required fields exist
                    if 'customer_info' not in order:
                        order['customer_info'] = {}
                    if 'items' not in order:
                        order['items'] = []
                    if 'total_amount' not in order:
                        order['total_amount'] = 0
                    if 'status' not in order:
                        order['status'] = 'pending'
                    if 'order_date' not in order:
                        order['order_date'] = datetime.now()
                    
                    # Process items
                    processed_items = []
                    for item in order.get('items', []):
                        if item:  # Ensure item exists
                            processed_item = {
                                'name': item.get('name', 'N/A'),
                                'quantity': int(item.get('quantity', 0)),
                                'price': float(item.get('price', 0))
                            }
                            processed_items.append(processed_item)
                    order['items'] = processed_items
                    
                    orders.append(order)
        
        return render_template('admin/orders.html', orders=orders)
    except Exception as e:
        flash(f'Error loading orders: {str(e)}')
        return render_template('admin/orders.html', orders=[])

@app.route('/admin/update_order_status/<order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    try:
        new_status = request.form.get('status')
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': new_status}}
        )
        
        flash('Order status updated successfully!')
        return redirect(url_for('admin_orders'))
    except Exception as e:
        flash(f'Error updating order status: {str(e)}')
        return redirect(url_for('admin_orders'))

@app.route('/admin/users')
@admin_required
def admin_users():
    # Convert cursor to list
    users = list(mongo.db.users.find())
    return render_template('admin/users.html', users=users)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        try:
            settings = {
                'site_name': request.form.get('site_name'),
                'site_description': request.form.get('site_description'),
                'contact_email': request.form.get('contact_email'),
                'contact_phone': request.form.get('contact_phone'),
                'address': request.form.get('address'),
                'social_media': {
                    'facebook': request.form.get('facebook'),
                    'twitter': request.form.get('twitter'),
                    'instagram': request.form.get('instagram')
                }
            }
            
            # Update or insert settings
            mongo.db.settings.update_one({}, {'$set': settings}, upsert=True)
            flash('Settings updated successfully!')
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}')
            
    # Get current settings
    settings = mongo.db.settings.find_one() or {}
    return render_template('admin/settings.html', settings=settings)

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    return render_template('admin/analytics.html')

@app.route('/api/admin/analytics/revenue', methods=['GET'])
@admin_required
def get_revenue_data():
    try:
        period = request.args.get('period', 'daily')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Start and end dates are required'}), 400
        
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format'}), 400
        
        match_query = {'order_date': {'$gte': start_date, '$lte': end_date}}
        
        if period == 'daily':
            group_id = {'$dateToString': {'format': '%Y-%m-%d', 'date': '$order_date'}}
        elif period == 'weekly':
            group_id = {
                'year': {'$year': '$order_date'},
                'week': {'$week': '$order_date'}
            }
        else:  # monthly
            group_id = {'$dateToString': {'format': '%Y-%m', 'date': '$order_date'}}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {
                '_id': group_id,
                'revenue': {'$sum': '$total_amount'}
            }},
            {'$sort': {'_id': 1}}
        ]
        
        revenue_data = list(mongo.db.orders.aggregate(pipeline))
        
        # Format the data for weekly grouping
        if period == 'weekly':
            revenue_data = [{
                '_id': f"{item['_id']['year']}-W{item['_id']['week']}",
                'revenue': item['revenue']
            } for item in revenue_data]
        
        return jsonify({'success': True, 'data': revenue_data})
    
    except Exception as e:
        print(f"Error in get_revenue_data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/analytics/orders', methods=['GET'])
@admin_required
def get_order_stats():
    try:
        period = request.args.get('period', 'daily')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Start and end dates are required'}), 400
        
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format'}), 400
        
        match_query = {'order_date': {'$gte': start_date, '$lte': end_date}}
        
        if period == 'daily':
            group_id = {'$dateToString': {'format': '%Y-%m-%d', 'date': '$order_date'}}
        elif period == 'weekly':
            group_id = {
                'year': {'$year': '$order_date'},
                'week': {'$week': '$order_date'}
            }
        else:  # monthly
            group_id = {'$dateToString': {'format': '%Y-%m', 'date': '$order_date'}}
        
        pipeline = [
            {'$match': match_query},
            {'$group': {
                '_id': group_id,
                'count': {'$sum': 1}
            }},
            {'$sort': {'_id': 1}}
        ]
        
        order_data = list(mongo.db.orders.aggregate(pipeline))
        
        # Format the data for weekly grouping
        if period == 'weekly':
            order_data = [{
                '_id': f"{item['_id']['year']}-W{item['_id']['week']}",
                'count': item['count']
            } for item in order_data]
        
        return jsonify({'success': True, 'data': order_data})
    
    except Exception as e:
        print(f"Error in get_order_stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/analytics/top-products', methods=['GET'])
@admin_required
def get_top_products():
    try:
        period = request.args.get('period', 'week')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Start and end dates are required'}), 400
        
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format'}), 400
        
        match_query = {'order_date': {'$gte': start_date, '$lte': end_date}}
        
        pipeline = [
            {'$match': match_query},
            {'$unwind': '$items'},
            {'$group': {
                '_id': '$items.product_id',
                'total_sold': {'$sum': '$items.quantity'},
                'revenue': {'$sum': {'$multiply': ['$items.price', '$items.quantity']}},
                'name': {'$first': '$items.name'}
            }},
            {'$sort': {'revenue': -1}},
            {'$limit': 5}
        ]
        
        top_products = list(mongo.db.orders.aggregate(pipeline))
        
        # Format the data
        formatted_products = []
        for product in top_products:
            try:
                product_id = ObjectId(product['_id'])
                prod_info = mongo.db.products.find_one({'_id': product_id})
                
                formatted_products.append({
                    'id': str(product['_id']),
                    'name': prod_info.get('name', 'Unknown Product') if prod_info else product.get('name', 'Unknown Product'),
                    'revenue': float(product.get('revenue', 0)),
                    'total_sold': int(product.get('total_sold', 0))
                })
            except Exception as e:
                print(f"Error processing product {product['_id']}: {str(e)}")
                continue
        
        return jsonify({'success': True, 'data': formatted_products})
    
    except Exception as e:
        print(f"Error in get_top_products: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/add_product', methods=['POST'])
@admin_required
def add_product():
    try:
        if 'image' not in request.files:
            flash('No image file')
            return redirect(url_for('admin_dashboard'))
        
        file = request.files['image']
        if file.filename == '':
            flash('No selected file')
            return redirect(url_for('admin_dashboard'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            product = {
                'name': request.form.get('name', ''),
                'price': float(request.form.get('price', 0)),
                'stock': int(request.form.get('stock', 0)),
                'image': filename
            }
            
            mongo.db.products.insert_one(product)
            flash('Product added successfully!')
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid file type')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error adding product: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_product/<product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    try:
        if request.method == 'GET':
            product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
            if not product:
                flash('Product not found')
                return redirect(url_for('admin_dashboard'))
            return render_template('admin/edit_product.html', product=product)
        else:
            # Handle POST request
            name = request.form.get('name')
            price = float(request.form.get('price'))
            stock = int(request.form.get('stock'))
            
            # Update product in MongoDB
            mongo.db.products.update_one(
                {'_id': ObjectId(product_id)},
                {'$set': {
                    'name': name,
                    'price': price,
                    'stock': stock
                }}
            )
            
            flash('Product updated successfully')
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Error updating product: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<product_id>')
@admin_required
def delete_product(product_id):
    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if product and product.get('image'):
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image'])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    mongo.db.products.delete_one({'_id': ObjectId(product_id)})
    flash('Product deleted successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        # Check if user already exists
        existing_user = mongo.db.users.find_one({'email': data['email']})
        if existing_user:
            return jsonify({'message': 'Email already registered'}), 400
        
        # Create new user
        hashed_password = generate_password_hash(data['password'])
        new_user = {
            'name': data['name'],
            'email': data['email'],
            'password': hashed_password,
            'cart': [],
            'created_at': datetime.now()
        }
        
        # Insert user into database
        result = mongo.db.users.insert_one(new_user)
        
        if result.inserted_id:
            return jsonify({
                'message': 'User registered successfully',
                'user_id': str(result.inserted_id)
            }), 201
        else:
            return jsonify({'message': 'Registration failed'}), 400
            
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return jsonify({'message': 'An error occurred during registration'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        user = mongo.db.users.find_one({'email': data['email']})
        
        if user and check_password_hash(user['password'], data['password']):
            # Set session
            session['user_id'] = str(user['_id'])
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'name': user['name'],
                    'email': user['email']
                }
            })
        return jsonify({'message': 'Invalid email or password'}), 401
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'message': 'An error occurred during login'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/update_stock/<product_id>', methods=['POST'])
def update_stock(product_id):
    try:
        data = request.get_json()
        quantity = int(data.get('quantity', 0))
        
        # Find the product
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Calculate new stock
        new_stock = product['stock'] - quantity
        if new_stock < 0:
            return jsonify({'error': 'Insufficient stock'}), 400
        
        # Update the stock
        mongo.db.products.update_one(
            {'_id': ObjectId(product_id)},
            {'$set': {'stock': new_stock}}
        )
        
        return jsonify({'success': True, 'new_stock': new_stock})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/check_stock/<product_id>')
def check_stock(product_id):
    try:
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            return jsonify({'error': 'Product not found', 'stock': 0}), 404
        return jsonify({'stock': product['stock']})
    except Exception as e:
        return jsonify({'error': str(e), 'stock': 0}), 500

if __name__ == '__main__':
    app.run(debug=True)