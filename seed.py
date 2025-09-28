
import csv, os, sqlite3

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'inhouse.sqlite3')

def upsert(cur, table, cols, row, conflict='IGNORE'):
    keys = ','.join(cols)
    qs = ','.join(['?']*len(cols))
    sql = f"INSERT OR {conflict} INTO {table}({keys}) VALUES({qs})"
    cur.execute(sql, row)

def load_csv(cur, fname, table, cols):
    path = os.path.join(BASE, fname)
    if not os.path.exists(path): 
        print('skip', fname)
        return
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for d in r:
            row = [d[c] for c in cols]
            upsert(cur, table, cols, row)

def seed_nota_office_rooms(cur):
    """Seed Nota Office rooms according to blueprint specification"""
    # Meeting Rooms (10개) - Blueprint 시드 데이터
    meeting_rooms = [
        ('Disagree&Commit', 'MEETING', 10, '1F', 'room-disagree-commit'),
        ('Ownership', 'MEETING', 10, '1F', 'room-ownership'),
        ('Customer-Centric', 'MEETING', 10, '1F', 'room-customer-centric'),
        ('Trust', 'MEETING', 10, '1F', 'room-trust'),
        ('Leadership Principle', 'MEETING', 10, '1F', 'room-leadership'),
        ('회의실1', 'MEETING', 8, '1F', 'room-meeting-1'),
        ('회의실2', 'MEETING', 8, '1F', 'room-meeting-2'),
        ('회의실3', 'MEETING', 8, '1F', 'room-meeting-3'),
        ('회의실4', 'MEETING', 8, '1F', 'room-meeting-4'),
        ('회의실5', 'MEETING', 8, '1F', 'room-meeting-5'),
    ]
    
    # Focus Rooms (포커스룸)
    focus_rooms = [
        ('Focus-A', 'FOCUS', 1, '1F', 'focus-a'),
        ('Focus-B', 'FOCUS', 1, '1F', 'focus-b'),
        ('Focus-C', 'FOCUS', 1, '1F', 'focus-c'),
        ('Focus-D', 'FOCUS', 1, '1F', 'focus-d'),
        ('Focus-E', 'FOCUS', 1, '1F', 'focus-e'),
    ]
    
    # Insert meeting rooms
    for room_data in meeting_rooms:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO rooms (name, type, capacity, floor, svg_id) 
                VALUES (?, ?, ?, ?, ?)
            """, room_data)
        except Exception as e:
            print(f"Warning: Could not insert meeting room {room_data[0]}: {e}")
    
    # Insert focus rooms
    for room_data in focus_rooms:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO rooms (name, type, capacity, floor, svg_id) 
                VALUES (?, ?, ?, ?, ?)
            """, room_data)
        except Exception as e:
            print(f"Warning: Could not insert focus room {room_data[0]}: {e}")
    
    print(f"Seeded {len(meeting_rooms)} meeting rooms and {len(focus_rooms)} focus rooms")

def load_hris_data(cur):
    """Load HRIS data for Calendar Hub"""
    import json
    
    # Load HRIS employees
    emp_path = os.path.join(BASE, 'HRIS data', 'employees_basic.json')
    if os.path.exists(emp_path):
        with open(emp_path, 'r', encoding='utf-8') as f:
            employees = json.load(f)
        
        cur.execute("DELETE FROM hris_employees")  # Clear existing data
        
        for emp in employees:
            cur.execute("""
                INSERT INTO hris_employees 
                (employee_id, name, gender, dob, org_code, org_name, title, hire_date, email, location, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp['employee_id'], emp['name'], emp['gender'], emp['dob'],
                emp['org_code'], emp['org_name'], emp['title'], emp['hire_date'],
                emp['email'], emp['location'], emp['is_active']
            ))
        
        print(f"Loaded {len(employees)} HRIS employees")
    
    # Load HRIS vacations
    vac_path = os.path.join(BASE, 'HRIS data', 'vacations_2025-09.json')
    if os.path.exists(vac_path):
        with open(vac_path, 'r', encoding='utf-8') as f:
            vacations = json.load(f)
        
        cur.execute("DELETE FROM vacation_events")  # Clear existing data
        
        for vac in vacations:
            cur.execute("""
                INSERT INTO vacation_events 
                (employee_id, name, org_code, org_name, type, start_at, end_at, all_day, status, hris_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vac['employee_id'], vac['name'], vac['org_code'], vac['org_name'],
                vac['type'], vac['start_at'], vac['end_at'], vac['all_day'],
                vac['status'], vac['updated_at']
            ))
        
        print(f"Loaded {len(vacations)} vacation events")

def seed_sample_calendar_events(cur):
    """Create sample calendar events for testing"""
    from datetime import datetime, timedelta
    
    # Sample My events
    my_events = [
        {
            'title': '개인 미팅',
            'description': '클라이언트와의 개인 미팅',
            'start_at': '2025-09-22T10:00:00+09:00',
            'end_at': '2025-09-22T11:00:00+09:00',
            'all_day': False,
            'location': '회의실 A',
            'event_type': 'MY',
            'owner_email': 'user014@example.com'
        },
        {
            'title': '프로젝트 검토',
            'description': '주간 프로젝트 진행 상황 검토',
            'start_at': '2025-09-23T14:00:00+09:00',
            'end_at': '2025-09-23T15:30:00+09:00',
            'all_day': False,
            'location': '온라인',
            'event_type': 'MY',
            'owner_email': 'user014@example.com'
        }
    ]
    
    # Sample Official events
    official_events = [
        {
            'title': '전사 워크샵',
            'description': '2025년 3분기 전사 워크샵 및 팀 빌딩',
            'start_at': '2025-09-25T09:00:00+09:00',
            'end_at': '2025-09-25T18:00:00+09:00',
            'all_day': True,
            'location': '대강당',
            'event_type': 'OFFICIAL',
            'owner_email': 'hr@nota.ai'
        },
        {
            'title': 'NotaAI 제품 발표회',
            'description': '새로운 AI 제품 라인 공개 발표회',
            'start_at': '2025-09-26T15:00:00+09:00',
            'end_at': '2025-09-26T17:00:00+09:00',
            'all_day': False,
            'location': '컨퍼런스홀',
            'event_type': 'OFFICIAL',
            'owner_email': 'hr@nota.ai'
        }
    ]
    
    # Insert sample events
    cur.execute("DELETE FROM calendar_events WHERE owner_email = 'user014@example.com'")  # Clear existing demo data
    
    for event in my_events + official_events:
        cur.execute("""
            INSERT INTO calendar_events 
            (title, description, start_at, end_at, all_day, location, event_type, owner_email, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event['title'], event['description'], event['start_at'], event['end_at'],
            event['all_day'], event['location'], event['event_type'], 
            event['owner_email'], event['owner_email']
        ))
    
    print(f"Created {len(my_events)} My events and {len(official_events)} Official events")

def seed_user_settings(cur):
    """Create sample user settings"""
    cur.execute("""
        INSERT OR REPLACE INTO user_settings (user_email, setting_key, setting_value)
        VALUES ('user014@example.com', 'default_org', 'HR')
    """)
    print("Set default organization for demo user")

def seed_report_it_issues(cur):
    """Seed Report-It sample issues for testing"""
    from datetime import datetime, timedelta
    
    # Helper function to get ISO time string
    def get_time(days_ago=0, hours_ago=0):
        dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Sample issues data
    sample_issues = [
        # Ownership - 진행중인 이슈들
        {
            'location_id': 'Ownership',
            'title': '프로젝터',
            'type': '고장',
            'description': '전원 버튼을 눌러도 반응이 없습니다. LED 표시등도 켜지지 않는 상태입니다.',
            'status': 'OPEN',
            'reporter_email': 'user001@nota.ai',
            'reported_at': get_time(days_ago=2),
            'source': 'google_form'
        },
        {
            'location_id': 'Ownership',
            'title': '화이트보드 마커',
            'type': '성능저하',
            'description': '마커가 거의 다 말라서 글씨가 잘 안써집니다. 새 마커로 교체 필요합니다.',
            'status': 'IN_PROGRESS',
            'reporter_email': 'user002@nota.ai',
            'reported_at': get_time(days_ago=1),
            'source': 'google_form'
        },
        
        # Trust - 완료된 이슈
        {
            'location_id': 'Trust',
            'title': '에어컨',
            'type': '고장',
            'description': '냉방이 전혀 안됩니다. 리모컨으로도 작동하지 않습니다.',
            'status': 'DONE',
            'reporter_email': 'user003@nota.ai',
            'reported_at': get_time(days_ago=5),
            'source': 'google_form'
        },
        
        # Focus-A - 조치 불가 이슈
        {
            'location_id': 'Focus-A',
            'title': '의자',
            'type': '파손',
            'description': '의자 등받이가 완전히 부러졌습니다. 사용할 수 없는 상태입니다.',
            'status': 'CANNOT_FIX',
            'reporter_email': 'user004@nota.ai',
            'reported_at': get_time(days_ago=3),
            'source': 'manual'
        },
        
        # Lounge - 다양한 이슈들
        {
            'location_id': 'Lounge',
            'title': '커피머신',
            'type': '고장',
            'description': '물이 나오지 않습니다. 전원은 들어오는데 펌프에 문제가 있는 것 같습니다.',
            'status': 'OPEN',
            'reporter_email': 'user005@nota.ai',
            'reported_at': get_time(hours_ago=3),
            'source': 'google_form'
        },
        {
            'location_id': 'Lounge',
            'title': '소파',
            'type': '성능저하',
            'description': '쿠션이 많이 꺼져서 앉기 불편합니다.',
            'status': 'OPEN',
            'reporter_email': 'user006@nota.ai',
            'reported_at': get_time(hours_ago=5),
            'source': 'google_form'
        },
        
        # SnackBar - 최근 이슈들
        {
            'location_id': 'SnackBar',
            'title': '냉장고',
            'type': '고장',
            'description': '냉장고 문이 제대로 닫히지 않습니다. 고무패킹이 손상된 것 같습니다.',
            'status': 'IN_PROGRESS',
            'reporter_email': 'user007@nota.ai',
            'reported_at': get_time(hours_ago=8),
            'source': 'google_form'
        },
        {
            'location_id': 'SnackBar',
            'title': '전자레인지',
            'type': '기타',
            'description': '작동은 되는데 이상한 소음이 계속 납니다.',
            'status': 'OPEN',
            'reporter_email': 'user008@nota.ai',
            'reported_at': get_time(hours_ago=12),
            'source': 'google_form'
        }
    ]
    
    # Insert issues and create related records
    for issue_data in sample_issues:
        # Insert issue
        cur.execute("""
            INSERT INTO issues (location_id, title, type, description, status, reporter_email, reported_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            issue_data['location_id'],
            issue_data['title'],
            issue_data['type'],
            issue_data['description'],
            issue_data['status'],
            issue_data['reporter_email'],
            issue_data['reported_at'],
            issue_data['source']
        ))
        
        issue_id = cur.lastrowid
        
        # Create initial status history
        cur.execute("""
            INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
            VALUES (?, 'OPEN', 'System', '이슈 접수', ?)
        """, (issue_id, issue_data['reported_at']))
        
        # Add additional status changes for non-OPEN issues
        if issue_data['status'] == 'IN_PROGRESS':
            cur.execute("""
                INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
                VALUES (?, 'IN_PROGRESS', '시설관리자', '조치 시작', ?)
            """, (issue_id, get_time(hours_ago=2)))
            
            # Add manager comment for in-progress issues
            cur.execute("""
                INSERT INTO comments (issue_id, body, author, source, created_at)
                VALUES (?, '문제를 확인했으며 조치 중입니다. 곧 해결될 예정입니다.', '시설관리자', 'manual', ?)
            """, (issue_id, get_time(hours_ago=1)))
            
        elif issue_data['status'] == 'DONE':
            cur.execute("""
                INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
                VALUES (?, 'IN_PROGRESS', '시설관리자', '조치 시작', ?)
            """, (issue_id, get_time(days_ago=4)))
            
            cur.execute("""
                INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
                VALUES (?, 'DONE', '시설관리자', '수리 완료', ?)
            """, (issue_id, get_time(days_ago=2)))
            
            # Add completion comment
            cur.execute("""
                INSERT INTO comments (issue_id, body, author, source, created_at)
                VALUES (?, '에어컨 수리가 완료되었습니다. 정상 작동을 확인했습니다.', '시설관리자', 'manual', ?)
            """, (issue_id, get_time(days_ago=2)))
            
        elif issue_data['status'] == 'CANNOT_FIX':
            cur.execute("""
                INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
                VALUES (?, 'IN_PROGRESS', '시설관리자', '조치 검토', ?)
            """, (issue_id, get_time(days_ago=2)))
            
            cur.execute("""
                INSERT INTO status_history (issue_id, status, actor, memo, changed_at)
                VALUES (?, 'CANNOT_FIX', '시설관리자', '수리 불가 - 교체 필요', ?)
            """, (issue_id, get_time(days_ago=1)))
            
            # Add cannot fix comment
            cur.execute("""
                INSERT INTO comments (issue_id, body, author, source, created_at)
                VALUES (?, '의자 프레임이 완전히 손상되어 수리가 불가능합니다. 새 의자로 교체 예정입니다.', '시설관리자', 'manual', ?)
            """, (issue_id, get_time(days_ago=1)))
    
    # Add some sample attachments for Google Form issues
    sample_attachments = [
        (1, 'https://drive.google.com/file/d/1234567890/view'),  # 프로젝터 사진
        (5, 'https://drive.google.com/file/d/2345678901/view'),  # 커피머신 사진
        (7, 'https://drive.google.com/file/d/3456789012/view'),  # 냉장고 사진
    ]
    
    for issue_id, attachment_url in sample_attachments:
        try:
            cur.execute("""
                INSERT INTO attachments (issue_id, url, created_at)
                VALUES (?, ?, ?)
            """, (issue_id, attachment_url, get_time()))
        except:
            # Skip if issue_id doesn't exist
            pass
    
    print('Report-It sample issues seeded successfully!')

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    
    # Legacy CSV loading
    load_csv(cur, 'employees.csv', 'employees', ['name','email','team'])
    load_csv(cur, 'desks.csv', 'desks', ['label','floor'])
    # Note: Skip legacy rooms.csv as we're using the new rooms table structure
    load_csv(cur, 'assets.csv', 'assets', ['asset_code','name','type','location'])
    
    # Seed Nota Office rooms
    seed_nota_office_rooms(cur)
    
    # Load Calendar Hub HRIS data
    load_hris_data(cur)
    
    # Create sample calendar events
    seed_sample_calendar_events(cur)
    
    # Set user settings
    seed_user_settings(cur)
    
    # Seed Report-It sample issues
    seed_report_it_issues(cur)
    
    # seed some vacation/company events if CSVs exist (legacy)
    # vacations.csv -> events(kind='vac', title=name, start,end)
    vpath = os.path.join(BASE, 'vacations.csv')
    if os.path.exists(vpath):
        with open(vpath, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for d in r:
                cur.execute("INSERT INTO events(kind, owner_email, title, start, end) VALUES('vac', ?, ?, ?, ?)",
                            (d.get('email'), d.get('name'), d.get('start'), d.get('end')))
    cpath = os.path.join(BASE, 'company_events.csv')
    if os.path.exists(cpath):
        with open(cpath, newline='', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for d in r:
                cur.execute("INSERT INTO events(kind, owner_email, title, start, end, location, body, link) VALUES('company', ?, ?, ?, ?, ?, ?, ?)",
                            (d.get('created_by'), d.get('title'), d.get('start'), d.get('end'), d.get('location'), d.get('body'), d.get('link')))
    
    con.commit()
    con.close()
    print('Seed complete.')
    print('Calendar Hub is now ready with HRIS data and sample events!')

if __name__ == '__main__':
    main()
