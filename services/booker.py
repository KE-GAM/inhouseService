
from flask import Blueprint, request, render_template, redirect, jsonify
from db import get_db
from datetime import datetime, timedelta
from i18n import get_language_from_request
import sqlite3
import json

# Admin monitoring logging
def log_event(user_id, service, action, target_id=None, meta=None):
    """모니터링 이벤트를 로깅합니다."""
    try:
        db = get_db()
        meta_json = json.dumps(meta) if meta else None
        
        db.execute(
            """INSERT INTO monitoring_events (ts, user_id, service, action, target_id, meta)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, service, action, target_id, meta_json)
        )
        db.commit()
    except Exception as e:
        print(f"Failed to log event: {e}")

bp = Blueprint('booker', __name__)

# HRIS 데이터 동기화 함수
def sync_hris_employees():
    """HRIS employees_basic.json 데이터를 동기화"""
    db = get_db()
    
    try:
        with open('HRIS data/employees_basic.json', 'r', encoding='utf-8') as f:
            employees = json.load(f)
        
        # 기존 데이터 삭제 후 새로 삽입
        db.execute("DELETE FROM hris_employees")
        
        for emp in employees:
            db.execute("""
                INSERT INTO hris_employees 
                (employee_id, name, gender, dob, org_code, org_name, title, hire_date, email, location, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp['employee_id'], emp['name'], emp['gender'], emp['dob'],
                emp['org_code'], emp['org_name'], emp['title'], emp['hire_date'],
                emp['email'], emp['location'], emp['is_active']
            ))
        
        db.commit()
        return len(employees)
    except Exception as e:
        print(f"HRIS employees sync error: {e}")
        return 0

# HRIS 사용자 정보 조회 함수
def get_user_info(user_email):
    """사용자 정보 조회 (조직, 권한 포함)"""
    db = get_db()
    
    # HRIS 데이터 동기화 (데이터가 없는 경우 자동 동기화)
    employee_count = db.execute("SELECT COUNT(*) as count FROM hris_employees").fetchone()
    if employee_count['count'] == 0:
        print("HRIS 데이터가 없어서 자동 동기화를 실행합니다...")
        sync_hris_employees()
    
    # HRIS에서 사용자 정보 조회
    user_info = db.execute("""
        SELECT employee_id, name, org_code, org_name, title, email
        FROM hris_employees 
        WHERE email = ? AND is_active = 1
    """, (user_email,)).fetchone()
    
    if user_info:
        # 이원규는 Admin 권한 부여
        is_admin = user_info['email'] == 'lwk9589@gmail.com'
        
        return {
            'employee_id': user_info['employee_id'],
            'name': user_info['name'],
            'org_code': user_info['org_code'],
            'org_name': user_info['org_name'],
            'title': user_info['title'],
            'email': user_info['email'],
            'is_admin': is_admin
        }
    
    # 데모 사용자 (HRIS에 없는 경우)
    return {
        'employee_id': 'DEMO001',
        'name': 'Demo User',
        'org_code': 'UNKNOWN',
        'org_name': 'Unknown Department',
        'title': 'User',
        'email': user_email
    }

# Helper functions
def get_current_time():
    """Get current time in ISO format"""
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

def parse_time(time_str):
    """Parse ISO time string to datetime"""
    return datetime.fromisoformat(time_str.replace('Z', ''))

def get_room_status(db, room_id, room_type):
    """Determine current status of a room"""
    now = get_current_time()
    
    if room_type == 'MEETING':
        # Check for active reservation
        active = db.execute("""
            SELECT end_time FROM reservations 
            WHERE room_id = ? AND status = 'ACTIVE' 
            AND start_time <= ? AND end_time > ?
        """, (room_id, now, now)).fetchone()
        
        if active:
            return 'OCCUPIED', {'until': active['end_time']}
        
        # Check for upcoming reservation (within 30 minutes)
        upcoming = db.execute("""
            SELECT start_time FROM reservations 
            WHERE room_id = ? AND status = 'ACTIVE' 
            AND start_time > ? 
            ORDER BY start_time LIMIT 1
        """, (room_id, now)).fetchone()
        
        if upcoming:
            start_time = parse_time(upcoming['start_time'])
            time_diff = (start_time - parse_time(now)).total_seconds() / 60
            if time_diff <= 30:
                return 'RESERVED', {'start': upcoming['start_time']}
        
        return 'AVAILABLE', {}
    
    elif room_type == 'FOCUS':
        # Check for active occupancy
        active = db.execute("""
            SELECT start_time, timer_duration FROM occupancies 
            WHERE room_id = ? AND status = 'active'
        """, (room_id,)).fetchone()
        
        if active:
            start_time = parse_time(active['start_time'])
            end_time = start_time + timedelta(seconds=active['timer_duration'])
            return 'OCCUPIED', {'until': end_time.strftime('%Y-%m-%dT%H:%M:%S')}
        
        return 'AVAILABLE', {}
    
    return 'AVAILABLE', {}

# Main routes
@bp.route('/booker')
def booker_home():
    """Main dashboard page"""
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    user_info = get_user_info(user_email)
    lang = get_language_from_request(request)
    return render_template('booker/main.html', active='booker', user=user_info, lang=lang)

# API Routes
@bp.route('/api/rooms/status')
def rooms_status():
    """Get status of all rooms - unified API for both meeting rooms and focus rooms"""
    db = get_db()
    
    rooms = db.execute("""
        SELECT id, name, type, capacity, svg_id 
        FROM rooms 
        ORDER BY type, name
    """).fetchall()
    
    result = []
    for room in rooms:
        status, details = get_room_status(db, room['id'], room['type'])
        
        room_data = {
            'roomId': room['id'],
            'name': room['name'],
            'type': room['type'],
            'capacity': room['capacity'],
            'svgId': room['svg_id'],
            'status': status
        }
        
        if details:
            if 'until' in details:
                room_data['current'] = {'until': details['until']}
            if 'start' in details:
                room_data['next'] = {'start': details['start']}
        
        result.append(room_data)
    
    return jsonify(result)

@bp.route('/api/user/status')
def user_status():
    """Get current user's reservations and focus room status"""
    db = get_db()
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    
    # Get active focus room
    focus_room = db.execute("""
        SELECT r.id, r.name, o.start_time, o.timer_duration
        FROM occupancies o
        JOIN rooms r ON o.room_id = r.id
        WHERE o.status = 'active' AND r.type = 'FOCUS'
        LIMIT 1
    """).fetchone()
    
    # Get active meeting room reservations
    meeting_reservations = db.execute("""
        SELECT r.id, r.name, res.id as reservation_id, res.start_time, res.end_time
        FROM reservations res
        JOIN rooms r ON res.room_id = r.id
        WHERE res.status = 'ACTIVE' AND r.type = 'MEETING'
        AND res.start_time <= ? AND res.end_time > ?
        ORDER BY res.start_time
    """, (get_current_time(), get_current_time())).fetchall()
    
    # Get upcoming meeting room reservations
    upcoming_reservations = db.execute("""
        SELECT r.id, r.name, res.id as reservation_id, res.start_time, res.end_time
        FROM reservations res
        JOIN rooms r ON res.room_id = r.id
        WHERE res.status = 'ACTIVE' AND r.type = 'MEETING'
        AND res.start_time > ?
        ORDER BY res.start_time
    """, (get_current_time(),)).fetchall()
    
    return jsonify({
        'focus_room': dict(focus_room) if focus_room else None,
        'active_meeting_rooms': [dict(r) for r in meeting_reservations],
        'upcoming_meeting_rooms': [dict(r) for r in upcoming_reservations]
    })

@bp.route('/api/rooms/<int:room_id>/reservations', methods=['GET', 'POST'])
def room_reservations(room_id):
    """Handle meeting room reservations"""
    db = get_db()
    
    # Verify room exists and is meeting room
    room = db.execute("SELECT type FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room or room['type'] != 'MEETING':
        return jsonify({'error': 'Meeting room not found'}), 404
    
    if request.method == 'GET':
        # Get reservations for a room
        from_time = request.args.get('from', get_current_time())
        to_time = request.args.get('to', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'))
        
        reservations = db.execute("""
            SELECT id, start_time, end_time, status, created_at
            FROM reservations 
            WHERE room_id = ? AND status = 'ACTIVE'
            AND start_time < ? AND end_time > ?
            ORDER BY start_time
        """, (room_id, to_time, from_time)).fetchall()
        
        return jsonify([dict(r) for r in reservations])
    
    elif request.method == 'POST':
        # Create new reservation
        data = request.get_json()
        start_time = data.get('start')
        end_time = data.get('end')
        
        user_email = 'lwk9589@gmail.com'  # 현재 사용자 (실제로는 세션에서 가져와야 함)
        target_id = f"R-{room_id}-{start_time}"
        
        # 예약 시도 로그
        log_event(user_email, 'booker', 'reservation_attempt', target_id, {
            'roomId': str(room_id),
            'start': start_time,
            'end': end_time,
            'source': 'user'
        })
        
        if not start_time or not end_time:
            # 예약 실패 로그
            log_event(user_email, 'booker', 'reservation_failed', target_id, {
                'roomId': str(room_id),
                'start': start_time,
                'end': end_time,
                'reason': 'invalid',
                'source': 'user'
            })
            return jsonify({'error': 'Start and end time required'}), 400
        
        # Validate time order
        if parse_time(start_time) >= parse_time(end_time):
            # 예약 실패 로그
            log_event(user_email, 'booker', 'reservation_failed', target_id, {
                'roomId': str(room_id),
                'start': start_time,
                'end': end_time,
                'reason': 'invalid',
                'source': 'user'
            })
            return jsonify({'error': 'End time must be after start time'}), 400
        
        # Check for conflicts
        conflict = db.execute("""
            SELECT 1 FROM reservations 
            WHERE room_id = ? AND status = 'ACTIVE'
            AND NOT (end_time <= ? OR start_time >= ?)
        """, (room_id, start_time, end_time)).fetchone()
        
        if conflict:
            # 예약 실패 로그 (중복)
            log_event(user_email, 'booker', 'reservation_failed', target_id, {
                'roomId': str(room_id),
                'start': start_time,
                'end': end_time,
                'reason': 'overlap',
                'source': 'user'
            })
            return jsonify({'error': 'Time conflict with existing reservation'}), 409
        
        # Create reservation
        try:
            cursor = db.execute("""
                INSERT INTO reservations (room_id, start_time, end_time)
                VALUES (?, ?, ?)
            """, (room_id, start_time, end_time))
            
            reservation_id = cursor.lastrowid
            
            # Get room info for calendar event
            room_info = db.execute("""
                SELECT name, floor FROM rooms WHERE id = ?
            """, (room_id,)).fetchone()
            
            # Create calendar event for the reservation
            user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
            
            if room_info:
                # Store times as-is without timezone conversion
                # JavaScript will handle timezone parsing consistently
                calendar_start = start_time if 'T' in start_time else f"{start_time}T00:00:00"
                calendar_end = end_time if 'T' in end_time else f"{end_time}T00:00:00"
                
                room_location = f"{room_info['name']}"
                if room_info['floor']:
                    room_location += f" ({room_info['floor']}층)"
                
                db.execute("""
                    INSERT INTO calendar_events 
                    (title, description, start_at, end_at, all_day, location, event_type, owner_email, created_by)
                    VALUES (?, ?, ?, ?, 0, ?, 'MY', ?, ?)
                """, (
                    f"회의실 예약 - {room_info['name']}",
                    f"자동 생성된 회의실 예약 일정\n예약 ID: {reservation_id}",
                    calendar_start,
                    calendar_end,
                    room_location,
                    user_email,
                    user_email
                ))
            
            db.commit()
            
            # 예약 성공 로그
            log_event(user_email, 'booker', 'reservation_success', target_id, {
                'roomId': str(room_id),
                'start': start_time,
                'end': end_time,
                'reservationId': str(reservation_id),
                'source': 'user'
            })
            
            return jsonify({
                'id': reservation_id,
                'room_id': room_id,
                'start_time': start_time,
                'end_time': end_time,
                'status': 'ACTIVE',
                'calendar_event_created': room_info is not None
            }), 201
        except sqlite3.Error as e:
            return jsonify({'error': 'Database error'}), 500

@bp.route('/api/rooms/<int:room_id>/reservations/<int:reservation_id>/cancel', methods=['POST'])
def cancel_reservation(room_id, reservation_id):
    """Cancel a meeting room reservation"""
    db = get_db()
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    
    # Verify reservation exists and is active
    reservation = db.execute("""
        SELECT id, start_time, end_time FROM reservations 
        WHERE id = ? AND room_id = ? AND status = 'ACTIVE'
    """, (reservation_id, room_id)).fetchone()
    
    if not reservation:
        return jsonify({'error': 'Reservation not found'}), 404
    
    # Check if reservation has already started
    now = get_current_time()
    if parse_time(reservation['start_time']) <= parse_time(now):
        return jsonify({'error': 'Cannot cancel reservation that has already started'}), 400
    
    # Cancel reservation
    try:
        db.execute("""
            UPDATE reservations 
            SET status = 'CANCELLED' 
            WHERE id = ?
        """, (reservation_id,))
        
        # Also delete related calendar event
        user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
        
        # Find and delete calendar event with matching reservation ID
        deleted_events = db.execute("""
            DELETE FROM calendar_events 
            WHERE owner_email = ? 
            AND event_type = 'MY' 
            AND description LIKE ?
        """, (user_email, f'%예약 ID: {reservation_id}%'))
        
        db.commit()
        
        return jsonify({
            'id': reservation_id,
            'status': 'CANCELLED',
            'message': 'Reservation cancelled successfully',
            'calendar_event_deleted': True
        })
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/rooms/<int:room_id>/checkout', methods=['POST'])
def checkout_meeting_room(room_id):
    """Check out from a meeting room (early end)"""
    db = get_db()
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    
    # Find active reservation for this room
    reservation = db.execute("""
        SELECT id, start_time, end_time FROM reservations 
        WHERE room_id = ? AND status = 'ACTIVE'
        AND start_time <= ? AND end_time > ?
        ORDER BY start_time DESC LIMIT 1
    """, (room_id, get_current_time(), get_current_time())).fetchone()
    
    if not reservation:
        return jsonify({'error': 'No active reservation found for this room'}), 404
    
    # End the reservation early
    try:
        db.execute("""
            UPDATE reservations 
            SET end_time = ?, status = 'CANCELLED'
            WHERE id = ?
        """, (get_current_time(), reservation['id']))
        db.commit()
        
        return jsonify({
            'id': reservation['id'],
            'room_id': room_id,
            'end_time': get_current_time(),
            'message': 'Checked out successfully'
        })
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/focus/<int:room_id>/claim', methods=['POST'])
def claim_focus_room(room_id):
    """Claim a focus room (start using) - one per user"""
    db = get_db()
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    start_time = get_current_time()
    target_id = f"F-{room_id}-{start_time}"
    
    # Verify room exists and is focus room
    room = db.execute("SELECT type FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room or room['type'] != 'FOCUS':
        return jsonify({'error': 'Focus room not found'}), 404
    
    # Check if already occupied by anyone
    active = db.execute("""
        SELECT 1 FROM occupancies 
        WHERE room_id = ? AND status = 'active'
    """, (room_id,)).fetchone()
    
    if active:
        return jsonify({'error': 'Room already occupied'}), 409
    
    # Check if user already has an active focus room
    user_active = db.execute("""
        SELECT r.name FROM occupancies o
        JOIN rooms r ON o.room_id = r.id
        WHERE o.status = 'active' AND r.type = 'FOCUS'
        LIMIT 1
    """).fetchone()
    
    if user_active:
        return jsonify({'error': f'You already have an active focus room: {user_active["name"]}'}), 409
    
    # Create occupancy
    timer_duration = 7200  # 2 hours in seconds
    
    try:
        cursor = db.execute("""
            INSERT INTO occupancies (room_id, start_time, timer_duration)
            VALUES (?, ?, ?)
        """, (room_id, start_time, timer_duration))
        db.commit()
        
        end_time = (parse_time(start_time) + timedelta(seconds=timer_duration)).strftime('%Y-%m-%dT%H:%M:%S')
        
        # 포커스룸 찜하기 성공 로그
        log_event(user_email, 'booker', 'claim_focusroom', target_id, {
            'roomId': str(room_id),
            'until': end_time,
            'occupancyId': str(cursor.lastrowid),
            'source': 'user'
        })
        
        return jsonify({
            'id': cursor.lastrowid,
            'room_id': room_id,
            'start_time': start_time,
            'estimated_end': end_time,
            'timer_duration': timer_duration
        }), 201
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/focus/<int:room_id>/extend', methods=['POST'])
def extend_focus_room(room_id):
    """Extend focus room usage by 30 minutes"""
    db = get_db()
    
    # Find active occupancy
    occupancy = db.execute("""
        SELECT id, timer_duration FROM occupancies 
        WHERE room_id = ? AND status = 'active'
    """, (room_id,)).fetchone()
    
    if not occupancy:
        return jsonify({'error': 'No active occupancy found'}), 404
    
    # Extend by 30 minutes (1800 seconds)
    new_duration = occupancy['timer_duration'] + 1800
    
    try:
        db.execute("""
            UPDATE occupancies 
            SET timer_duration = ? 
            WHERE id = ?
        """, (new_duration, occupancy['id']))
        db.commit()
        
        return jsonify({
            'id': occupancy['id'],
            'timer_duration': new_duration,
            'extended_by': 1800
        })
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/focus/<int:room_id>/release', methods=['POST'])
def release_focus_room(room_id):
    """Release focus room (check out)"""
    db = get_db()
    
    # Find active occupancy
    occupancy = db.execute("""
        SELECT id FROM occupancies 
        WHERE room_id = ? AND status = 'active'
    """, (room_id,)).fetchone()
    
    if not occupancy:
        return jsonify({'error': 'No active occupancy found'}), 404
    
    # Mark as completed
    end_time = get_current_time()
    
    try:
        db.execute("""
            UPDATE occupancies 
            SET status = 'completed', end_time = ? 
            WHERE id = ?
        """, (end_time, occupancy['id']))
        db.commit()
        
        return jsonify({
            'id': occupancy['id'],
            'end_time': end_time,
            'status': 'completed'
        })
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

# Legacy booking support for backward compatibility
def has_conflict(db, employee_id, resource_type, resource_id, date, slot):
    # resource conflict
    row = db.execute("""SELECT 1 FROM bookings WHERE resource_type=? AND resource_id=? AND date=? AND slot=?""",
                     (resource_type, resource_id, date, slot)).fetchone()
    if row: return True
    # employee double-book
    row = db.execute("""SELECT 1 FROM bookings WHERE employee_id=? AND date=? AND slot=?""", (employee_id, date, slot)).fetchone()
    return bool(row)

@bp.route('/booker/reserve', methods=['POST'])
def legacy_reserve():
    """Legacy reservation endpoint for backward compatibility"""
    employee_id = 1  # demo user
    resource_type = request.form.get('resource_type','room')
    resource_id = int(request.form.get('resource_id','1'))
    date = request.form.get('date')
    slot = request.form.get('slot')
    db = get_db()
    if has_conflict(db, employee_id, resource_type, resource_id, date, slot):
        return redirect('/booker')
    db.execute("INSERT INTO bookings(employee_id,resource_type,resource_id,date,slot) VALUES(?,?,?,?,?)",
               (employee_id, resource_type, resource_id, date, slot))
    db.commit()
    return redirect('/booker')
