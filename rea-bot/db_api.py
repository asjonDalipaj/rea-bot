from logger import setup_logger
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import json


# Set up loggers for db_api and ai_scraper
db_api_logger = setup_logger('db_api_logger', './logs/api_logfile.log')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ads.db'
db = SQLAlchemy(app)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String, nullable=False)
    price = db.Column(db.String, nullable=False)
    area = db.Column(db.String, nullable=False)
    bedrooms = db.Column(db.String, nullable=False)
    energy_label = db.Column(db.String, nullable=False)
    ad_link = db.Column(db.String, nullable=False)
    furnished = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            'address': self.address,
            'price': self.price,
            'area': self.area,
            'bedrooms': self.bedrooms,
            'energy_label': self.energy_label,
            'ad_link': self.ad_link,
            'furnished': self.furnished
        }


def load_jsonl_into_db(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line.strip())
            listing = Listing(**entry)
            db.session.add(listing)
    db.session.commit()

with app.app_context():

    db.create_all()
    # Call this function with the path to your JSONL file the first time you run the app
    load_jsonl_into_db('./results/results_utrecht.jsonl')

    db_api_logger.info('DB API started.')

@app.route('/ads', methods=['GET'])
def ads():
    # Retrieve query parameters
    address_query = request.args.get('address', '')
    ad_link_query = request.args.get('ad_link', '')

    # Base query
    query = Listing.query

    # Filter by address if the address parameter is provided
    if address_query:
        query = query.filter(Listing.address.like(f"%{address_query}%"))

    # Filter by ad_link if the ad_link parameter is provided
    if ad_link_query:
        query = query.filter(Listing.ad_link == ad_link_query)

    # Execute the query and return the results
    results = query.all()
    return jsonify([listing.to_dict() for listing in results])

@app.route('/ads', methods=['POST'])
def create_ad():
    try:
        data = request.get_json()
        new_ad = Listing(**data)
        db.session.add(new_ad)
        db.session.commit()
        return jsonify(new_ad.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        db_api_logger.error(f"Error creating ad: {e}")
        return jsonify({"message": "Failed to create ad", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)