
from flask import Flask, render_template
from db import init_db_command
from services.notice import bp as notice_bp
from services.booker import bp as booker_bp
from services.calendar import bp as calendar_bp
from services.report import bp as report_bp
import sqlite3

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(DATABASE='inhouse.sqlite3', JSON_AS_ASCII=False, TEMPLATES_AUTO_RELOAD=True)

    # Blueprints
    app.register_blueprint(notice_bp)
    app.register_blueprint(booker_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(report_bp)

    @app.route('/')
    def index():
        return render_template('sidebar_base.html', title='Inhouse Services', active='home', user={'email': 'nota_inhouse@nota.ai'})

    # CLI: flask --app app init-db
    @app.cli.command('init-db')
    def init_db():
        init_db_command()
        print('Initialized the database.')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=8000)
