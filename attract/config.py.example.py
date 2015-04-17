import os

class Config(object):
    # Configured for GMAIL
    MAIL_SERVER = ''
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = ''
    MAIL_PASSWORD = ''
    DEFAULT_MAIL_SENDER = ''

    # Flask-Security setup
    SECURITY_LOGIN_WITHOUT_CONFIRMATION = True
    SECURITY_REGISTERABLE = True
    SECURITY_RECOVERABLE = True
    SECURITY_CHANGEABLE = True
    SECUIRTY_POST_LOGIN = '/'
    SECURITY_PASSWORD_HASH = ''
    SECURITY_PASSWORD_SALT = ''
    SECURITY_EMAIL_SENDER = ''


class Development(Config):
    SECRET_KEY=''
    SERVER_NAME='attract.local:5555'
    DEBUG=True
    SQLALCHEMY_DATABASE_URI=''
    SECURITY_REGISTERABLE=True
    SECURITY_LOGIN_USER_TEMPLATE = 'security/login_user.html'
    MEDIA_FOLDER = ''
    MEDIA_URL = ''
    MEDIA_THUMBNAIL_FOLDER = ''
    MEDIA_THUMBNAIL_URL = ''
    FILE_STORAGE = '{0}/application/static/storage'.format(
                os.path.join(os.path.dirname(__file__)))
