import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, redirect, url_for, jsonify, flash
from db import get_db

bp = Blueprint('calendar', __name__)

# HRIS 데이터 동기화 함수들
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

def sync_hris_vacations():
    """HRIS vacations_2025-09.json 데이터를 동기화"""
    db = get_db()
    
    try:
        with open('HRIS data/vacations_2025-09.json', 'r', encoding='utf-8') as f:
            vacations = json.load(f)
        
        # 기존 데이터 삭제 후 새로 삽입
        db.execute("DELETE FROM vacation_events")
        
        for vac in vacations:
            db.execute("""
                INSERT INTO vacation_events 
                (employee_id, name, org_code, org_name, type, start_at, end_at, all_day, status, hris_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vac['employee_id'], vac['name'], vac['org_code'], vac['org_name'],
                vac['type'], vac['start_at'], vac['end_at'], vac['all_day'],
                vac['status'], vac['updated_at']
            ))
        
        db.commit()
        
        # 구독된 휴가 이벤트의 동기화 처리
        sync_subscribed_vacation_events()
        
        return len(vacations)
    except Exception as e:
        print(f"HRIS vacations sync error: {e}")
        return 0

def sync_subscribed_vacation_events():
    """구독된 휴가 이벤트들의 동기화 처리"""
    db = get_db()
    
    # 구독된 휴가 이벤트들을 조회
    subscriptions = db.execute("""
        SELECT s.*, v.status as vacation_status, v.start_at, v.end_at, v.title as vacation_title
        FROM event_subscriptions s
        LEFT JOIN vacation_events v ON s.source_event_id = v.id
        WHERE s.source_table = 'vacation_events'
    """).fetchall()
    
    for sub in subscriptions:
        if sub['vacation_status'] == 'CANCELLED' or not sub['vacation_status']:
            # 원본이 취소되었거나 존재하지 않으면 My 이벤트에서 제거
            db.execute("DELETE FROM calendar_events WHERE id = ?", (sub['my_event_id'],))
            db.execute("DELETE FROM event_subscriptions WHERE id = ?", (sub['id'],))
        else:
            # 원본이 변경되었으면 My 이벤트 업데이트
            db.execute("""
                UPDATE calendar_events 
                SET start_at = ?, end_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (sub['start_at'], sub['end_at'], sub['my_event_id']))
    
    db.commit()

def get_user_info(user_email):
    """사용자 정보 조회 (조직, 권한 포함)"""
    db = get_db()
    
    # HRIS에서 사용자 정보 조회
    user_info = db.execute("""
        SELECT employee_id, name, org_code, org_name, title, email
        FROM hris_employees 
        WHERE email = ? AND is_active = 1
    """, (user_email,)).fetchone()
    
    if user_info:
        # HR팀 또는 관리자 권한 체크
        is_hr_admin = user_info['org_code'] in ['HR'] or 'Manager' in user_info['title'] or 'Director' in user_info['title']
        
        return {
            'employee_id': user_info['employee_id'],
            'name': user_info['name'],
            'org_code': user_info['org_code'],
            'org_name': user_info['org_name'],
            'title': user_info['title'],
            'email': user_info['email'],
            'is_hr_admin': is_hr_admin
        }
    
    # 데모 사용자 (HRIS에 없는 경우)
    return {
        'employee_id': 'DEMO001',
        'name': 'Demo User',
        'org_code': 'HR',  # 데모용으로 HR 권한 부여
        'org_name': 'People Operations',
        'title': 'Admin',
        'email': user_email,
        'is_hr_admin': True  # 데모용으로 관리자 권한 부여
    }

def get_user_default_org(user_email):
    """사용자의 기본 조직 설정 조회"""
    db = get_db()
    setting = db.execute("""
        SELECT setting_value FROM user_settings 
        WHERE user_email = ? AND setting_key = 'default_org'
    """, (user_email,)).fetchone()
    
    if setting:
        return setting['setting_value']
    
    # 기본값이 없으면 사용자 정보에서 org_code 사용
    user_info = get_user_info(user_email)
    return user_info['org_code']

def set_user_default_org(user_email, org_code):
    """사용자의 기본 조직 설정 저장"""
    db = get_db()
    db.execute("""
        INSERT OR REPLACE INTO user_settings (user_email, setting_key, setting_value)
        VALUES (?, 'default_org', ?)
    """, (user_email, org_code))
    db.commit()

# Calendar Hub 메인 라우트
@bp.route('/calendar')
def calendar_home():
    """Calendar Hub 메인 페이지"""
    user_email = 'user014@example.com'  # 데모용 고정값 (한지원 - HR 팀)
    
    # 사용자 정보 조회
    user_info = get_user_info(user_email)
    
    # URL 파라미터 처리
    tab = request.args.get('tab', 'my')
    view = request.args.get('view', 'week')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    org = request.args.get('org', get_user_default_org(user_email))
    show_birthdays = request.args.get('showBirthdays', '0') == '1'
    
    # 날짜 범위 계산
    try:
        current_date = datetime.fromisoformat(date)
    except:
        current_date = datetime.now()
    
    if view == 'month':
        # 월 뷰: 해당 월의 첫날부터 마지막날까지
        start_date = current_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
    elif view == 'week':
        # 주 뷰: 월요일부터 일요일까지
        days_since_monday = current_date.weekday()
        start_date = current_date - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6)
    else:  # day
        # 일 뷰: 해당 일만
        start_date = current_date
        end_date = current_date
    
    # 조직 목록 조회
    db = get_db()
    orgs = db.execute("""
        SELECT DISTINCT org_code, org_name FROM hris_employees 
        WHERE is_active = 1 ORDER BY org_name
    """).fetchall()
    
    context = {
        'active': 'calendar',
        'user': user_info,  # 확장된 사용자 정보 전달
        'tab': tab,
        'view': view,
        'date': date,
        'current_date': current_date,
        'start_date': start_date,
        'end_date': end_date,
        'org': org,
        'show_birthdays': show_birthdays,
        'orgs': orgs
    }
    
    return render_template('calendar/hub.html', **context)

# API 엔드포인트들
@bp.route('/api/calendar/events')
def api_get_events():
    """캘린더 이벤트 조회 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    tab = request.args.get('tab', 'my')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    org = request.args.get('org')
    show_birthdays = request.args.get('showBirthdays', '0') == '1'
    
    db = get_db()
    events = []
    
    if tab == 'my':
        # My Calendar 이벤트들
        # 날짜 비교를 위해 ISO8601 형식과 호환되도록 수정
        start_filter = f"{start_date}T00:00:00+09:00" if start_date else "1900-01-01T00:00:00+09:00"
        end_filter = f"{end_date}T23:59:59+09:00" if end_date else "2099-12-31T23:59:59+09:00"
        
        my_events = db.execute("""
            SELECT ce.*, 
                   CASE WHEN es.id IS NOT NULL THEN 1 ELSE 0 END as is_subscribed,
                   es.source_table, es.source_event_id
            FROM calendar_events ce
            LEFT JOIN event_subscriptions es ON ce.id = es.my_event_id
            WHERE ce.owner_email = ? AND ce.event_type = 'MY'
              AND ce.start_at >= ? AND ce.start_at <= ?
            ORDER BY ce.start_at
        """, (user_email, start_filter, end_filter)).fetchall()
        
        for event in my_events:
            events.append({
                'id': event['id'],
                'title': event['title'],
                'start': event['start_at'],
                'end': event['end_at'],
                'allDay': bool(event['all_day']),
                'type': 'my',
                'status': event['status'],
                'location': event['location'],
                'description': event['description'],
                'isSubscribed': bool(event['is_subscribed']),
                'sourceTable': event['source_table'],
                'sourceEventId': event['source_event_id']
            })
    
    elif tab == 'vacation':
        # Vacation Calendar 이벤트들 (조직별 필터링)
        # 날짜 비교를 위해 ISO8601 형식과 호환되도록 수정
        start_filter = f"{start_date}T00:00:00+09:00" if start_date else "1900-01-01T00:00:00+09:00"
        end_filter = f"{end_date}T23:59:59+09:00" if end_date else "2099-12-31T23:59:59+09:00"
        
        # '전체 팀' 선택 시 조직 필터링 제거
        if org == 'ALL':
            vacation_events = db.execute("""
                SELECT * FROM vacation_events 
                WHERE status = 'ACTIVE'
                  AND start_at >= ? AND start_at <= ?
                ORDER BY start_at
            """, (start_filter, end_filter)).fetchall()
        else:
            vacation_events = db.execute("""
                SELECT * FROM vacation_events 
                WHERE org_code = ? AND status = 'ACTIVE'
                  AND start_at >= ? AND start_at <= ?
                ORDER BY start_at
            """, (org, start_filter, end_filter)).fetchall()
        
        for event in vacation_events:
            # 휴가 종류 표시: HALF(반차)만 표시하고 나머지는 이름만
            if event['type'] == 'HALF':
                title = f"{event['name']} (반차)"
            else:
                title = event['name']
            
            events.append({
                'id': event['id'],
                'title': title,
                'start': event['start_at'],
                'end': event['end_at'],
                'allDay': bool(event['all_day']),
                'type': 'vacation',
                'employeeName': event['name'],
                'vacationType': event['type'],
                'orgName': event['org_name']
            })
        
        # 생일자 표시 (선택 시)
        if show_birthdays:
            # '전체 팀' 선택 시 모든 팀의 생일자 표시
            if org == 'ALL':
                birthday_events = db.execute("""
                    SELECT name, dob FROM hris_employees 
                    WHERE is_active = 1
                """).fetchall()
            else:
                birthday_events = db.execute("""
                    SELECT name, dob FROM hris_employees 
                    WHERE org_code = ? AND is_active = 1
                """, (org,)).fetchall()
            
            for emp in birthday_events:
                try:
                    # 생일을 현재 연도로 변환
                    birth_date = datetime.fromisoformat(emp['dob'])
                    current_year = datetime.now().year
                    birthday_this_year = birth_date.replace(year=current_year)
                    
                    # 조회 범위에 포함되는지 확인
                    if start_date <= birthday_this_year.strftime('%Y-%m-%d') <= end_date:
                        events.append({
                            'id': f"birthday_{emp['name']}",
                            'title': f"🎂 {emp['name']} 생일",
                            'start': birthday_this_year.strftime('%Y-%m-%d'),
                            'end': birthday_this_year.strftime('%Y-%m-%d'),
                            'allDay': True,
                            'type': 'birthday'
                        })
                except:
                    continue
    
    elif tab == 'official':
        # Official Calendar 이벤트들
        # 날짜 비교를 위해 ISO8601 형식과 호환되도록 수정
        start_filter = f"{start_date}T00:00:00+09:00" if start_date else "1900-01-01T00:00:00+09:00"
        end_filter = f"{end_date}T23:59:59+09:00" if end_date else "2099-12-31T23:59:59+09:00"
        
        official_events = db.execute("""
            SELECT * FROM calendar_events 
            WHERE event_type = 'OFFICIAL'
              AND start_at >= ? AND start_at <= ?
            ORDER BY start_at
        """, (start_filter, end_filter)).fetchall()
        
        for event in official_events:
            events.append({
                'id': event['id'],
                'title': event['title'],
                'start': event['start_at'],
                'end': event['end_at'],
                'allDay': bool(event['all_day']),
                'type': 'official',
                'status': event['status'],
                'location': event['location'],
                'description': event['description']
            })
    
    return jsonify(events)

# 이벤트 생성
@bp.route('/api/calendar/events', methods=['POST'])
def api_create_event():
    """이벤트 생성 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    data = request.get_json()
    
    db = get_db()
    
    # 권한 체크 (Official 이벤트는 HR/Admin만 생성 가능)
    if data.get('eventType') == 'OFFICIAL':
        user_info = get_user_info(user_email)
        if not user_info['is_hr_admin']:
            return jsonify({'error': 'Official 이벤트는 HR/Admin만 생성할 수 있습니다'}), 403
    
    db.execute("""
        INSERT INTO calendar_events 
        (title, description, start_at, end_at, all_day, location, event_type, owner_email, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['title'], data.get('description', ''), data['start'], data['end'],
        data.get('allDay', False), data.get('location', ''), data['eventType'],
        user_email, user_email
    ))
    
    db.commit()
    
    return jsonify({'success': True})

# 이벤트 구독
@bp.route('/api/calendar/subscribe', methods=['POST'])
def api_subscribe_event():
    """이벤트 구독 API"""
    try:
        user_email = 'user014@example.com'  # 한지원 - HR 팀
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        if 'sourceTable' not in data or 'sourceEventId' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        source_table = data['sourceTable']  # 'vacation_events' or 'calendar_events'
        source_event_id = data['sourceEventId']
        
    except Exception as e:
        return jsonify({'error': 'Invalid request data'}), 400
    
    try:
        db = get_db()
        
        # 원본 이벤트 조회
        if source_table == 'vacation_events':
            source_event = db.execute("""
                SELECT * FROM vacation_events WHERE id = ?
            """, (source_event_id,)).fetchone()
            
            if not source_event:
                return jsonify({'error': 'Event not found'}), 404
            
            title = f"{source_event['name']} ({source_event['type']})"
            description = f"구독된 휴가 일정 - {source_event['org_name']}"
        else:
            source_event = db.execute("""
                SELECT * FROM calendar_events WHERE id = ? AND event_type = 'OFFICIAL'
            """, (source_event_id,)).fetchone()
            
            if not source_event:
                return jsonify({'error': 'Event not found'}), 404
            
            title = source_event['title']
            description = f"구독된 공식 일정\n{source_event['description'] or ''}"
        
        # 이미 구독했는지 확인
        existing = db.execute("""
            SELECT id FROM event_subscriptions 
            WHERE subscriber_email = ? AND source_table = ? AND source_event_id = ?
        """, (user_email, source_table, source_event_id)).fetchone()
        
        if existing:
            return jsonify({'error': 'Already subscribed'}), 400
        
        # My Calendar에 이벤트 생성
        cursor = db.execute("""
            INSERT INTO calendar_events 
            (title, description, start_at, end_at, all_day, location, event_type, owner_email, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 'MY', ?, ?)
        """, (
            title, description, source_event['start_at'], source_event['end_at'],
            source_event['all_day'], source_event['location'] if source_event['location'] else '', user_email, user_email
        ))
        
        my_event_id = cursor.lastrowid
        
        # 구독 관계 생성
        db.execute("""
            INSERT INTO event_subscriptions 
            (subscriber_email, source_table, source_event_id, my_event_id)
            VALUES (?, ?, ?, ?)
        """, (user_email, source_table, source_event_id, my_event_id))
        
        db.commit()
        
        return jsonify({'success': True, 'message': '내 캘린더에 구독되었습니다'})
    
    except Exception as e:
        return jsonify({'error': f'Subscription failed: {str(e)}'}), 500

# HRIS 동기화
@bp.route('/api/calendar/sync-hris', methods=['POST'])
def api_sync_hris():
    """HRIS 데이터 동기화 API (HR/Admin 전용)"""
    emp_count = sync_hris_employees()
    vac_count = sync_hris_vacations()
    
    return jsonify({
        'success': True,
        'message': f'HRIS 동기화 완료: 직원 {emp_count}명, 휴가 {vac_count}건'
    })

# 이벤트 수정
@bp.route('/api/calendar/events/<int:event_id>', methods=['PUT'])
def api_update_event(event_id):
    """이벤트 수정 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    data = request.get_json()
    
    db = get_db()
    
    # 권한 체크: 본인 이벤트이거나 Official 이벤트의 경우 HR/Admin 권한 체크
    event = db.execute("""
        SELECT * FROM calendar_events WHERE id = ?
    """, (event_id,)).fetchone()
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    if event['owner_email'] != user_email and event['event_type'] == 'OFFICIAL':
        # Official 이벤트는 HR/Admin만 수정 가능
        user_info = get_user_info(user_email)
        if not user_info['is_hr_admin']:
            return jsonify({'error': 'Official 이벤트는 HR/Admin만 수정할 수 있습니다'}), 403
    elif event['owner_email'] != user_email:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # 구독된 이벤트는 수정 불가
    subscription = db.execute("""
        SELECT id FROM event_subscriptions WHERE my_event_id = ?
    """, (event_id,)).fetchone()
    
    if subscription:
        return jsonify({'error': 'Subscribed events cannot be edited'}), 400
    
    db.execute("""
        UPDATE calendar_events 
        SET title = ?, description = ?, start_at = ?, end_at = ?, 
            all_day = ?, location = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data['title'], data.get('description', ''), data['start'], data['end'],
        data.get('allDay', False), data.get('location', ''), event_id
    ))
    
    db.commit()
    
    return jsonify({'success': True})

# 이벤트 삭제
@bp.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
def api_delete_event(event_id):
    """이벤트 삭제 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    
    db = get_db()
    
    # 권한 체크
    event = db.execute("""
        SELECT * FROM calendar_events WHERE id = ?
    """, (event_id,)).fetchone()
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    if event['owner_email'] != user_email and event['event_type'] == 'OFFICIAL':
        # Official 이벤트는 HR/Admin만 삭제 가능
        user_info = get_user_info(user_email)
        if not user_info['is_hr_admin']:
            return jsonify({'error': 'Official 이벤트는 HR/Admin만 삭제할 수 있습니다'}), 403
    elif event['owner_email'] != user_email:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # 구독 관계가 있는 경우 처리
    if event['event_type'] == 'OFFICIAL':
        # Official 이벤트가 삭제되면 구독된 My 이벤트들도 제거
        subscriptions = db.execute("""
            SELECT my_event_id FROM event_subscriptions 
            WHERE source_table = 'calendar_events' AND source_event_id = ?
        """, (event_id,)).fetchall()
        
        for sub in subscriptions:
            db.execute("DELETE FROM calendar_events WHERE id = ?", (sub['my_event_id'],))
        
        db.execute("""
            DELETE FROM event_subscriptions 
            WHERE source_table = 'calendar_events' AND source_event_id = ?
        """, (event_id,))
    else:
        # My 이벤트가 삭제되면 관련 구독 관계만 제거
        db.execute("DELETE FROM event_subscriptions WHERE my_event_id = ?", (event_id,))
    
    db.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    db.commit()
    
    return jsonify({'success': True})

# 구독 해제 (Unsubscribe)
@bp.route('/api/calendar/unsubscribe', methods=['POST'])
def api_unsubscribe_event():
    """이벤트 구독 해제 API"""
    try:
        user_email = 'user014@example.com'  # 한지원 - HR 팀
        data = request.get_json()
        
        if not data or 'myEventId' not in data:
            return jsonify({'error': 'Missing myEventId'}), 400
        
        my_event_id = data['myEventId']
        
        db = get_db()
        
        # 구독 관계 조회
        subscription = db.execute("""
            SELECT * FROM event_subscriptions WHERE my_event_id = ? AND subscriber_email = ?
        """, (my_event_id, user_email)).fetchone()
        
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        # My 이벤트와 구독 관계 삭제
        db.execute("DELETE FROM calendar_events WHERE id = ?", (my_event_id,))
        db.execute("DELETE FROM event_subscriptions WHERE id = ?", (subscription['id'],))
        
        db.commit()
        
        return jsonify({'success': True, 'message': '구독이 해지되어 내 캘린더에서 제거되었습니다'})
    
    except Exception as e:
        return jsonify({'error': f'Unsubscribe failed: {str(e)}'}), 500

# 연결 해제 (Unlink)
@bp.route('/api/calendar/unlink', methods=['POST'])
def api_unlink_event():
    """이벤트 연결 해제 API"""
    try:
        user_email = 'user014@example.com'  # 한지원 - HR 팀
        data = request.get_json()
        
        if not data or 'myEventId' not in data:
            return jsonify({'error': 'Missing myEventId'}), 400
        
        my_event_id = data['myEventId']
        
        db = get_db()
        
        # 구독 관계 조회
        subscription = db.execute("""
            SELECT * FROM event_subscriptions WHERE my_event_id = ? AND subscriber_email = ?
        """, (my_event_id, user_email)).fetchone()
        
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        # 구독 관계만 삭제 (My 이벤트는 유지)
        db.execute("DELETE FROM event_subscriptions WHERE id = ?", (subscription['id'],))
        
        # 이벤트 설명 업데이트 (연결 해제됨을 표시)
        db.execute("""
            UPDATE calendar_events 
            SET description = COALESCE(description, '') || '\n[연결 해제됨: 원본과 동기화되지 않음]',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (my_event_id,))
        
        db.commit()
        
        return jsonify({'success': True, 'message': '연결이 해제되어 독립 일정으로 전환되었습니다'})
    
    except Exception as e:
        return jsonify({'error': f'Unlink failed: {str(e)}'}), 500

# 이벤트 상세 조회
@bp.route('/api/calendar/events/<int:event_id>')
def api_get_event(event_id):
    """이벤트 상세 조회 API"""
    db = get_db()
    
    event = db.execute("""
        SELECT ce.*, 
               CASE WHEN es.id IS NOT NULL THEN 1 ELSE 0 END as is_subscribed,
               es.source_table, es.source_event_id, es.user_memo
        FROM calendar_events ce
        LEFT JOIN event_subscriptions es ON ce.id = es.my_event_id
        WHERE ce.id = ?
    """, (event_id,)).fetchone()
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    return jsonify({
        'id': event['id'],
        'title': event['title'],
        'description': event['description'],
        'start': event['start_at'],
        'end': event['end_at'],
        'allDay': bool(event['all_day']),
        'location': event['location'],
        'eventType': event['event_type'],
        'status': event['status'],
        'isSubscribed': bool(event['is_subscribed']),
        'sourceTable': event['source_table'],
        'sourceEventId': event['source_event_id'],
        'userMemo': event['user_memo']
    })

# Vacation 이벤트 상세 조회
@bp.route('/api/calendar/vacation-events/<int:event_id>')
def api_get_vacation_event(event_id):
    """휴가 이벤트 상세 조회 API"""
    db = get_db()
    
    event = db.execute("""
        SELECT * FROM vacation_events WHERE id = ?
    """, (event_id,)).fetchone()
    
    if not event:
        return jsonify({'error': 'Vacation event not found'}), 404
    
    return jsonify({
        'id': event['id'],
        'employeeId': event['employee_id'],
        'name': event['name'],
        'orgCode': event['org_code'],
        'orgName': event['org_name'],
        'type': event['type'],
        'start': event['start_at'],
        'end': event['end_at'],
        'allDay': bool(event['all_day']),
        'status': event['status']
    })

# 사용자 설정
@bp.route('/api/calendar/user-settings', methods=['POST'])
def api_save_user_settings():
    """사용자 설정 저장 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    data = request.get_json()
    
    if 'defaultOrg' in data:
        set_user_default_org(user_email, data['defaultOrg'])
    
    return jsonify({'success': True})

@bp.route('/api/calendar/user-settings')
def api_get_user_settings():
    """사용자 설정 조회 API"""
    user_email = 'user014@example.com'  # 한지원 - HR 팀
    
    db = get_db()
    settings = db.execute("""
        SELECT setting_key, setting_value FROM user_settings 
        WHERE user_email = ?
    """, (user_email,)).fetchall()
    
    result = {}
    for setting in settings:
        result[setting['setting_key']] = setting['setting_value']
    
    return jsonify(result)