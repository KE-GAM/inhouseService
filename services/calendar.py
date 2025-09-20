
from flask import Blueprint, request, render_template, redirect
from db import get_db

bp = Blueprint('calendar', __name__)

@bp.route('/calendar')
def calendar_home():
    db = get_db()
    my = db.execute("SELECT id,title,start,end FROM events WHERE kind='my' ORDER BY start DESC LIMIT 20").fetchall()
    vac = db.execute("SELECT id,title,start,end FROM events WHERE kind='vac' ORDER BY start DESC LIMIT 20").fetchall()
    company = db.execute("SELECT id,title,start,end FROM events WHERE kind='company' ORDER BY start DESC LIMIT 20").fetchall()
    return render_template('calendar/main.html', my=my, vac=vac, company=company, active='calendar', user={'email': 'nota_inhouse@nota.ai'})

@bp.route('/calendar/my/new', methods=['POST'])
def calendar_my_new():
    db = get_db()
    title = request.form.get('title')
    start = request.form.get('start')
    end = request.form.get('end')
    db.execute("INSERT INTO events(kind, owner_email, title, start, end) VALUES('my','demo@nota.ai',?,?,?)", (title, start, end))
    db.commit()
    return redirect('/calendar')

@bp.route('/calendar/company/new', methods=['POST'])
def calendar_company_new():
    db = get_db()
    title = request.form.get('title')
    start = request.form.get('start')
    end = request.form.get('end')
    db.execute("INSERT INTO events(kind, owner_email, title, start, end) VALUES('company','hr@nota.ai',?,?,?)", (title, start, end))
    db.commit()
    return redirect('/calendar')
