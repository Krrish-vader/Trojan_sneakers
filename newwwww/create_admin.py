from flask import Flask
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/ecommerce'
mongo = PyMongo(app)

def create_admin():
    admin = {
        'username': 'admin',
        'password': generate_password_hash('admin123')  # Change this password
    }
    
    # Check if admin already exists
    existing_admin = mongo.db.admins.find_one({'username': admin['username']})
    if existing_admin:
        print("Admin user already exists!")
        return
    
    # Create admin user
    mongo.db.admins.insert_one(admin)
    print("Admin user created successfully!")

if __name__ == '__main__':
    create_admin() 