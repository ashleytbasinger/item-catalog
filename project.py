from flask import Flask, render_template, request, redirect, url_for
from flask import jsonify, flash, Response
from flask import session as login_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc
from database_seed import *
import random, string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from flask import make_response
import httplib2, json, requests
from functools import wraps

# App Configuration

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog"
app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Helper Methods


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def login_required(f):
    """ Is the user logged in or not? """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' in login_session:
            return f(*args, **kwargs)
        else:
            flash("You need to be logged in to add a new item.")
            return redirect(url_for('getMainPage'))
    return decorated_function


def checkIfTitleExists(title):
    """ Checks if the item has a unique title in db """
    results = session.query(Item).filter_by(title=title).all()
    return len(results) > 0

# Routes


@app.route('/')
def routeToMain():
    return redirect(url_for('getMainPage'))


@app.route('/catalog/JSON')
def getCatalog():
    output_json = []
    categories = session.query(Category).all()
    for category in categories:
        items = session.query(Item).filter_by(category_id=category.id)
        category_output = {}
        category_output["id"] = category.id
        category_output["name"] = category.name
        category_output["items"] = [i.serialize for i in items]
        output_json.append(category_output)
    return jsonify(Categories=output_json)


@app.route('/catalog', methods=['GET', 'POST'])
def getMainPage():
    """ Handler for main page, includes auth, session management """
    try:
        user = login_session['user_id']
    except KeyError:
        user = None
    if request.method == 'GET':
        STATE = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
        login_session['state'] = STATE
        categories = session.query(Category).all()
        latest_items = session.query(Item).order_by(
            desc(Item.date)).all()
        category_names = {}
        for category in categories:
            category_names[category.id] = category.name
        if len(latest_items) == 0:
            flash("No items found")
        return render_template(
            'index.html', categories=categories, items=latest_items,
            category_names=category_names, user=user, STATE=STATE
        )
    else:
        print ("Starting authentication")
        if request.args.get('state') != login_session['state']:
            response = make_response(json.dumps('Invalid state parameter.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response
        # Get auth code
        code = request.data

        try:
            # Turn auth code into credentials object
            oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
            oauth_flow.redirect_uri = 'postmessage'
            credentials = oauth_flow.step2_exchange(code)
        except FlowExchangeError:
            response = make_response(
                json.dumps('Failed to turn auth code into credentials.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response

        # Validate access token
        access_token = credentials.access_token
        url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
               % access_token)
        h = httplib2.Http()
        result = json.loads(h.request(url, 'GET')[1])
        # Stop if there's an error
        if result.get('error') is not None:
            response = make_response(json.dumps(result.get('error')), 500)
            response.headers['Content-Type'] = 'application/json'

        # Verify access token for the intended user
        gplus_id = credentials.id_token['sub']
        if result['user_id'] != gplus_id:
            response = make_response(
                json.dumps("Token's user ID doesn't match provided user ID."), 401)
            response.headers['Content-Type'] = 'application/json'
            return response

        # Verify access token
        if result['issued_to'] != CLIENT_ID:
            response = make_response(
                json.dumps("Token's client ID does not match app's."), 401)
            print "Token's client ID does not match app's."
            response.headers['Content-Type'] = 'application/json'
            return response

        stored_credentials = login_session.get('credentials')
        stored_gplus_id = login_session.get('gplus_id')
        if stored_credentials is not None and gplus_id == stored_gplus_id:
            response = make_response(json.dumps('Current user is already connected.'), 200)
            response.headers['Content-Type'] = 'application/json'
            return response

        # Access token stored in session
        login_session['access_token'] = access_token
        login_session['gplus_id'] = gplus_id

        # Get user info
        userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
        params = {'access_token': access_token, 'alt': 'json'}
        answer = requests.get(userinfo_url, params=params)
        data = answer.json()

        login_session['user_id'] = data['name']

        # see if user exists, if it doesn't make a new one
        # user_id = getUserID(login_session['user'])
        # if not user_id:
        #     user_id = createUser(login_session)
        # login_session['user_id'] = user_id

        flash("you are now logged in as %s" % login_session['user_id'])
        return redirect(url_for('getMainPage'))


@app.route('/catalog/categories/<category_name>/')
def getItems(category_name):
    """ Returns items for a given category name """
    categories = session.query(Category).all()
    selected_category = session.query(Category).filter_by(name=category_name).one()
    items = session.query(Item).filter_by(category_id=selected_category.id).all()
    category_names = {}
    for category in categories:
        category_names[category.id] = category.name
    if len(items) == 0:
        flash("No items found in this category")
    try:
        user = login_session['user_id']
    except KeyError:
        user = None
    return render_template(
        'category_detail.html', selected_category=selected_category,  user=user,
        items=items, categories=categories, category_names=category_names
    )


@app.route('/catalog/items/<item_title>/')
def getItemDetails(item_title):
    """ Returns a specific item object given its title """
    item = session.query(Item).filter_by(title=item_title).one()
    category = session.query(Category).filter_by(id=item.category_id).one()
    return render_template(
        'item_detail.html', item=item, category=category
    )


@app.route('/catalog/items/new', methods=['GET', 'POST'])
@login_required
def newItem():
    """ Handles the creation of a new item """
    categories = session.query(Category).all()
    try:
        user = login_session['user_id']
    except KeyError:
        user = None
    if request.method == 'POST':
        title = request.form['title']
        if checkIfTitleExists(title):
            flash("Please enter a different title. Item " + title + " already exists.")
            return redirect(url_for('newItem'))
        newItem = Item(title, request.form['description'], request.form['category_id'], login_session['user_id'])
        session.add(newItem)
        session.commit()
        return redirect(url_for('getMainPage'))
    else:
        return render_template(
            'create_item.html', categories=categories, user=user
        )


@app.route('/catalog/items/<item_title>/edit', methods=['GET', 'POST'])
@login_required
def editItem(item_title):
    """ Handles updating an existing item """
    editedItem = session.query(Item).filter_by(title=item_title).one()
    # See if the logged in user is the owner of item
    creator = getUserInfo(editedItem.user_id)
    user = getUserInfo(login_session['user_id'])
    # If logged in user != item owner redirect them
    if creator.id != login_session['user_id']:
        flash("You cannot edit this item.")
        return redirect(url_for('getMainPage'))
    if request.method == 'POST':
        if request.form['title']:
            title = request.form['title']
            if item_title != title and checkIfTitleExists(title):
                flash("Please enter a different title. Item " + title + " already exists.")
                return redirect(url_for('editItem', item_title=item_title)).one()
            editedItem.title = title
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['category_id']:
            editedItem.category_id = request.form['category_id']
        session.add(editedItem)
        session.commit()
        return redirect(url_for('getMainPage'))
    else:
        user = login_session['user_id']
        return render_template(
            'edit_item.html', item=editedItem, category=category,
            categories=categories, user=user
        )


@app.route('/catalog/items/<item_title>/delete', methods=['GET', 'POST'])
@login_required
def deleteItem(item_title):
    """ Deletes an item given its unique title """
    # See if the logged in user is the owner of item
    itemToDelete = session.query(Item).filter_by(title=item_title).one()
    creator = getUserInfo(itemToDelete.user_id)
    user = getUserInfo(login_session['user_id'])
    # If logged in user != item owner redirect them
    if creator.id != login_session['user_id']:
        flash("You cannot delete this item.")
        return redirect(url_for('getMainPage'))
    if request.method == 'POST':
        itemToDelete = session.query(Item).filter_by(title=item_title).one()
        session.delete(itemToDelete)
        session.commit()
        return redirect(url_for('getMainPage'))
    else:
        user = login_session['user_id']
        return render_template('delete_item.html', item_title=item_title, user=user)


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['user_id']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['user_id']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('getMainPage'))
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

if __name__ == '__main__':
    app.secret_key = 'secret'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
