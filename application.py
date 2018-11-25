import json
import random
import string
import httplib2
import requests
import database_setup

from flask import Flask, render_template, redirect, flash, url_for,\
    jsonify, make_response
from flask import session as login_session
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from flask import make_response
from flask import request
from flask import jsonify

from database_setup import User, Category, Item, Base
from sqlalchemy import desc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


app = Flask(__name__)


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog Application"

engine = create_engine('sqlite:///catalog.db',
                       connect_args={'check_same_thread': False})
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/gconnect', methods=['POST'])
def gconnect():
    print "start"
    print request.args.get('state')
    print login_session['state']
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data
    print "state token validated"

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print "Credentials object upgraded"

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
    print "Access token is valid"

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print "Access token is used for the intended user"

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response
    print "access tokein is valid for this app"

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        t_str = 'Current user is already connected.'
        response = make_response(json.dumps(t_str),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id
    print "store access token"

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    print "user info get"

    data = answer.json()
    print "data = answer.json()"

    print(data)
    login_session['username'] = data['id']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: '
    output += '150px;-webkit-border-radius: '
    output += '150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/login')
def login():
    state = ''.join(random.choice(string.ascii_uppercase + string.
                    digits) for x in xrange(32))
    print(state)
    login_session['state'] = state
    return render_template('login.html', STATE=login_session['state'])


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        t_str = 'Current user not connected.'
        response = make_response(json.dumps(t_str), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    t_str = 'https://accounts.google.com/o/oauth2/revoke?token=%s'
    url = t_str % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        t_str = 'Successfully disconnected.'
        response = make_response(json.dumps(t_str), 200)
        response.headers['Content-Type'] = 'application/json'
        return render_template('logout.html', title="Logout",
                               msg='SUCCESS', logged=url_for('.login'),
                               logact="Login")
    else:
        t_str = 'Failed to revoke token for given user.'
        response = make_response(json.dumps(t_str, 400))
        response.headers['Content-Type'] = 'application/json'
        return render_template('logout.html', title="Logout",
                               msg='Failed to revoke token for given user.',
                               logged=url_for('.login'), logact="Login")


@app.route('/flgout', methods=['POST'])
def force_logout():
    if request.form["msg"] == "fromlogout":
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        return "SUCCESS"
    else:
        return "ERROR"


# Create the index page
@app.route('/')
@app.route('/catalog')
def make_catalog():
    if 'username' not in login_session:
        print("here through out1")
        item_list = show_items()
        cat_list = show_categories()
        return render_template('catalog.html', title="Catalog",
                               item_list=item_list, logged=url_for('.login'),
                               logact="Login", cat_list=cat_list)
    else:
        print("here through out2")
        check_create_user()
        item_list = show_items()
        cat_list = show_categories()
        print "creating"
        return render_template('catalog.html', title="Catalog",
                               item_list=item_list,
                               logged=url_for('.gdisconnect'),
                               logact="Logout",
                               create=url_for('.create_new_item'),
                               cat_list=cat_list)


@app.route('/create')
def create_new_item(title="Create New Item"):

    # Check that user is logged in
    if 'username' not in login_session:
        return redirect('/login')

    # Show the existing categories
    print("this is done")
    categories = show_categories()
    return render_template('create.html', title=title,
                           logged=url_for('.gdisconnect'), logact="Logout",
                           categories=categories)


@app.route('/add', methods=['POST'])
def add():

    if 'username' not in login_session:
        ret = {'html': "Not logged in",
               'status': "ERROR"}
        return json.dumps(ret)

    if 'name' not in request.form or 'desc' not in request.form:
        ret = {'html': "No values given",
               'status': "ERROR"}
        return json.dumps(ret)

    t_name = request.form["name"]
    t_desc = request.form["desc"]

    if session.query(Item).filter(Item.name == t_name).count() != 0:
        ret_str = t_name
        ret_str += " is already in the database"
        ret = {'html': ret_str, 'status': "ERROR"}
        return json.dumps(ret)

    # get only one category id
    t_cat = get_category_id(request.form["category"])
    if t_cat == "ERROR":
        ret = {'html': "Error getting category id", 'status': "ERROR"}
        return json.dumps(ret)

    # get only one user id
    t_user = get_user_id(login_session['email'])
    if t_user == "ERROR":
        ret = {'html': "Error getting user id", 'status': "ERROR"}
        return json.dumps(ret)

    # add to database
    t_itm = Item(name=t_name, description=t_desc,
                 category_id=t_cat, user_id=t_user)
    session.add(t_itm)
    session.commit()

    # Return
    ret = {'html': "Item successfully added!", 'status': "SUCCESS"}
    return json.dumps(ret)


@app.route('/catalog/<catname>')
def make_category(catname):

    # Check if logged in to change login/logout link
    if 'username' not in login_session:
        t_logact = "Login"
        t_logged = url_for('.gdisconnect')
    else:
        t_logact = "Logout"
        t_logged = url_for('.login')

    # Get all items in category
    query = session.query(Item).join(Category)
    query = query.filter(Category.name == catname)
    ret = [x.name for x in query]
    return render_template('category.html', title=catname, catlist=ret,
                           logged=t_logged, logact=t_logact)


@app.route('/catalog/<catname>/<itemname>')
def make_item(catname, itemname):

    # Check if logged in or not
    if 'username' not in login_session:
        t_logact = "Login"
        t_logged = url_for('.login')
        try:
            query = session.query(Item).filter(Item.name == itemname)
            query = query.one()
        except Exception as e:
            print(e)
            return render_template('notfound.html', title="denied",
                                   logged=url_for('.login'), logact="Login")
        return render_template('item.html', title=itemname, item=itemname,
                               desc=query.description, logged=t_logged,
                               logact=t_logact)
    else:
        t_logact = "Logout"
        t_logged = url_for('.gdisconnect')
        if owns_item(itemname):
            t_edit = True
        else:
            t_edit = False
        try:
            query = session.query(Item).filter(Item.name == itemname)
            query = query.first()
        except Exception as e:
            print(e)
            return render_template('notfound.html', title="denied",
                                   logged=url_for('.gdisconnect'),
                                   logact="Logout")
        return render_template('item.html', title=itemname, item=itemname,
                               desc=query.description, logged=t_logged,
                               logact=t_logact, edit=t_edit)


# Create JSON endpoint
@app.route('/catalog.json')
def endpoint():
    return jsonify(make_json())


@app.route('/<itemname>/edit')
def edit_item(itemname):

    # redirect if not logged in
    if 'username' not in login_session:
        return redirect('/login')

    # check if user owns the item
    if not owns_item(itemname):
        return render_template('denied.html', title="denied",
                               logged=url_for('.gdisconnect'), logact="Logout")

    # generate form to edit item
    categories = show_categories()
    query = session.query(Item).filter(Item.name == itemname).first()
    t_desc = query.description
    query2 = session.query(Category).join(Item)
    query2 = query2.filter(Item.name == itemname)
    t_cat = query2.first().name
    return render_template('edit.html', title="edit", item=itemname,
                           logged=url_for('.gdisconnect'), logact="Logout",
                           categories=categories, name=itemname, desc=t_desc,
                           cur_cat=t_cat)


@app.route('/edit', methods=['POST'])
def edit():

    # Check that user is logged in
    if 'username' not in login_session:
        ret = {'html': "Not logged in",
               'status': "ERROR"}
        return json.dumps(ret)

    # make sure data was posted
    if ('name' not in request.form or 'desc' not in request.form or
            'original' not in request.form or 'category' not in request.form):
        ret = {'html': "No values given",
               'status': "ERROR"}
        return json.dumps(ret)

    # get data
    original_name = request.form["original"]
    new_name = request.form["name"]
    new_desc = request.form["desc"]
    new_cat = get_category_id(request.form["category"])

    # update data
    item = session.query(Item).filter(Item.name == original_name).first()
    item.name = new_name
    item.description = new_desc
    item.category_id = new_cat
    session.commit()

    # return to ajax call
    ret = {'status': "SUCCESS",
           'html': "Successfully updated item"}

    return json.dumps(ret)


@app.route('/<itemname>/delete')
def delete_item(itemname):

    # redirect if not logged in
    if 'username' not in login_session:
        return redirect('/login')

    # check if user owns the item
    if not owns_item(itemname):
        return render_template('denied.html', title="denied",
                               logged=url_for('.gdisconnect'), logact="Logout")

    # Ask to confirm delete item
    return render_template('delete.html', title="delete", item=itemname,
                           logged=url_for('.gdisconnect'), logact="Logout")


@app.route('/delete', methods=['POST'])
def delete():

    # Make sure something was posted
    if 'itemname' not in request.form:
        ret = {'html': "ERROR. No item selecte for delete", 'status': "ERROR"}
        return json.dumps(ret)
    itemname = request.form["itemname"]

    # redirect if not logged in
    if 'username' not in login_session:
        return redirect('/login')

    # check if user owns the item
    if not owns_item(itemname):
        ret = {'html': "ERROR. You don't own that item", 'status': "ERROR"}
        return json.dumps(ret)

    # delete item
    session.query(Item).filter(Item.name == itemname).delete()
    session.commit()

    ret = {'html': "Item successfully deleted!", 'status': "SUCCESS"}
    return json.dumps(ret)


def get_category_id(name):

    try:
        cat_id = session.query(Category).filter(Category.name == name)
        cat_id = cat_id.one().id
        return cat_id
    except Exception as e:
        print(e)
        return "ERROR"


def get_user_id(email):

    try:
        u_id = session.query(User).filter(User.email == email).one().id
        return u_id
    except Exception as e:
        print(e)
        return "ERROR"


def owns_item(item):

    query = session.query(Item).join(User)
    query = query.filter(User.email == login_session['email'])
    query = query.filter(Item.name == item)
    print query.count()
    return query.count() != 0


def show_categories():

    query = session.query(Category)
    ret = [x.name for x in query]
    return ret


def show_items():

    print("show_items function start")
    query = session.query(Item).order_by(desc(Item.create_date))
    ret = []
    for x in query:
        print(x.name)
        print(x.id)
        t_name = x.name
        t_cat = session.query(Category).filter(Category.id == x.category_id)\
            .one()
        ret.append((t_name, t_cat.name))
    return ret


def no_email():

    query = session.query(User).filter(User.email == login_session['email'])
    print query.count()
    return query.count() == 0


def insert_user():
    temp_email = login_session['email']
    temp_name = login_session['username']
    temp_pic = login_session['picture']
    temp_user = User(email=temp_email, name=temp_name, picture=temp_pic)
    session.add(temp_user)
    session.commit()


def check_create_user():

    print "check and creating user"
    if no_email():
        print "no email"
        insert_user()


def make_json():
    cats = session.query(Category)
    the_list = [{'id': x.id, 'name': x.name, 'item': None}
                for x in cats]
    result = []
    for i in the_list:
        items = session.query(Item).filter_by(category_id=i['id']).all()
        print(items)
        category_item = dict(item=[item.serialize for item in items])
        i['item'] = category_item
        print(the_list)
    return the_list


if __name__ == '__main__':
    app.secret_key = 'supersecretkey'  # for using sessioion
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
