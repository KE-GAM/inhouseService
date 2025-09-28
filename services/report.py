from flask import Blueprint, request, render_template, jsonify, redirect, url_for
from db import get_db
from datetime import datetime, timedelta
from i18n import get_language_from_request
import sqlite3
import json

bp = Blueprint('report', __name__)

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
    if time_str:
        return datetime.fromisoformat(time_str.replace('Z', ''))
    return datetime.now()

def get_status_color(status):
    """Get color for status"""
    colors = {
        'OPEN': 'white',
        'IN_PROGRESS': 'warning',
        'DONE': 'success',
        'CANNOT_FIX': 'danger'
    }
    return colors.get(status, 'secondary')

def get_status_badge(status):
    """Get Bootstrap badge class for status"""
    colors = {
        'OPEN': 'badge-light',
        'IN_PROGRESS': 'badge-warning',
        'DONE': 'badge-success',
        'CANNOT_FIX': 'badge-danger'
    }
    return colors.get(status, 'badge-secondary')

def get_status_label(status):
    """Get Korean label for status"""
    labels = {
        'OPEN': '접수',
        'IN_PROGRESS': '조치 중',
        'DONE': '조치 완료',
        'CANNOT_FIX': '조치 불가'
    }
    return labels.get(status, status)

def has_duplicate_issue(db, location_id, title, within_hours=24):
    """Check for duplicate issues within specified hours"""
    cutoff_time = (datetime.now() - timedelta(hours=within_hours)).strftime('%Y-%m-%dT%H:%M:%S')
    
    duplicate = db.execute("""
        SELECT id FROM issues 
        WHERE location_id = ? AND title = ? 
        AND status IN ('OPEN', 'IN_PROGRESS')
        AND reported_at > ?
        ORDER BY reported_at DESC
        LIMIT 1
    """, (location_id, title, cutoff_time)).fetchone()
    
    return duplicate['id'] if duplicate else None

def create_status_history(db, issue_id, status, actor=None, memo=None):
    """Create status history entry"""
    db.execute("""
        INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
        VALUES (?, ?, ?, ?, ?)
    """, (issue_id, status, actor, memo, get_current_time()))

# Main routes
@bp.route('/report')
def list_reports():
    """이슈 목록 페이지"""
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    user_info = get_user_info(user_email)
    lang = get_language_from_request(request)
    return render_template('report/list.html', 
                         active='report', 
                         user=user_info,
                         lang=lang)

@bp.route('/report/place/<location_id>')
def place_page(location_id):
    """장소별 페이지"""
    # 장소별 Google Form URL 매핑
    google_form_urls = {
        'Ownership': 'https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Ownership',
        'Trust': 'https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Trust',
        'Focus-A': 'https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Focus-A',
        'Lounge': 'https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Lounge',
        'SnackBar': 'https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Lounge'
    }
    
    form_url = google_form_urls.get(location_id, '#')
    
    user_email = 'lwk9589@gmail.com'  # 이원규 - Service Architect
    user_info = get_user_info(user_email)
    
    return render_template('report/place.html', 
                         location_id=location_id,
                         form_url=form_url,
                         active='report', 
                         user=user_info)

# API Routes
@bp.route('/api/issues', methods=['GET'])
def get_issues():
    """이슈 목록 조회 API (전사 공개)"""
    db = get_db()
    
    # 필터 파라미터
    location_id = request.args.get('location_id')
    status = request.args.get('status')
    search = request.args.get('search')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    issue_type = request.args.get('type')
    
    # 기본 쿼리
    query = """
        SELECT i.*, 
               COUNT(c.id) as comment_count,
               COUNT(a.id) as attachment_count
        FROM issues i
        LEFT JOIN comments c ON i.id = c.issue_id
        LEFT JOIN attachments a ON i.id = a.issue_id
        WHERE 1=1
    """
    params = []
    
    # 필터 적용
    if location_id:
        query += " AND i.location_id = ?"
        params.append(location_id)
    
    if status:
        query += " AND i.status = ?"
        params.append(status)
        
    if issue_type:
        query += " AND i.type = ?"
        params.append(issue_type)
    
    if search:
        query += " AND (i.title LIKE ? OR i.description LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term])
    
    if from_date:
        query += " AND i.reported_at >= ?"
        params.append(from_date)
        
    if to_date:
        query += " AND i.reported_at <= ?"
        params.append(to_date)
    
    query += " GROUP BY i.id ORDER BY i.reported_at DESC"
    
    issues = db.execute(query, params).fetchall()
    
    result = []
    for issue in issues:
        issue_data = dict(issue)
        issue_data['status_label'] = get_status_label(issue['status'])
        issue_data['status_badge'] = get_status_badge(issue['status'])
        issue_data['reported_date'] = issue['reported_at'][:10] if issue['reported_at'] else ''
        result.append(issue_data)
    
    return jsonify(result)

@bp.route('/api/issues/<int:issue_id>', methods=['GET'])
def get_issue_detail(issue_id):
    """이슈 상세 조회 API"""
    db = get_db()
    
    # 이슈 기본 정보
    issue = db.execute("""
        SELECT * FROM issues WHERE id = ?
    """, (issue_id,)).fetchone()
    
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    
    # 첨부 파일
    attachments = db.execute("""
        SELECT * FROM attachments WHERE issue_id = ? ORDER BY created_at
    """, (issue_id,)).fetchall()
    
    # 코멘트
    comments = db.execute("""
        SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at
    """, (issue_id,)).fetchall()
    
    # 상태 이력
    status_history = db.execute("""
        SELECT * FROM status_history WHERE issue_id = ? ORDER BY changed_at
    """, (issue_id,)).fetchall()
    
    # 결과 조합
    result = dict(issue)
    result['status_label'] = get_status_label(issue['status'])
    result['status_badge'] = get_status_badge(issue['status'])
    result['attachments'] = [dict(a) for a in attachments]
    result['comments'] = [dict(c) for c in comments]
    result['status_history'] = [dict(h) for h in status_history]
    
    return jsonify(result)

@bp.route('/api/issues', methods=['POST'])
def create_issue():
    """이슈 등록 API (Apps Script 연동)"""
    # API 토큰 검증 (실제 환경에서는 환경변수에서 가져오기)
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON data required'}), 400
    
    # 필수 필드 검증
    required_fields = ['location_id', 'title', 'type']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    
    try:
        # 중복 검사
        duplicate_id = has_duplicate_issue(db, data['location_id'], data['title'])
        
        if duplicate_id:
            # 기존 이슈에 병합
            merge_description = f"[Auto-merge] 추가 접수: {data.get('description', '설명 없음')}"
            
            # 코멘트 추가
            db.execute("""
                INSERT INTO comments (issue_id, body, author, source, created_at)
                VALUES (?, ?, ?, 'auto_merge', ?)
            """, (duplicate_id, merge_description, 'System', get_current_time()))
            
            # 첨부 파일 추가
            if data.get('attachments'):
                for url in data['attachments']:
                    db.execute("""
                        INSERT INTO attachments (issue_id, url, created_at)
                        VALUES (?, ?, ?)
                    """, (duplicate_id, url, get_current_time()))
            
            db.commit()
            return jsonify({'merged_into': duplicate_id}), 200
        
        else:
            # 신규 이슈 생성
            reported_at = data.get('reported_at', get_current_time())
            
            cursor = db.execute("""
                INSERT INTO issues (location_id, title, type, description, reporter_email, reported_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['location_id'],
                data['title'],
                data['type'],
                data.get('description', ''),
                data.get('reporter_email', ''),
                reported_at,
                data.get('source', 'google_form')
            ))
            
            issue_id = cursor.lastrowid
            
            # 상태 이력 생성
            create_status_history(db, issue_id, 'OPEN', 'System', '이슈 접수')
            
            # 첨부 파일 추가
            if data.get('attachments'):
                for url in data['attachments']:
                    db.execute("""
                        INSERT INTO attachments (issue_id, url, created_at)
                        VALUES (?, ?, ?)
                    """, (issue_id, url, get_current_time()))
            
            db.commit()
            return jsonify({'id': issue_id}), 201
            
    except sqlite3.Error as e:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/issues/<int:issue_id>/status', methods=['PATCH'])
def update_issue_status(issue_id):
    """이슈 상태 변경 API (시설 관리자)"""
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
    
    new_status = data['status']
    actor = data.get('actor', '시설관리자')
    memo = data.get('memo', '')
    
    # 상태 검증
    valid_statuses = ['OPEN', 'IN_PROGRESS', 'DONE', 'CANNOT_FIX']
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    db = get_db()
    
    try:
        # 이슈 존재 확인
        issue = db.execute("SELECT id, status FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404
        
        # 상태 업데이트
        db.execute("""
            UPDATE issues SET status = ?, updated_at = ? WHERE id = ?
        """, (new_status, get_current_time(), issue_id))
        
        # 상태 이력 생성
        create_status_history(db, issue_id, new_status, actor, memo)
        
        db.commit()
        
        return jsonify({
            'id': issue_id,
            'status': new_status,
            'status_label': get_status_label(new_status),
            'actor': actor,
            'memo': memo
        })
        
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/issues/<int:issue_id>/comments', methods=['POST'])
def add_issue_comment(issue_id):
    """이슈 코멘트 추가 API (시설 관리자)"""
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify({'error': 'Comment body is required'}), 400
    
    body = data['body']
    author = data.get('author', '시설관리자')
    
    db = get_db()
    
    try:
        # 이슈 존재 확인
        issue = db.execute("SELECT id FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404
        
        # 코멘트 추가
        cursor = db.execute("""
            INSERT INTO comments (issue_id, body, author, source, created_at)
            VALUES (?, ?, ?, 'manual', ?)
        """, (issue_id, body, author, get_current_time()))
        
        comment_id = cursor.lastrowid
        
        # 이슈 업데이트 시간 갱신
        db.execute("""
            UPDATE issues SET updated_at = ? WHERE id = ?
        """, (get_current_time(), issue_id))
        
        db.commit()
        
        return jsonify({
            'id': comment_id,
            'issue_id': issue_id,
            'body': body,
            'author': author,
            'created_at': get_current_time()
        }), 201
        
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/issues/<int:issue_id>/merge', methods=['POST'])
def merge_issue(issue_id):
    """이슈 병합 API (시설 관리자)"""
    data = request.get_json()
    if not data or 'target_id' not in data:
        return jsonify({'error': 'Target issue ID is required'}), 400
    
    target_id = data['target_id']
    actor = data.get('actor', '시설관리자')
    
    if issue_id == target_id:
        return jsonify({'error': 'Cannot merge issue with itself'}), 400
    
    db = get_db()
    
    try:
        # 두 이슈 모두 존재하는지 확인
        issues = db.execute("""
            SELECT id, title, description FROM issues WHERE id IN (?, ?)
        """, (issue_id, target_id)).fetchall()
        
        if len(issues) != 2:
            return jsonify({'error': 'One or both issues not found'}), 404
        
        source_issue = next(i for i in issues if i['id'] == issue_id)
        target_issue = next(i for i in issues if i['id'] == target_id)
        
        # 소스 이슈의 첨부파일과 코멘트를 타겟으로 이동
        db.execute("""
            UPDATE attachments SET issue_id = ? WHERE issue_id = ?
        """, (target_id, issue_id))
        
        db.execute("""
            UPDATE comments SET issue_id = ? WHERE issue_id = ?
        """, (target_id, issue_id))
        
        db.execute("""
            UPDATE status_history SET issue_id = ? WHERE issue_id = ?
        """, (target_id, issue_id))
        
        # 병합 코멘트 추가
        merge_comment = f"[병합] '{source_issue['title']}' 이슈가 병합됨\n원본 설명: {source_issue['description'] or '없음'}"
        db.execute("""
            INSERT INTO comments (issue_id, body, author, source, created_at)
            VALUES (?, ?, ?, 'manual', ?)
        """, (target_id, merge_comment, actor, get_current_time()))
        
        # 소스 이슈 삭제
        db.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        
        # 타겟 이슈 업데이트 시간 갱신
        db.execute("""
            UPDATE issues SET updated_at = ? WHERE id = ?
        """, (get_current_time(), target_id))
        
        db.commit()
        
        return jsonify({
            'merged_from': issue_id,
            'merged_into': target_id,
            'message': f'Issue #{issue_id} merged into #{target_id}'
        })
        
    except sqlite3.Error:
        return jsonify({'error': 'Database error'}), 500

@bp.route('/api/places/<location_id>/active', methods=['GET'])
def get_active_issues_by_location(location_id):
    """장소별 진행 중 이슈 요약 API"""
    db = get_db()
    
    issues = db.execute("""
        SELECT id, title, type, status, reported_at
        FROM issues 
        WHERE location_id = ? AND status IN ('OPEN', 'IN_PROGRESS')
        ORDER BY reported_at DESC
    """, (location_id,)).fetchall()
    
    result = []
    for issue in issues:
        issue_data = dict(issue)
        issue_data['status_label'] = get_status_label(issue['status'])
        issue_data['status_badge'] = get_status_badge(issue['status'])
        result.append(issue_data)
    
    return jsonify({
        'location_id': location_id,
        'active_count': len(result),
        'issues': result
    })

# HRIS 동기화
@bp.route('/api/report/sync-hris', methods=['POST'])
def api_sync_hris():
    """HRIS 데이터 동기화 API"""
    emp_count = sync_hris_employees()
    
    return jsonify({
        'success': True,
        'message': f'HRIS 동기화 완료: 직원 {emp_count}명'
    })