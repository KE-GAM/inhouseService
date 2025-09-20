
from flask import Blueprint, request, render_template
import sqlite3, os
from db import get_db

bp = Blueprint('notice', __name__)

@bp.route('/announcements')
def list_ann():
    db = get_db()
    rows = db.execute('SELECT author, text, created_at FROM announcements ORDER BY created_at DESC').fetchall()
    return render_template('notice/list.html', rows=rows)

@bp.route('/notice/new', methods=['POST'])
def new_ann():
    # Demo-only manual creation (when Slack integration isn't configured yet)
    author = request.form.get('author') or 'demo'
    text = request.form.get('text') or '[공지] 내용 없음'
    db = get_db()
    db.execute("INSERT INTO announcements(author,text,created_at) VALUES(?,?,datetime('now'))", (author, text))
    db.commit()
    from flask import redirect
    return redirect('/announcements')
