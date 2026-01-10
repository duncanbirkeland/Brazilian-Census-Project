# README and VIDEO

Your _readme_ goes here

Your _video_ must replace the `demo.mp4` file in this folder

Before submitting your coursework, run `./clean.sh` as this will remove the virtual environment which can be reconstructed locally.

Registration in this application works by forcing the user to enter an email address and a password, this will then redirect them to the home screen instructing them that this tab is no longer necessary.
If the email exists the user will receive an email with a link to authenticate using a token, this token will be equivalent to the token stored in the database and if these tokens match then the user will be
set to verified in the database and therefore their account will be capable of being logged in to. This application has two separate classes User representing an attendee and a superuser which extends from attendee.
The superuser is created by default and is the only superuser on the database, all emails are sent from the superuser's account.

Logging in to an account takes in the users email and password, if these match their equivalents in the database and the user is set to verified then they will be allowed to login, otherwise the user will be returned a 
relavent error message explaining either whether the user has: an email that is not registered in the database, an incorrect password or if the user is not verified. If the user has forgotten their password they can
send a reset password request to their email, the code will then be emailed and if the user enters this emailed code then the new password they enter will be set to the user's password in the database. To do this the
verification code required in the database is reset, and the data is posted to a resetpassword route to check whether the code entered is correct and if not an error will be returned. This route makes use of ajax so that 
the user doesn't get sent to a new page to enter the code for ease of use.

The superuser modification has a few key features, a form to add a new event in which an error message will be returned if not all fields are filled an image can be selected. This event will then be posted to the database with
the number of tickets allocated by default set to 0. The event modification form allows the user to modify the capacity to any capacity higher than the number of tickets-allocated, provided max capacity hasn't already been reached
this form also allows the superuser to cancel event, in which case the event will be sent to cancelled in the database, users will be refunded any credits, and all users with tickets to this event will be emailed of the cancellation. To access
this page and any of these modification routes, the user will need to be a superuser, any any of the functions are encapsulated within the superuser class for added safety.

By default all routes that require a user to be logged in, e.g. viewing a ticket, have a @login_required attached them to prevent non logged in users viewing them.

All templates for ease extend from a file called navbar.html which contains a navbar, which has javascript to modify the navbar e.g. remove login and register if the user is logged in, and add the number of credits if the user is an 
attendee. The page by default has a background and the css file as well as jquery linked. All templates extending from this have all their html placed inside of the content block or the headblock.

The viewticket page finds the barcode via a hidden variable which contains the barcode filename, and has a background of the chosen image.

The view events page makes use of a json file to make javascript modifications to the page based on the data, for example if the event is full or the event has been cancelled, the submit button to purchase a ticket is disabled, the colour changes
and the prop is disabled to prevent the button being pressed. All events are in flexbox so they can infinitely scroll down. If the user has a ticket for the event, the button will change style and value to allow the user to view their ticket
and the route of the submit button is changed. A cancel event button is also added. As the event page is infinitely scrollable the background is replaced with a repeating background that inverts each time to create a seamless transition

The first additional feature is several QOL improvements for the events page, the first being an image that is shown next to each event and once the ticket is being viewed the background is set to the image of the event, the second being a search bar
which is intended to be helpful when a large number of events are added, as the user can search for an event, the two closest matches will be displayed and once the user clicks on these only the flexbox of this event will appear.

The other additional feature is a credit system to allow user to purchase tickets. By default all users have 100 credits, and can spend credits to purchase tickets. If the user cancels their ticket they will be refunded for this event, and if the 
superuser cancels an event they have a ticket for they will also be refunded. In order to allow certain users to have more credits so that they can attend more events, the user can request an increase in credits, which the superuser can then verify
if they want to.

Security on the website is performed by only allowing logged in users to attend logged in routes and only allow super users to attend routes to modify events, with all modifying functions encapsulated within the super user class. Most variables passed
into jinja templates have all tags stripped to prevent html being inserted into the webpage. All passwords are hashed, and a module named secret is used to create alphanumeric authentication tokens. Almost all queries are parameterised so SQL injections can't occur.

The general styling for the website is based around minimalism with brightly coloured backgrounds and submit buttons, with most text being monotome other than key headers.

Meta tags are used in my html files in case users with accessibility issues need to view the website using a screen reader.

In the database as well as having all the unique columns for each class transitivity is implemented using a foreign key so that you can retrieve event_ids and user_ids by querying the ticket.