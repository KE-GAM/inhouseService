
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
