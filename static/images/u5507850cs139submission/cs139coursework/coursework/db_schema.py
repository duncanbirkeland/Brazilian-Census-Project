from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import delete
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash
from eventbyte import login_manager
from datetime import datetime
import os
# create the database interface
superpasskey = 'Thisisasecretpassword123'
db = SQLAlchemy()
class Event(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(50), unique=False)
    timedate = db.Column(db.DateTime, unique=False)
    duration = db.Column(db.String(30), unique = False)
    capacity = db.Column(db.Integer, unique = False)
    location = db.Column(db.String(50), unique = False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cancelled = db.Column(db.Integer)
    tickets_allocated = db.Column(db.Integer)
    tickets = relationship('Ticket', backref = "event")
    price = db.Column(db.Integer)
    #Creates a relationship between tickets

    def __init__(self, name,timedate, duration, capacity, location, price):
        self.name = name
        self.timedate = timedate
        self.duration = duration
        self.capacity = capacity
        self.location = location
        self.tickets_allocated = 0
        self.cancelled = False
        self.price = price
        #Sets all the properties to what is inputted by the user and default a new event to have no-tickets allocated and to not be cancelled


class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True)
    passhash = db.Column(db.String(100), unique=False)
    is_super = db.Column(db.Boolean)
    #Has a field to show whether a user is super
    authenticator_token = db.Column(db.String(64), unique = True)
    verified = db.Column(db.Boolean)
    credit = db.Column(db.Integer)
    events = relationship('Event', backref = 'user')
    tickets = relationship('Ticket', backref = 'user')

    #Creates a relationship
    def __init__(self, username, passhash, is_super, authenticator_token):  
        self.credit = 100
        self.username=username
        self.passhash=passhash
        self.is_super=is_super
        self.authenticator_token = authenticator_token
        self.verified = False
        #Sets the user to not be verified when an account is created and sets the authenticator_token as well as all other field
        
@login_manager.user_loader
def get_user(user_id):
    return User.query.filter_by(id = user_id).first()
    #Loads the user by id

def get_Super_User(user_id):
    return Superuser.query.filter_by(id=user_id).first()

class Superuser(User):
    def addEvent(self, name, duration, starttimedate, capacity, location, price):
        print(starttimedate)
        db.session.add(Event(name, datetime.strptime(starttimedate, "%Y-%m-%dT%H:%M"), duration, capacity, location, price ))
        addTransaction(f"{name} was added at {datetime.now()}")
        #Create a new event with allf"{os.getlogin()}@dcs.warwick.ac.uk"

    def deleteEvent(self, id):
        itemtocancel = Event.query.filter_by(id=id).first()
        addTransaction(f"{itemtocancel.name} was cancelled at {datetime.now()}")
        #Sets the cancel field to be true and create a transaction saying this event has been cancelled
        itemtocancel.cancelled = True
        db.session.commit()

    def modifyCapacity(self, id, capacity):
        itemtoChange = Event.query.filter_by(id=id).first()
        itemtoChange.capacity = capacity
        db.session.commit()
    #Encapsulate all superuser functions into a superuser class so that the superuser class has to be accessed to modify events
        
class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    barcode = db.Column(db.Integer)
    #Creates the ticket class with foreign keys to the user and event that the ticket is for as well as a barcode
    def __init__(self, user_id, event_id, barcode):
        self.user_id = user_id
        self.event_id = event_id
        self.barcode = barcode



class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    stringoftransaction = db.Column(db.String(100))
    def __init__(self, stringoftransaction):
        self.stringoftransaction = stringoftransaction
    #Create a transation with an id and a string

def dbinit():
    add_user(f"{os.getlogin()}@dcs.warwick.ac.uk",  generate_password_hash(superpasskey), True, 0)
    User.query.filter_by(username = f"{os.getlogin()}@dcs.warwick.ac.uk").first().verified = True
    db.session.commit()


def getIdByName(name):
    return User.query.filter_by(username=name).first().id
    #Gets the id of a user via the name

def add_user(name, password, is_super, token):
    if (is_super):
        usertoadd = Superuser(name, password, True, token)
    else:
        usertoadd = User(name, password, False, token)
    db.session.add(usertoadd)
    db.session.commit()
    #Adds a user to the database with the name password and authentication token, if the user is a superuser set superuser to be true
    
def getHash(name):
    user = User.query.filter_by(username=name).first()
    if user is not None:
        return user.passhash
    else:
        return "None"
    #If the user exists get the hashedpassword
    
def hasTicket(user_id, event_id):
    if Ticket.query.filter_by(user_id=user_id, event_id=event_id).first() is not None:
        return 1
    return 0
    #Returns 1 if there exists a ticket with a given user_id and event_id and 0 otherwise

def return_event_dictionary(currentid, event):
    return {
            'id': event.id,
            'name': event.name,
            'duration': event.duration,
            'capacity': event.capacity,
            'location': event.location,
            'timedate': str(event.timedate),
            'tickets_allocated': event.tickets_allocated,
            'has_ticket': hasTicket(currentid, event.id),
            'cancelled': event.cancelled,
            'price': event.price
    }
    #Returns a dictionary for all attributes of an event to be used as a json file
def getAllEvents():
    return Event.query.filter(Event.timedate > datetime.now()).all()
    #Returns all future events

def addTicket(userid, eventid, barcode):
    ticket = Ticket(userid, eventid, barcode)
    db.session.add(ticket)
    db.session.commit()
    addTransaction(f"A ticket for {Event.query.filter_by(id=eventid).first().name} has been assigned to {User.query.filter_by(id=userid).first().username} at {datetime.now()}")

    #Adds a new ticket to the table and create a transaction saying who the tickets were for

def addTransaction(entrystring):
    newtransaction = Transaction(entrystring)
    db.session.add(newtransaction)
    print(entrystring)
    db.session.commit()

    #Creates a new transaction