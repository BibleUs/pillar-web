import sys
import os
import config
from attractsdk import Api
from attractsdk.users import User
from attractsdk.tokens import Token
from attractsdk.exceptions import UnauthorizedAccess

from flask import Flask
from flask import session
from flask import Blueprint
from flask import redirect
from flask import url_for

from flask.ext.mail import Mail
from flask.ext.thumbnails import Thumbnail
from flask.ext.assets import Environment

from flask.ext.login import LoginManager
from flask.ext.login import UserMixin
from flask.ext.login import current_user


# Initialize the Flask all object
app = Flask(__name__,
    template_folder='templates',
    static_folder='static')

# Filemanager used by Flask-Admin extension
filemanager = Blueprint('filemanager', __name__, static_folder='static/files')

# Choose the configuration to load
app.config.from_object(config.Development)


# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "users.login"
login_manager.login_message = u"Please login."


@login_manager.user_loader
def load_user(userid):
    api = Api(
        endpoint=SystemUtility.attract_server_endpoint(),
        username=None,
        password=None,
        token=userid
    )

    params = {'where': 'token=="{0}"'.format(userid)}
    token = Token.all(params, api=api)
    if token:
        user_id = token['_items'][0]['user']
        user = User.find(user_id, api=api)
    if token and user:
        login_user = userClass(userid)
        login_user.email = user['email']
        login_user.objectid = user['_id']
        try:
            login_user.first_name = user['first_name']
        except KeyError:
            pass
        try:
            login_user.last_name = user['last_name']
        except KeyError:
            pass
    else:
        login_user = None
    return login_user


class userClass(UserMixin):
    def __init__(self, token):
        # We store the Token instead of ID
        self.id = token
        self.first_name = None
        self.last_name = None
        self.objectid = None


class SystemUtility():
    def __new__(cls, *args, **kwargs):
        raise TypeError("Base class may not be instantiated")

    @staticmethod
    def blender_id_endpoint():
        """Gets the endpoint for the authentication API. If the env variable
        is defined, it's possible to override the (default) production address.
        """
        return os.environ.get(
            'BLENDER_ID_ENDPOINT', "https://www.blender.org/id")

    @staticmethod
    def attract_server_endpoint():
        """Gets the endpoint for the authentication API. If the env variable
        is defined, it's possible to override the (default) production address.
        """
        return os.environ.get(
            'ATTRACT_SERVER_ENDPOINT', "http://127.0.0.1:5000")

    @staticmethod
    def attract_api():
        api = Api(
            endpoint=SystemUtility.attract_server_endpoint(),
            username=None,
            password=None,
            token=current_user.id
        )
        return api

    @staticmethod
    def session_item(item):
        if item in session:
            return session[item]
        else:
            return None

# Initialized the available extensions
mail = Mail(app)
thumb = Thumbnail(app)
assets = Environment(app)


# Import controllers
from application.modules.node_types import node_types
from application.modules.nodes import nodes
from application.modules.users import users
from application.modules.main import homepage
from application.helpers import url_for_other_page
from application.modules.stats import stats
# from application.modules.files import files

# Pagination global to use un jinja template
app.jinja_env.globals['url_for_other_page'] = url_for_other_page

# Register blueprints for the imported controllers
app.register_blueprint(filemanager)
app.register_blueprint(node_types, url_prefix='/node-types')
app.register_blueprint(nodes, url_prefix='/nodes')
app.register_blueprint(users, url_prefix='/users')
app.register_blueprint(stats, url_prefix='/stats')
# app.register_blueprint(files, url_prefix='/files')


@app.errorhandler(UnauthorizedAccess)
def handle_invalid_usage(error):
    """Global exception handling for attractsdk UnauthorizedAccess
    Currently the api is fully locked down so we need to constantly
    check for user authorization.
    """
    return redirect(url_for('users.login'))
