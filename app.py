
from flask import Flask, render_template, request, make_response
from db import init_db_command
from services.noonpick import bp as noonpick_bp, validate_api_keys
from services.booker import bp as booker_bp
from services.calendar import bp as calendar_bp
from services.report import bp as report_bp
from services.guidebook import bp as guidebook_bp
from services.admin import bp as admin_bp
from i18n import get_language_from_request, t, with_language
import sqlite3
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(DATABASE='inhouse.sqlite3', JSON_AS_ASCII=False, TEMPLATES_AUTO_RELOAD=True)

    # Blueprints
    app.register_blueprint(noonpick_bp)
    app.register_blueprint(booker_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(guidebook_bp)
    app.register_blueprint(admin_bp)

    # Context processor for templates
    @app.context_processor
    def inject_language():
        return {
            'lang': get_language_from_request(request),
            't': t
        }

    @app.route('/')
    @with_language
    def index(lang):
        return render_template('sidebar_base.html', 
                             title='Inhouse Services', 
                             active='home', 
                             user={'email': 'lwk9589@gmail.com', 'name': '이원규', 'org_name': 'Service Architect', 'title': 'Developer', 'is_admin': True},
                             lang=lang)
    
    @app.route('/set_language/<lang>')
    def set_language(lang):
        if lang not in ['ko', 'en']:
            lang = 'ko'
        
        # Referer 헤더에서 이전 페이지 URL 가져오기
        referer = request.headers.get('Referer')
        if not referer:
            referer = '/'
        
        response = make_response('', 302)
        response.set_cookie('language', lang, max_age=60*60*24*365)  # 1 year
        response.headers['Location'] = referer
        
        return response
    
    @app.route('/translations/<lang>.json')
    def get_translations(lang):
        if lang not in ['ko', 'en']:
            lang = 'ko'
        
        import json
        import os
        translations_path = os.path.join(os.path.dirname(__file__), 'translations', f'{lang}.json')
        
        try:
            with open(translations_path, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            return translations
        except FileNotFoundError:
            return {'error': 'Translation file not found'}, 404
    
    @app.route('/test_language')
    def test_language():
        lang = get_language_from_request(request)
        return f"<h1>Language Test</h1><p>Current language: {lang}</p><p>Cookie: {request.cookies.get('language', 'not set')}</p>"

    # CLI: flask --app app init-db
    @app.cli.command('init-db')
    def init_db():
        init_db_command()
        # NoonPick 오피스 초기화
        from services.noonpick import init_offices
        init_offices()
        print('Initialized the database and NoonPick offices.')

    # Context processor for templates
    @app.context_processor
    def inject_language():
        return {
            'lang': get_language_from_request(request),
            't': t
        }
    
    return app

if __name__ == '__main__':
    # API 키 검증
    if not validate_api_keys():
        print("일부 API 키가 설정되지 않았습니다. 서비스가 제한적으로 동작할 수 있습니다.")
    
    app = create_app()
    app.run(debug=True, port=8000)
