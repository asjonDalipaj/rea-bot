import os
from logger import setup_logger
from dotenv import load_dotenv
from telegram import Bot
from quart import Quart, jsonify, request
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.future import select

# Initialize Quart app
app = Quart(__name__)

# Configure the async database engine
DATABASE_URL = "sqlite+aiosqlite:///instance/listings.db"  # Replace with your database URL
engine = create_async_engine(DATABASE_URL, echo=True)

# Async session maker
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Base model
Base = declarative_base()

# Set up loggers for db_api and ai_scraper
db_api_logger = setup_logger('db_api_logger', './logs/api_logfile.log')

# Start the bot
load_dotenv()
tg_bot_hash = os.getenv('TG_BOT_HASH')

tg_bot = Bot(token=tg_bot_hash)

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, default='NoUsernameYet')
    chat_id = Column(String, nullable=True)

    def to_dict(self):
        return {
            'username': self.username,
            'chat_id': self.chat_id
        }

class Filter(Base):
    __tablename__ = 'filter'
    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('user.id'), nullable=False)
    # Todo - make these two nullable
    furnished = Column(String, nullable=False)
    including_bills = Column(String, nullable=False)
    #
    min_price = Column(String, nullable=True)
    max_price = Column(String, nullable=True)
    min_sqm = Column(String, nullable=True)
    max_sqm = Column(String, nullable=True)
    min_bedroom = Column(Integer, nullable=True, default=1)
    city = Column(String, nullable=False)
    
    user = relationship('User', backref='filter')

    def to_dict(self):
        return {
            'userid': self.userid,
            'furnished': self.furnished,
            'including_bills': self.including_bills,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'min_sqm': self.min_sqm,
            'max_sqm': self.max_sqm,
            'min_bedroom': self.min_bedroom,
            'city': self.city,
        }

class Listing(Base):
    __tablename__ = 'listing'
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    price = Column(String, nullable=False)
    area = Column(String, nullable=False)
    bedrooms = Column(String, nullable=False)
    energy_label = Column(String, nullable=False)
    listing_link = Column(String, nullable=False)
    furnished = Column(String, nullable=False, server_default='no')
    including_bills = Column(String, nullable=False, server_default='no')

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

class Message(Base):
    __tablename__ = 'message'  # Correct table name for messages
    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('user.id'), nullable=False, unique=True)  # Enforce unique messages per user
    message = Column(String, nullable=True)
    
    # Correct the back reference to reflect the relationship
    # If you want the relationship to represent "one-to-one", use uselist=False
    user = relationship('User', backref='message', uselist=False)

    def to_dict(self):
        return {
            'userid': self.userid,
            'message': self.message
        }

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# APIs
@app.route('/listings', methods=['GET'])
async def listings():
    # Retrieve query parameters
    address_query = request.args.get('address', '')
    listing_link_query = request.args.get('listing_link', '')

    async with async_session() as session:
        # Base query using SQLAlchemy 2.0 style
        stmt = select(Listing)

        # Filter by address if the address parameter is provided
        if address_query:
            stmt = stmt.filter(Listing.address.like(f"%{address_query}%"))

        # Filter by listing_link if the listing_link parameter is provided
        if listing_link_query:
            stmt = stmt.filter(Listing.listing_link == listing_link_query)

        # Execute the query and return the results
        results = await session.execute(stmt)
        listings = results.scalars().all()
    
    return jsonify([listing.to_dict() for listing in listings])

@app.route('/listings', methods=['POST'])
async def create_listing():
    try:
        data = await request.get_json()
        new_listing = Listing(**data)

        async with async_session() as session:
            async with session.begin():
                session.add(new_listing)
            await session.commit()

        return jsonify(new_listing.to_dict()), 201
    except Exception as e:
        await session.rollback()
        # Assuming you have set up logging as in Flask
        # Replace `db_api_logger.error` with your logger's name
        db_api_logger.error(f"Error creating listing: {e}")
        return jsonify({"message": "Failed to create listing", "error": str(e)}), 500
    
@app.route('/notify', methods=['POST'])
async def notify():
    data = await request.get_json()
    user = data['user']
    listing_data = data['listing']
    
    listing_msg, applying_msg = await create_notification_message(user['id'], listing_data)
    
    # Send a message asynchronously
    await send_telegram_message(user['chat_id'], listing_msg, applying_msg)
    
    return jsonify({"message": "Notification sent"}), 200

@app.route('/users', methods=['GET'])
async def get_users():
    async with async_session() as session:  # Replace `async_session` with your actual sessionmaker
        result = await session.execute(select(User))
        users = result.scalars().all()
        users_data = [
            {'id': user.id, 'username': user.username, 'chat_id': user.chat_id}
            for user in users
        ]
        return jsonify(users_data), 200
    
@app.route('/users/<string:chat_id>', methods=['GET'])
async def get_user_by_chat_id(chat_id):
    async with async_session() as session:
        # Assuming User is your SQLAlchemy model and async_session is set up for async ORM operations
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if user:
            user_data = {
                'id': user.id,
                'username': user.username,
                'chat_id': user.chat_id
            }
            return jsonify(user_data), 200
        else:
            return jsonify({'message': 'User not found'}), 404

@app.route('/users', methods=['POST'])
async def add_user():
    data = await request.get_json()
    username = data.get('username')
    chat_id = data.get('chat_id')

    if chat_id:
        async with async_session() as session:
            async with session.begin():
                user = await session.execute(select(User).filter_by(username=username))
                user = user.scalars().first()
                if not user:
                    user = User(username=username, chat_id=chat_id)
                    session.add(user)
                    await session.commit()
                    return jsonify({'message': 'User added successfully'}), 201
                else:
                    return jsonify({'message': 'User already exists'}), 200
    else:
        return jsonify({'message': 'Bad request, chat_id not provided'}), 400

@app.route('/users/<string:userid>/filters', methods=['GET'])
async def get_user_filters(userid):
    async with async_session() as session:
        # Assuming Filter is your SQLAlchemy model and async_session is set up for async ORM operations
        result = await session.execute(select(Filter).filter_by(userid=userid))
        user_filters = result.scalars().all()

    filters_data = [{
        'id': filter_.id,
        'furnished': filter_.furnished,
        'including_bills': filter_.including_bills,
        'min_price': filter_.min_price,
        'max_price': filter_.max_price,
        'min_sqm': filter_.min_sqm,
        'max_sqm': filter_.max_sqm,
        'min_bedroom': filter_.min_bedroom,
        'city': filter_.city
    } for filter_ in user_filters]  # Renamed to filter_ to avoid name clash with the built-in filter function

    return jsonify(filters_data), 200

@app.route('/filters', methods=['POST'])
async def create_filters():
    try:
        data = await request.get_json()
        new_filter = Filter(**data)

        async with async_session() as session:
            async with session.begin():
                session.add(new_filter)
            await session.commit()

        return jsonify(new_filter.to_dict()), 201
    except Exception as e:
        await session.rollback()
        db_api_logger.error(f"Error creating the filter: {e}")
        return jsonify({"message": "Failed to create listing", "error": str(e)}), 500

@app.route('/message', methods=['POST'])
async def create_message():
    try:
        data = await request.get_json()
        new_message = Message(**data)

        async with async_session() as session:
            async with session.begin():
                session.add(new_message)
            await session.commit()

        return jsonify(new_message.to_dict()), 201
    except Exception as e:
        await session.rollback()
        db_api_logger.error(f"Error creating the filter: {e}")
        return jsonify({"message": "Failed to create listing", "error": str(e)}), 500

async def get_applying_message_by_userid(userid):
    # Query the Message table for the applying message for the specified user
    async with async_session() as session:
        # Assuming Filter is your SQLAlchemy model and async_session is set up for async ORM operations
        result = await session.execute(select(Message).where(Message.userid == userid))
        applying_message = result.scalars().first()

    # If an applying message exists, return its content
    if applying_message:
        return applying_message.message
    else:
        applying_message = """
        "NOTE! This is a default message, change it to your needs - [ADDRESS] will be replaced with the address of the listing is being found.\n\n"
        "I'm looking for an apartment in Utrecht and I've found your listing at [ADDRESS].\n"
        "I would love to view this apartment!\n"
        f"My name is [YOUR NAME] and I am a [your profession]. My bruto income is €[your bruto] per month. I'm moving in by myself/with my partner.\n\n"
        "I'm available for a viewing as soon as it's possible. Could I come by for a viewing?\n\n"
        "You can reach me at +XX XXXXXXX or your.mail@gmail.com.\n\n"
        "Hope to hear from you!\n"
        "Kind regards,\n"""
        return None

# Function utilities
async def create_notification_message(userid, listing_data):
   # Send notification
    listing_msg = (
        f"🏄 Found new listing!\n"
        f"{listing_data['address']} - € {listing_data['price']} p/m - {listing_data['bedrooms']} bedroom(s) - {listing_data['area']} m2 - E/L: {listing_data['energy_label']}\n"
        f"{listing_data['listing_link']}"
    )

    # Ensure each line is stripped of leading/trailing whitespace
    listing_msg = "\n".join(line.strip() for line in listing_msg.splitlines())

    applying_msg = await get_applying_message_by_userid(userid)
    applying_msg = applying_msg.replace('[ADDRESS]', listing_data['address'])

    # Ensure each line is stripped of leading/trailing whitespace
    applying_msg = "\n".join(line.strip() for line in applying_msg.splitlines())
    return listing_msg, applying_msg

async def send_telegram_message(chat_id, listing_msg, applying_msg):
    # Send the messages to the channel
    await tg_bot.send_message(chat_id=chat_id, text=listing_msg)
    await tg_bot.send_message(chat_id=chat_id, text=applying_msg)

# Run the app
if __name__ == '__main__':
    app.run()

@app.before_serving
async def startup():
    await create_tables()