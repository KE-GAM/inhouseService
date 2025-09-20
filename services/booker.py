
from flask import Blueprint, request, render_template, redirect, flash
from db import get_db

bp = Blueprint('booker', __name__)

def has_conflict(db, employee_id, resource_type, resource_id, date, slot):
    # resource conflict
    row = db.execute("""SELECT 1 FROM bookings WHERE resource_type=? AND resource_id=? AND date=? AND slot=?""",
                     (resource_type, resource_id, date, slot)).fetchone()
    if row: return True
    # employee double-book
    row = db.execute("""SELECT 1 FROM bookings WHERE employee_id=? AND date=? AND slot=?""", (employee_id, date, slot)).fetchone()
    return bool(row)

@bp.route('/booker')
def booker_home():
    db = get_db()
    my = db.execute("SELECT resource_type, resource_id, date, slot FROM bookings ORDER BY created_at DESC LIMIT 20").fetchall()
    return render_template('booker/main.html', my=my)

@bp.route('/booker/reserve', methods=['POST'])
def reserve():
    employee_id = 1  # demo user
    resource_type = request.form.get('resource_type','room')
    resource_id = int(request.form.get('resource_id','1'))
    date = request.form.get('date')
    slot = request.form.get('slot')
    db = get_db()
    if has_conflict(db, employee_id, resource_type, resource_id, date, slot):
        # For simplicity use redirect; Flash requires secret_key; skip for barebones
        return redirect('/booker')
    db.execute("INSERT INTO bookings(employee_id,resource_type,resource_id,date,slot) VALUES(?,?,?,?,?)",
               (employee_id, resource_type, resource_id, date, slot))
    db.commit()
    return redirect('/booker')
