from flask import Flask, render_template, url_for, request, redirect, session, send_from_directory, jsonify
from flask_mail import Mail, Message
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from barcode import EAN13
import random
from datetime import datetime
import secrets
app = Flask(__name__)
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'returnLogin'
#Sets any @login_required routes to redirect to the login page
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///eventbyte.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_USE_SENDMAIL'] = True
app.config['MAIL_SUPPRESS_SEND'] = False
#Set the routes of the database, sets send mail to be allowed, and allows emails to be sent

from db_schema import db, getIdByName, dbinit, get_user, add_user, getHash, User, Event, get_Super_User, getAllEvents, return_event_dictionary, addTicket, Ticket, addTransaction, Transaction
app.secret_key = 'Hellothere'
db.init_app(app)
mail = Mail(app)
resetdb =  False 
if resetdb:
    with app.app_context():
        db.drop_all()
        db.create_all()
        dbinit()
        #Recreates the table

        for filename in os.listdir('static'):
            if filename.endswith('.svg'):
                os.remove(os.path.join('static', filename))
        for filename in os.listdir('static/eventimages'):
            if filename.endswith('.png'):
                os.remove(os.path.join('static/eventimages', filename))
        #Deletes all barcode files when the database is reset


@app.route('/events.json')
def getevents():
    datadirectory = os.path.join(app.root_path, 'data')
    #Returns the json file
    return send_from_directory(datadirectory, 'events.json')



@app.route('/')
def index():
    if current_user.is_authenticated:
        #Show the render template with adjusted links if the user is logged in, otherwise show the render_template with the default links
        return render_template('index.html', super=current_user.is_super, auth=current_user.is_authenticated, credit = current_user.credit)
    else:
        return render_template('index.html', information = session.pop('information', None))


@app.route('/templates/dashboard')
@login_required
def AllowChanges():
    events = Event.query.filter(Event.timedate > datetime.now()).all()
    eventsdict = [return_event_dictionary(current_user.id, event) for event in events]
    with open('data/events.json', 'w') as f:
        json.dump(eventsdict, f, indent=4)
    #Creates a json dictionary with all future events so that they can be modified
    if current_user.is_super:
        return render_template('dashboard.html', super=current_user.is_super, transactions=Transaction.query.all(), error=session.pop('error', None), auth=current_user.is_authenticated, boxoneerror=session.pop('boxoneerror', None))
        #Return the page with all transactions and errors if the user is a super user otherwise redirect them back to the home page
    else:
        return redirect('/')


@app.route('/templates/login')
def returnLogin():
    #Return the login template with any errors
    if current_user.is_authenticated:
        return redirect("/logout")
    return render_template('login.html', error=session.pop('error', None))


@app.route('/templates/register')
def returnRegister():
    if current_user.is_authenticated:
        return redirect("/logout")
    errors = session.pop('errors',None)
    return render_template('register.html', errors=errors)


@app.route('/getticket', methods=['POST'])
@login_required
def getTicket():
    isbelowcapacity = False
    isabovecapacity = False
    event_id = request.form['geteventid']
    #Get the event_id for each flexbox and set two variables which are used to establish whether the tickets_allocated goes over 95% capacity when the user receives a ticket
    if event_id is not None:
        if (Event.query.filter_by(id=event_id).first().price <= current_user.credit):
            current_user.credit -= Event.query.filter_by(id=event_id).first().price
            db.session.commit()
            randnum = str(random.randint(100000000000, 999999999999))
            barcode = EAN13(randnum)
            barcode.save(f'static/{randnum}')
            #Generate a 12 digit barcode of format EAN13 and save this as a .svg file in static

            addTicket(current_user.id, event_id, randnum)
            if (Event.query.filter_by(id=event_id).first().tickets_allocated <= 0.95 * Event.query.filter_by(
                    id=event_id).first().capacity):
                isbelowcapacity = True

            Event.query.filter_by(id=event_id).first().tickets_allocated += 1

            if (Event.query.filter_by(id=event_id).first().tickets_allocated > 0.95 * Event.query.filter_by(
                    id=event_id).first().capacity):
                isabovecapacity = True
            #Add a ticket then set isbelowcapacity to True and isabovecapacity to True if getting a ticket causes the remaining tickets to be less than 5% of the capacity
                
            db.session.commit()
            #Commit the change of tickets_allocated to the database

            if isbelowcapacity and isabovecapacity:
                eventname = Event.query.filter_by(id=event_id).first().name
                msg = Message('Event close to capacity', sender=f"{os.getlogin()}@dcs.warwick.ac.uk",
                            recipients=[f"{os.getlogin()}@dcs.warwick.ac.uk"])
                msg.body = f'{eventname} is either full or nearly at capacity'
                mail.send(msg)
                #If the capacity is now below 5% then send an email to the superuser showing that the capacity is now below 5%
        else:
            session['error'] = "Insufficient funds to buy this ticket"
    return redirect("/templates/events")
    #Refresh the page
        


@app.route('/logout')
@login_required
#For a user to logout they must be logged in hence using login_required
def LogoutUser():
    logout_user()
    #Logout the user then redirect to the login page
    return redirect("/templates/login")


@app.route('/register',methods=['POST'])
#Post method is used as register will be receiving data from a form
def RegisterUser():
    authenticator_token = secrets.token_hex(32)
    #Create a token of 32 alphanumeric characters that will be emailed to the user

    username = request.form['username']
    password = request.form['password']
    errors = []
    #Set an empty list of errors

    if (User.query.filter_by(username=username).first() != None):
        errors.append('This user already exists')
        #If the username is already in the database add an error to the list saying that this user is already here

    if errors == []:
        add_user(username, generate_password_hash(password), False, authenticator_token)
        #Create the superuser account if the superuser has the correct email and password
        #Otherwise create a normal user account by setting is_super to false
        msg = Message('Verify Your Email Address', sender=f"{os.getlogin()}@dcs.warwick.ac.uk",
                      recipients=[username])
        verifylink = url_for('authenticateUser', authenticateid=authenticator_token, _external=True)
        msg.body = f'Please click on the following link to verify your email address: {verifylink}'
        mail.send(msg)
        
        #Send a link with a token that will be equal to the token in the database, external is set to true so that the correct route is sent regardless of the port number
        session['information'] = "You have received a verification email, this tab is no longer needed"
        return redirect("/")
    else:
        session['errors'] = errors
        return redirect(url_for('returnRegister'))
        #Redirect back to the register page is there's a function and add an error to the session which will be shown on th register page


@app.route('/authenticate/<authenticateid>')
def authenticateUser(authenticateid):
    if User.query.filter_by(authenticator_token=authenticateid).first() is not None:
        User.query.filter_by(authenticator_token=authenticateid).first().verified = True
        db.session.commit()

        #Set the user in the database to be verified

        newuser = get_user(User.query.filter_by(authenticator_token=authenticateid).first().id)
        login_user(newuser)
        #Find the user and login the user

        addTransaction(f"{newuser.username} has verified at {datetime.now()}")

    #Create a new transaction with the username and mentioning the time verification occurs
    return redirect("/templates/events")

@app.route('/login', methods=['POST'])
def LoginUser():
    username = request.form['username']
    password = request.form['password']
    
    #Get the posted username and password

    if User.query.filter_by(username=username).first() is not None:
        #Checks if the user with this username exists
        
        if check_password_hash(getHash(username), password) and User.query.filter_by(
                username=username).first().verified == True:
            #Checks if the user is verified

            user = get_user(getIdByName(username))
            login_user(user)

            #If the user is verified create a new transaction mentioning a user has logged in, and login in the user

            addTransaction(f"{user.username} has logged in at {datetime.now()}")
            return redirect("/")
            
        elif check_password_hash(getHash(username), password):
            session['error'] = "This user is not verified"
            #If the password is correct but the initial statement wasn't then the error must be the user is not verified, and therefore set the session error to be the user not verified

        else:
            print(getHash(username))
            session['error'] = "Incorrect password"
            #Otherwise thhe error must be the password doesn't exist
    else:
        #The user must be none hence the error is that the user doesn't exist
        session['error'] = "This user doesn't exist"
    return redirect("/templates/login")


@app.route('/removeticket', methods=['POST'])
@login_required
def removeTicket():
    eventid = request.form['getevent']
    tickettoremove = Ticket.query.filter_by(user_id=current_user.id, event_id=eventid).first()
    #Find the ticket for this event and this user
    current_user.credit += Event.query.filter_by(id=eventid).first().price
    db.session.delete(tickettoremove)
    Event.query.filter_by(id=eventid).first().tickets_allocated -= 1
    
    #Delete the ticket from the database, decrement the value storing tickets_allocated and commit to the database
    db.session.commit()

    return redirect("/templates/events")


@app.route('/addevent', methods=['POST'])
@login_required
def CreateEvent():
    try:
        name = request.form['Ticketname']
        duration = request.form['Ticketduration']
        date = request.form['Ticketdate']
        capacity = request.form['Ticketcapacity']
        location = request.form['Ticketlocation']
        price = request.form['Ticketprice']
        image = request.files['filetoadd']
        #Retrieve all the event details from the form

        if current_user.is_super:
            image.save(os.path.join('static/eventimages', f"{len(Event.query.all())+ 1}.png")) 
            #Saves the image in an event images folder with the id used to identify the image
            super = get_Super_User(current_user.id)
            super.addEvent(name, duration, date, capacity, location, price)
            return redirect("/templates/dashboard")
            #Check to ensure only a super user is modifying the page, and if so add an event with these details
    except:
        session['boxoneerror'] = 'Not all fields have been completed'
        return redirect("/templates/dashboard")

    return redirect("/templates/login")

@app.route('/templates/events')
def viewEvents():
    events = getAllEvents()
    if current_user.is_authenticated:
        #If the user is authenticated use the json dictionary and include super and auth so that the navbar can add the modify events link and remove the login and register link
        eventsdict = [return_event_dictionary(current_user.id, event) for event in events]
        with open('data/events.json', 'w') as f:
            json.dump(eventsdict, f, indent=4)
        return render_template("events.html", issignedin=1, super=current_user.is_super, dictionary=eventsdict, auth=current_user.is_authenticated, error = session.pop('error',None), credit = current_user.credit)
    else:
        return render_template("events.html", issignedin=0, dictionary=events)

@app.route('/addcredit/<userid>')
@login_required
def supplementCredit(userid):
    if current_user.is_super:
        User.query.filter_by(id = userid).first().credit += 100
        db.session.commit()
        return redirect('/templates/dashboard')
    return redirect('/')
@app.route('/requestcredits')
@login_required
def requestCredit():
    addTransaction('<a href="{}">Click here to supplement {}s credit</a>'.format(
        url_for('supplementCredit', userid=current_user.id), current_user.username))
    return redirect('/templates/events')
@app.route('/viewticket', methods = ['POST'])
def lookAtTicket():
    event = request.form['geteventid'] 
    user = current_user.id
    #Gets the current user and id, looks for that tiket in the database
    ticket = Ticket.query.filter_by(event_id=event, user_id=user).first()
    
    #If the ticket exists return the barcode by searching for the barcode associated with that ticket and returning the svg file from static, otherwise redirect the user
    if ticket:
        return render_template("viewticket.html", event=event, barcodedata=str(ticket.barcode) + ".svg", super=current_user.is_super, auth=current_user.is_authenticated, credit = current_user.credit)
    else:
        return redirect("/templates/events")
    
@app.route('/templates/resetpassword')
def showPage():
    #Display the page to reset the password with any errors
    return render_template("passwordreset.html", error = session.pop('error', None))


@app.route('/removeevent', methods=['POST'])
@login_required
def deleteEvent():
    #This route is login required as it has to be a super user
    id = request.form['cancelid']
    if id is not None:
        super = get_Super_User(current_user.id)
        super.deleteEvent(id)
        #Cancel the event using functions from the superuser class
        ticketstoemail = Ticket.query.filter_by(event_id=id).all()
        for ticket in ticketstoemail:
            ticket = User.query.filter_by(id=ticket.user_id).first().username
            User.query.filter_by(username=ticket).first().credit += Event.query.filter_by(id=id).first().price
            db.session.commit()
            try:
                msg = Message('Event Cancellation', sender=f"{os.getlogin()}@dcs.warwick.ac.uk", recipients=[ticket])
                msg.body = f"{Event.query.filter_by(id=id).first().name} has been cancelled"
                mail.send(msg)
            except:
                print("An error has occurred")
                
    return redirect("/templates/dashboard")


@app.route('/modifycapacity', methods=['POST'])
@login_required
def modCapacity():
    id = request.form['modifyid']
    if id is not None:
        if Event.query.filter_by(id=id).first().tickets_allocated != Event.query.filter_by(id=id).first().capacity:
            capacity = int(request.form['Ticketcapacity'])
            if (capacity >= Event.query.filter_by(id=id).first().tickets_allocated):
                super = get_Super_User(current_user.id)
                super.modifyCapacity(id, request.form['Ticketcapacity'])
                #Set the capacity to be the new capacity assuming that the new capacity is greater than or equals to the tickets_allocated, and then add a transaction

                addTransaction(f"{Event.query.filter_by(id=id).first().name} has had its capacity changed at {datetime.now()}")

            else:
                #Tells the superuser that they can't modify this as too many tickets have already been allocated
                session['error'] = "Can't reduce capacity to below the number of tickets already allocated"
        else:
            session['error'] = "Can't change capacity as all tickets have been allocated"
    return redirect("/templates/dashboard")


@app.route('/sendemail', methods = ['POST'])
def sendPasswordreset():
    #Uses ajax to get the email of the user
    usertosend = request.form.get("usertosend")
    msg = Message('Reset code', sender=f"{os.getlogin()}@dcs.warwick.ac.uk", recipients=[usertosend])
    newcode = secrets.token_hex(4)
    msg.body = f"Use this code to reset your password {newcode}"
    #Sends an email to the user with an 8 digit alphanumeric code representing the code they need to verify to sign in

    try:
        #Attempts to set the code required in the database and send the email
        User.query.filter_by(username = usertosend).first().authenticator_token = newcode

        db.session.commit()
        mail.send(msg)
        return jsonify({'status': 'success'})
        #Return success if succeeds
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})



@app.route('/resetpassword', methods = ['POST'])
def resetPass():
    code = request.form['code']
    password = request.form['password']
    user = User.query.filter_by(username = request.form['hiddenname']).first()
    #Get the user to reset the password of
    if user is not None:
        #If the user exists and the code given is equal to the code in the database set the hash of the password to be the hash of the new password
        if user.authenticator_token == code:
            user.passhash = generate_password_hash(password)
            db.session.commit()
            return redirect("/templates/login")
        else:
            #If we have reached this stage and there is an error then the code must not be correct

            session['error'] = "This code is invalid"
            return redirect("/templates/resetpassword") 

    else:
        #If there is no user then this user doesn't exist

        session['error'] = "This user doesn't exist"
        return redirect("/templates/resetpassword") 
