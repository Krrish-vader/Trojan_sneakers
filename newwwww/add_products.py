from flask import Flask
from flask_pymongo import PyMongo
import os

app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/ecommerce'
mongo = PyMongo(app)

products = [
    {
        "name": "Jordan 1 Retro",
        "price": 400.00,
        "stock": 15,
        "image": "jordan1retroblue.jpg",
        "description": "Jordan 1 Retro Off-White University Blue sneakers"
    },
    {
        "name": "Nike Blazers",
        "price": 4500.00,
        "stock": 10,
        "image": "nikeblazer.jpg",
        "description": "Nike Blazers vintage style sneakers"
    },
    {
        "name": "Nike Dunk Low",
        "price": 2200.00,
        "stock": 12,
        "image": "nikedunklow.jpg",
        "description": "Nike Dunk Low classic black and white"
    },
    {
        "name": "Air Jordan Purple Ore",
        "price": 1800.00,
        "stock": 8,
        "image": "Airjordanpurpleorejpg.jpg",
        "description": "Air Jordan Purple Ore premium sneakers"
    },
    {
        "name": "Mcqueen Crocs",
        "price": 1200.00,
        "stock": 20,
        "image": "Mcqueen crocs.jpg",
        "description": "Lightning McQueen themed Crocs"
    },
    {
        "name": "Travis retro canary",
        "price": 180.00,
        "stock": 15,
        "image": "retro low travis scott canary.jpg",
        "description": "Travis Scott Nike yellow"
    },
    {
        "name": "Jordan low Black obsidian",
        "price": 650.00,
        "stock": 10,
        "image": "jordanlowblackdarkobsidian.jpg",
        "description": "Jordan Low Black Obsidian"
    },
    {
        "name": "New balance",
        "price": 600.00,
        "stock": 25,
        "image": "newbalancewhite.jpg",
        "description": "New Balance classic white and black"
    }
]

# Ensure uploads directory exists
os.makedirs('static/uploads', exist_ok=True)

# Copy images from static/images to static/uploads if they exist
def copy_images():
    for product in products:
        src_path = f'static/images/{product["image"]}'
        dst_path = f'static/uploads/{product["image"]}'
        if os.path.exists(src_path):
            import shutil
            shutil.copy2(src_path, dst_path)
            print(f"Copied {product['image']} to uploads folder")
        else:
            print(f"Warning: Image {product['image']} not found in static/images")

with app.app_context():
    # Copy images first
    copy_images()
    
    # Update products in database
    for product in products:
        mongo.db.products.update_one(
            {"name": product["name"]},
            {
                "$set": {
                    "image": product["image"],
                    "price": product["price"],
                    "stock": product["stock"],
                    "description": product["description"]
                }
            },
            upsert=True
        )
        print(f"Updated/Added {product['name']}")

print("Done updating products!") 