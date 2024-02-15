from logger import setup_logger
from flask import Flask, request, jsonify
import asyncio
import os
from sqlalchemy import create_engine, MetaData, Table
from telegram import Bot
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Config
# Read API key from a file and pass it to the function
load_dotenv()

# Prepend '-' for using channel ID
tg_channel_id = os.getenv('TG_CHANNEL_ID')
tg_channel_id = f'-{tg_channel_id}'

tg_bot_hash = os.getenv('TG_BOT_HASH')
# session_file = 'session'

tg_bot = Bot(token=tg_bot_hash)

# Set up loggers for db_api and ai_scraper
db_api_logger = setup_logger('db_api_logger', './logs/api_logfile.log')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///listings.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# For deleting tables
# engine = create_engine("sqlite:///instance/listings.db")
# metadata = MetaData()

class User(db.Model):
    userid = db.Column(db.String, primary_key=True)
    username = db.Column(db.String, nullable=False, default='NoUsernameYet')

    def to_dict(self):
        return {
            'userid': self.userid,
            'username': self.username
        }

class Filter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.String, db.ForeignKey('user.userid'), nullable=False)
    furnished = db.Column(db.String, nullable=False)
    including_bills = db.Column(db.String, nullable=False)
    min_price = db.Column(db.String, nullable=True)
    max_price = db.Column(db.String, nullable=True)
    min_sqm = db.Column(db.String, nullable=True)
    max_sqm = db.Column(db.String, nullable=True)
    
    user = db.relationship('User', backref=db.backref('filters', lazy=True))

    def to_dict(self):
        return {
            'user_id': self.userid,
            'furnished': self.furnished,
            'including_bills': self.including_bills,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'min_sqm': self.min_sqm,
            'max_sqm': self.max_sqm,
        }

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String, nullable=False)
    price = db.Column(db.String, nullable=False)
    area = db.Column(db.String, nullable=False)
    bedrooms = db.Column(db.String, nullable=False)
    energy_label = db.Column(db.String, nullable=False)
    listing_link = db.Column(db.String, nullable=False)
    furnished = db.Column(db.String, nullable=False)
    including_bills = db.Column(db.String, nullable=False, server_default='false')

    def to_dict(self):
        return {
            'address': self.address,
            'price': self.price,
            'area': self.area,
            'bedrooms': self.bedrooms,
            'energy_label': self.energy_label,
            'listing_link': self.listing_link,
            'furnished': self.furnished,
            'including_bills': self.including_bills
        }

with app.app_context():

    db.create_all()

    # new_filter = Filter(userid='OfficialAssa', furnished = 'true', including_bills = 'false',min_price = '500', max_price = '1400', min_sqm = None, max_sqm = None)
    
    # # Add the new user to the session
    # db.session.add(new_filter)

    # record_id = 3  # replace with the actual ID of the record you want to delete

    # # Find the record by ID
    # record_to_delete = db.session.query(Filter).get(record_id)

    # if record_to_delete:
    #     db.session.delete(record_to_delete)
    #     db.session.commit()

    # # Commit the session to write changes to the database
    # db.session.commit()

    # For deleting records
    # _alembic_tmp_filter = Table('_alembic_tmp_filter', metadata)

    # _alembic_tmp_filter.drop(engine)

    db_api_logger.info('DB API started.')

@app.route('/listings', methods=['GET'])
def listings():
    # Retrieve query parameters
    address_query = request.args.get('address', '')
    listing_link_query = request.args.get('listing_link', '')

    # Base query
    query = Listing.query

    # Filter by address if the address parameter is provided
    if address_query:
        query = query.filter(Listing.address.like(f"%{address_query}%"))

    # Filter by listing_link if the listing_link parameter is provided
    if listing_link_query:
        query = query.filter(Listing.listing_link == listing_link_query)

    # Execute the query and return the results
    results = query.all()
    return jsonify([listing.to_dict() for listing in results])

@app.route('/listings', methods=['POST'])
def create_listing():
    try:
        data = request.get_json()
        new_listing = Listing(**data)
        db.session.add(new_listing)
        db.session.commit()
        return jsonify(new_listing.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        db_api_logger.error(f"Error creating listing: {e}")
        return jsonify({"message": "Failed to create listing", "error": str(e)}), 500
    
@app.route('/notify', methods=['POST'])
def notify():
    data = request.json
    user_id = data['user_id']
    listing_data = data['listing_data']

    # # Implement logic to find the user's filters
    # user_filters = Filter.query.filter_by(user_id=user_id).first()

    # listing_msg, applying_msg = create_notification_message(listing_data)
    
    # if user_filters and does_listing_match_filters(listing_data, user_filters):
    #     asyncio.run(send_telegram_message(user_id, listing_msg, applying_msg))
    #     return jsonify({"status": "success", "message": "Notification sent"}), 200
    # else:
    #     return jsonify({"status": "success", "message": "No matching filters"}), 200
    
    listing_msg, applying_msg = create_notification_message(listing_data)

    asyncio.run(send_telegram_message(user_id, listing_msg, applying_msg))
    return jsonify({"status": "success", "message": "Notification sent"}), 200
    
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    users_data = [{'userid': user.userid, 'username': user.username} for user in users]  # Customize the fields as needed
    return jsonify(users_data), 200

@app.route('/users/userid/filters', methods=['GET'])
def get_user_filters(userid):
    user_filters = Filter.query.filter_by(userid=userid).all()
    filters_data = [{
        'id': filter.id,
        'furnished': filter.furnished,
        'including_bills': filter.including_bills,
        'min_price': filter.min_price,
        'max_price': filter.max_price,
        'min_sqm': filter.min_sqm,
        'max_sqm': filter.max_sqm
    } for filter in user_filters]
    return jsonify(filters_data), 200

# Function utilities
def create_notification_message(listing_data):
   # Send notification
    listing_msg = (
        f"🏄 Found new listing!\n"
        f"{listing_data['address']} - € {listing_data['price']} p/m - {listing_data['bedrooms']} bedroom(s) - {listing_data['area']} m2 - E/L: {listing_data['energy_label']}\n"
        f"{listing_data['listing_link']}"
    )

    # Ensure each line is stripped of leading/trailing whitespace
    listing_msg = "\n".join(line.strip() for line in listing_msg.splitlines())

    applying_msg = (
        f"I'm looking for an apartment in Utrecht and I've found your listing at {listing_data['address']}.\n"
        "I would love to view this apartment!\n"
        "My name is Asjon and I am a Software Engineer. My bruto income is €5800 per month. I'm moving in by myself.\n\n"
        "I'm available for a viewing as soon as it's possible. Could I come by for a viewing?\n\n"
        "You can reach me at +31 683715213 or asjon.dalipaj@gmail.com.\n\n"
        "Hope to hear from you!\n"
        "Kind regards,\n"
        "Asjon"
    )

    # Ensure each line is stripped of leading/trailing whitespace
    applying_msg = "\n".join(line.strip() for line in applying_msg.splitlines())
    return listing_msg, applying_msg

def does_listing_match_filters(listing_data, user_filters):
    # Here's a basic example of matching logic for price and area:
    listing_price = int(listing_data['price'])
    listing_area = int(listing_data['area'])
    
    filter_min_price = int(user_filters.min_price)
    filter_max_price = int(user_filters.max_price)
    filter_min_sqm = int(user_filters.min_sqm)
    filter_max_sqm = int(user_filters.max_sqm)

    # Here's an example of how you could check if the price and area are within user filters
    if listing_price >= filter_min_price and listing_price <= filter_max_price:
        if listing_area >= filter_min_sqm and listing_area <= filter_max_sqm:
            # Add more checks for other filters as necessary
            return True
    return False

def send_telegram_message(user_id, listing_msg, applying_msg):
    # Send the messages to the channel
    tg_bot.send_message(chat_id=user_id, text=listing_msg)
    tg_bot.send_message(chat_id=user_id, text=applying_msg)

if __name__ == '__main__':
    app.run(debug=False)