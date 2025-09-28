import json
import os
from functools import wraps

# Load translations
def load_translations():
    translations = {}
    translations_dir = os.path.join(os.path.dirname(__file__), 'translations')
    
    for lang in ['ko', 'en']:
        file_path = os.path.join(translations_dir, f'{lang}.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
    
    return translations

# Global translations cache
_translations = load_translations()

def get_translation(key, lang='ko'):
    """
    Get translation for a key in specified language.
    Falls back to Korean if translation not found.
    
    Args:
        key: Translation key (e.g., 'common.loading')
        lang: Language code ('ko' or 'en')
    
    Returns:
        Translated string
    """
    if lang not in _translations:
        lang = 'ko'
    
    keys = key.split('.')
    value = _translations[lang]
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        # Fallback to Korean
        if lang != 'ko':
            return get_translation(key, 'ko')
        # If Korean also fails, return the key itself
        return key

def get_language_from_request(request):
    """
    Get language from request (cookie, header, or default to Korean)
    """
    # Check cookie first
    lang = request.cookies.get('language', 'ko')
    
    # Validate language
    if lang not in ['ko', 'en']:
        lang = 'ko'
    
    return lang

def t(key, lang=None):
    """
    Shortcut function for get_translation
    """
    if lang is None:
        # Flask context에서 현재 언어 가져오기
        from flask import request
        lang = get_language_from_request(request)
    return get_translation(key, lang)

def with_language(f):
    """
    Decorator to inject language into view functions
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        lang = get_language_from_request(request)
        return f(*args, **kwargs, lang=lang)
    return decorated_function

def get_available_languages():
    """
    Get list of available languages
    """
    return list(_translations.keys())

def reload_translations():
    """
    Reload translations from files (useful for development)
    """
    global _translations
    _translations = load_translations()
