
from flask import Blueprint, request, render_template, redirect, jsonify
from db import get_db
from datetime import datetime, timedelta
import sqlite3
import json

bp = Blueprint('booker', __name__)

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
    return render_template('booker/main.html', active='booker', user={'email': 'user014@example.com'})

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
    user_id = 1  # Demo user ID
    
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
        
        if not start_time or not end_time:
            return jsonify({'error': 'Start and end time required'}), 400
        
        # Validate time order
        if parse_time(start_time) >= parse_time(end_time):
            return jsonify({'error': 'End time must be after start time'}), 400
        
        # Check for conflicts
        conflict = db.execute("""
            SELECT 1 FROM reservations 
            WHERE room_id = ? AND status = 'ACTIVE'
            AND NOT (end_time <= ? OR start_time >= ?)
        """, (room_id, start_time, end_time)).fetchone()
        
        if conflict:
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
            user_email = 'user014@example.com'  # 한지원 - HR 팀 (calendar과 동일)
            
            if room_info:
                # Convert ISO time to timezone-aware format
                calendar_start = start_time if 'T' in start_time else f"{start_time}T00:00:00"
                calendar_end = end_time if 'T' in end_time else f"{end_time}T00:00:00"
                
                # Add timezone if not present
                if '+' not in calendar_start and 'Z' not in calendar_start:
                    calendar_start += '+09:00'
                if '+' not in calendar_end and 'Z' not in calendar_end:
                    calendar_end += '+09:00'
                
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
    user_id = 1  # Demo user ID
    
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
        user_email = 'user014@example.com'  # 한지원 - HR 팀 (calendar과 동일)
        
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
    user_id = 1  # Demo user ID
    
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
    user_id = 1  # Demo user ID - in real app, get from session/auth
    
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
    start_time = get_current_time()
    timer_duration = 7200  # 2 hours in seconds
    
    try:
        cursor = db.execute("""
            INSERT INTO occupancies (room_id, start_time, timer_duration)
            VALUES (?, ?, ?)
        """, (room_id, start_time, timer_duration))
        db.commit()
        
        end_time = (parse_time(start_time) + timedelta(seconds=timer_duration)).strftime('%Y-%m-%dT%H:%M:%S')
        
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
