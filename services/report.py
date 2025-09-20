
from flask import Blueprint, request, render_template, jsonify
from db import get_db

bp = Blueprint('report', __name__)

@bp.route('/report')
def list_reports():
    db = get_db()
    rows = db.execute("SELECT id, asset_id, category, desc, status, created_at FROM tickets ORDER BY created_at DESC").fetchall()
    return render_template('report/list.html', rows=rows, active='report', user={'email': 'nota_inhouse@nota.ai'})

@bp.route('/report/inbound', methods=['POST'])
def report_inbound():
    data = request.get_json(silent=True) or {}
    asset_code = data.get('asset_id')
    email = data.get('reporter')
    category = data.get('category')
    desc = data.get('desc')
    db = get_db()
    # Map asset_code -> assets.id (create if not exists for demo)
    asset_row = db.execute("SELECT id FROM assets WHERE asset_code=?", (asset_code,)).fetchone()
    if not asset_row:
        db.execute("INSERT INTO assets(asset_code,name,type,location) VALUES(?,?,?,?)",
                   (asset_code or 'ASSET-UNKNOWN', 'unknown', category or '', data.get('location','')))
        db.commit()
        asset_row = db.execute("SELECT id FROM assets WHERE asset_code=?", (asset_code or 'ASSET-UNKNOWN',)).fetchone()
    db.execute("INSERT INTO tickets(asset_id, reporter_email, category, desc) VALUES(?,?,?,?)",
               (asset_row['id'], email, category, desc))
    db.commit()
    return jsonify({'ok': True})
