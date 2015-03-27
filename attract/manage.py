from application import app
# from application import db
from flask.ext.script import Manager
# from flask.ext.migrate import Migrate
# from flask.ext.migrate import MigrateCommand

# migrate = Migrate(app, db)
manager = Manager(app)
# manager.add_command('db', MigrateCommand)

@manager.command
def create_all_tables():
    db.create_all()

@manager.command
def runserver():
    app.run(port=5001)

manager.run()
