from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import json

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
    broker = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            'address': self.address,
            'price': self.price,
            'area': self.area,
            'bedrooms': self.bedrooms,
            'energy_label': self.energy_label,
            'broker': self.broker
        }


def load_jsonl_into_db(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line.strip())
            listing = Listing(**entry)
            db.session.add(listing)
    db.session.commit()

with app.app_context():
    # Call this function with the path to your JSONL file the first time you run the app
    db.drop_all()

    db.create_all()
    # Call this function with the path to your JSONL file the first time you run the app
    load_jsonl_into_db('./results/results_utrecht.jsonl')

@app.route('/ads', methods=['GET'])
def ads():
    address_query = request.args.get('address', '')
    
    # If no address query is provided, return all listings
    if not address_query:
        results = Listing.query.all()
    else:
        # If an address query is provided, filter listings by address
        results = Listing.query.filter(Listing.address.like(f"%{address_query}%")).all()
    
    return jsonify([listing.to_dict() for listing in results])

if __name__ == '__main__':
    app.run(debug=True)