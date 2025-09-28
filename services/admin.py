"""
관리자 모니터링 대시보드 서비스
5개 인하우스 서비스의 핵심 지표를 모니터링하는 API 및 페이지를 제공합니다.
"""

from flask import Blueprint, render_template, request, jsonify, g
from db import get_db
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import logging

bp = Blueprint('admin', __name__, url_prefix='/admin')

def log_event(user_id, service, action, target_id=None, meta=None):
    """
    모니터링 이벤트를 로깅합니다.
    
    Args:
        user_id: 사용자 ID (이메일 등)
        service: 서비스명 ('booker', 'calendar', 'reportit', 'faq', 'noonpick')
        action: 액션명 (스네이크 케이스)
        target_id: 대상 ID (선택사항)
        meta: 메타 데이터 (딕셔너리, JSON으로 저장됨)
    """
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
        logging.error(f"Failed to log event: {e}")

def get_bucket_type(from_dt, to_dt):
    """기간에 따라 버킷 타입을 결정합니다."""
    duration = to_dt - from_dt
    if duration <= timedelta(hours=72):
        return 'hour'
    return 'day'

def format_datetime_for_bucket(dt, bucket_type):
    """버킷 타입에 따라 datetime을 포맷팅합니다."""
    if bucket_type == 'hour':
        return dt.strftime('%Y-%m-%d %H:00:00')
    else:
        return dt.strftime('%Y-%m-%d')

def calculate_booker_metrics(db, from_dt, to_dt, bucket_type):
    """Booker 서비스 지표를 계산합니다."""
    metrics = {}
    series = defaultdict(list)
    
    # 기본 쿼리들
    attempt_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'booker' AND action = 'reservation_attempt' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    success_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'booker' AND action = 'reservation_success' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    failed_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'booker' AND action = 'reservation_failed' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    attempts = db.execute(attempt_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    successes = db.execute(success_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    failed = db.execute(failed_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    
    # 버킷별 집계
    attempt_buckets = defaultdict(int)
    success_buckets = defaultdict(int)
    overlap_buckets = defaultdict(int)
    
    for row in attempts:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        attempt_buckets[bucket] += 1
    
    for row in successes:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        success_buckets[bucket] += 1
    
    for row in failed:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        try:
            meta = json.loads(row['meta']) if row['meta'] else {}
            if meta.get('reason') == 'overlap':
                overlap_buckets[bucket] += 1
        except:
            pass
    
    # 전체 지표 계산
    total_attempts = sum(attempt_buckets.values())
    total_success = sum(success_buckets.values())
    total_overlap = sum(overlap_buckets.values())
    
    metrics['success_rate'] = {"value": total_success / total_attempts if total_attempts > 0 else 0}
    metrics['overlap_rate'] = {"value": total_overlap / total_attempts if total_attempts > 0 else 0}
    metrics['occupancy'] = {"value": 0.0}  # 실제 점유율 계산은 별도 구현 필요
    
    # 시계열 데이터
    all_buckets = set(attempt_buckets.keys()) | set(success_buckets.keys())
    for bucket in sorted(all_buckets):
        attempts_count = attempt_buckets[bucket]
        success_count = success_buckets[bucket]
        overlap_count = overlap_buckets[bucket]
        
        success_rate = success_count / attempts_count if attempts_count > 0 else 0
        overlap_rate = overlap_count / attempts_count if attempts_count > 0 else 0
        
        series['success_rate'].append([bucket, round(success_rate, 3)])
        series['overlap_rate'].append([bucket, round(overlap_rate, 3)])
        series['occupancy'].append([bucket, 0.0])  # 실제 점유율 계산 필요
    
    return metrics, dict(series)

def calculate_calendar_metrics(db, from_dt, to_dt, bucket_type):
    """Calendar 서비스 지표를 계산합니다."""
    metrics = {}
    series = defaultdict(list)
    
    # DAU 계산 (user 이벤트만)
    dau_query = """
        SELECT ts, user_id, meta FROM monitoring_events 
        WHERE service = 'calendar' 
        AND action IN ('view_calendar', 'register_vacation', 'event_created')
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    events = db.execute(dau_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    
    # 버킷별 DAU 및 탭 분포 계산
    dau_buckets = defaultdict(set)
    tab_buckets = defaultdict(lambda: defaultdict(int))
    
    for row in events:
        try:
            meta = json.loads(row['meta']) if row['meta'] else {}
            if meta.get('source') != 'user':
                continue
                
            dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
            bucket = format_datetime_for_bucket(dt, bucket_type)
            dau_buckets[bucket].add(row['user_id'])
            
            if 'tab' in meta:
                tab_buckets[bucket][meta['tab']] += 1
        except:
            pass
    
    # 전체 DAU
    all_users = set()
    for users in dau_buckets.values():
        all_users.update(users)
    
    metrics['dau'] = {"value": len(all_users)}
    
    # 시계열 데이터
    for bucket in sorted(dau_buckets.keys()):
        series['dau'].append([bucket, len(dau_buckets[bucket])])
    
    return metrics, dict(series)

def calculate_reportit_metrics(db, from_dt, to_dt, bucket_type):
    """Report-It 서비스 지표를 계산합니다."""
    metrics = {}
    series = defaultdict(list)
    
    # 이슈 생성/해결 이벤트 조회
    created_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'reportit' AND action = 'issue_created' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    resolved_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'reportit' AND action = 'issue_resolved' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    created_events = db.execute(created_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    resolved_events = db.execute(resolved_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    
    # 버킷별 집계
    created_buckets = defaultdict(int)
    resolved_buckets = defaultdict(int)
    ttr_buckets = defaultdict(list)
    
    for row in created_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        created_buckets[bucket] += 1
    
    for row in resolved_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        resolved_buckets[bucket] += 1
        
        try:
            meta = json.loads(row['meta']) if row['meta'] else {}
            if 'ttr_minutes' in meta:
                ttr_buckets[bucket].append(meta['ttr_minutes'])
        except:
            pass
    
    # 전체 지표
    total_created = sum(created_buckets.values())
    total_resolved = sum(resolved_buckets.values())
    all_ttr = []
    for ttr_list in ttr_buckets.values():
        all_ttr.extend(ttr_list)
    
    metrics['created'] = {"value": total_created}
    metrics['resolved'] = {"value": total_resolved}
    metrics['resolve_rate'] = {"value": total_resolved / total_created if total_created > 0 else 0}
    metrics['ttr_avg'] = {"value": sum(all_ttr) / len(all_ttr) if all_ttr else 0}
    
    # 시계열 데이터
    all_buckets = set(created_buckets.keys()) | set(resolved_buckets.keys())
    for bucket in sorted(all_buckets):
        series['created'].append([bucket, created_buckets[bucket]])
        series['resolved'].append([bucket, resolved_buckets[bucket]])
        
        created_count = created_buckets[bucket]
        resolved_count = resolved_buckets[bucket]
        resolve_rate = resolved_count / created_count if created_count > 0 else 0
        series['resolve_rate'].append([bucket, round(resolve_rate, 3)])
        
        bucket_ttr = ttr_buckets[bucket]
        avg_ttr = sum(bucket_ttr) / len(bucket_ttr) if bucket_ttr else 0
        series['ttr_avg'].append([bucket, round(avg_ttr, 1)])
    
    return metrics, dict(series)

def calculate_faq_metrics(db, from_dt, to_dt, bucket_type):
    """FAQ/Guidebook 서비스 지표를 계산합니다."""
    metrics = {}
    series = defaultdict(list)
    tables = {}
    
    # 검색 이벤트 조회
    search_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'faq' AND action = 'faq_search' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    zero_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'faq' AND action = 'faq_zero_result' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    view_query = """
        SELECT ts, target_id FROM monitoring_events 
        WHERE service = 'faq' AND action = 'faq_view' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    search_events = db.execute(search_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    zero_events = db.execute(zero_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    view_events = db.execute(view_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    
    # 버킷별 집계
    search_buckets = defaultdict(int)
    zero_buckets = defaultdict(int)
    zero_queries = defaultdict(int)
    doc_views = defaultdict(int)
    
    for row in search_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        search_buckets[bucket] += 1
    
    for row in zero_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        zero_buckets[bucket] += 1
        
        try:
            meta = json.loads(row['meta']) if row['meta'] else {}
            if 'q' in meta:
                zero_queries[meta['q']] += 1
        except:
            pass
    
    for row in view_events:
        if row['target_id']:
            doc_views[row['target_id']] += 1
    
    # 전체 지표
    total_searches = sum(search_buckets.values())
    total_zeros = sum(zero_buckets.values())
    
    metrics['zero_rate'] = {"value": total_zeros / total_searches if total_searches > 0 else 0}
    
    # 시계열 데이터
    all_buckets = set(search_buckets.keys()) | set(zero_buckets.keys())
    for bucket in sorted(all_buckets):
        search_count = search_buckets[bucket]
        zero_count = zero_buckets[bucket]
        zero_rate = zero_count / search_count if search_count > 0 else 0
        series['zero_rate'].append([bucket, round(zero_rate, 3)])
    
    # 표 데이터
    top_docs = sorted(doc_views.items(), key=lambda x: x[1], reverse=True)[:10]
    top_zero_queries = sorted(zero_queries.items(), key=lambda x: x[1], reverse=True)[:10]
    
    tables['top_docs'] = top_docs
    tables['zero_queries'] = top_zero_queries
    
    return metrics, dict(series), tables

def calculate_noonpick_metrics(db, from_dt, to_dt, bucket_type):
    """NoonPick 서비스 지표를 계산합니다."""
    metrics = {}
    series = defaultdict(list)
    tables = {}
    
    # 추천/선택 이벤트 조회
    recommended_query = """
        SELECT ts, meta FROM monitoring_events 
        WHERE service = 'noonpick' AND action = 'menu_recommended' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    selected_query = """
        SELECT ts, meta, target_id FROM monitoring_events 
        WHERE service = 'noonpick' AND action = 'menu_selected' 
        AND ts BETWEEN ? AND ?
        ORDER BY ts
    """
    
    recommended_events = db.execute(recommended_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    selected_events = db.execute(selected_query, (from_dt.strftime('%Y-%m-%d %H:%M:%S'), to_dt.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
    
    # 버킷별 집계
    recommended_buckets = defaultdict(int)
    selected_buckets = defaultdict(int)
    menu_selections = defaultdict(int)
    
    for row in recommended_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        recommended_buckets[bucket] += 1
    
    for row in selected_events:
        dt = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        bucket = format_datetime_for_bucket(dt, bucket_type)
        selected_buckets[bucket] += 1
        
        if row['target_id']:
            menu_selections[row['target_id']] += 1
    
    # 전체 지표
    total_recommended = sum(recommended_buckets.values())
    total_selected = sum(selected_buckets.values())
    
    metrics['select_rate'] = {"value": total_selected / total_recommended if total_recommended > 0 else 0}
    
    # 7일 중복률 계산 (최근 7일)
    recent_7days = datetime.now() - timedelta(days=7)
    recent_selected_query = """
        SELECT target_id FROM monitoring_events 
        WHERE service = 'noonpick' AND action = 'menu_selected' 
        AND ts >= ?
    """
    recent_selections = db.execute(recent_selected_query, (recent_7days.strftime('%Y-%m-%d %H:%M:%S'),)).fetchall()
    
    recent_menu_count = len(recent_selections)
    unique_menu_count = len(set(row['target_id'] for row in recent_selections if row['target_id']))
    
    metrics['dup7'] = {"value": 1 - (unique_menu_count / recent_menu_count) if recent_menu_count > 0 else 0}
    
    # 시계열 데이터
    all_buckets = set(recommended_buckets.keys()) | set(selected_buckets.keys())
    for bucket in sorted(all_buckets):
        recommended_count = recommended_buckets[bucket]
        selected_count = selected_buckets[bucket]
        select_rate = selected_count / recommended_count if recommended_count > 0 else 0
        series['select_rate'].append([bucket, round(select_rate, 3)])
    
    # 표 데이터
    top_menus = sorted(menu_selections.items(), key=lambda x: x[1], reverse=True)[:10]
    tables['top_menus'] = top_menus
    
    return metrics, dict(series), tables

@bp.route('/')
def dashboard():
    """관리자 모니터링 대시보드 메인 페이지"""
    return render_template('admin/dashboard.html', 
                         title='Admin Monitoring Dashboard', 
                         active='admin',
                         user={'email': 'lwk9589@gmail.com', 'name': '이원규', 'org_name': 'Service Architect', 'title': 'Developer', 'is_admin': True})

@bp.route('/api/metrics')
def api_metrics():
    """
    관리자 모니터링 API 엔드포인트
    
    Query Parameters:
    - service: booker|calendar|reportit|faq|noonpick
    - from: YYYY-MM-DD 또는 YYYY-MM-DD HH:MM:SS (KST)
    - to: YYYY-MM-DD 또는 YYYY-MM-DD HH:MM:SS (KST)
    - bucket: hour|day (자동 판정 가능)
    - include: 쉼표분리 지표 키
    - limit: 표 데이터 개수 제한
    """
    service = request.args.get('service', 'booker')
    from_str = request.args.get('from')
    to_str = request.args.get('to')
    bucket = request.args.get('bucket')
    include = request.args.get('include', '').split(',') if request.args.get('include') else []
    limit = int(request.args.get('limit', 10))
    
    # 기본값: 최근 7일
    if not from_str or not to_str:
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=7)
    else:
        try:
            # 날짜 형식 파싱 (다양한 형식 지원)
            if len(from_str) == 10:  # YYYY-MM-DD
                from_dt = datetime.strptime(from_str, '%Y-%m-%d')
            elif len(from_str) == 16:  # YYYY-MM-DD HH:MM
                from_dt = datetime.strptime(from_str, '%Y-%m-%d %H:%M')
            else:  # YYYY-MM-DD HH:MM:SS
                from_dt = datetime.strptime(from_str, '%Y-%m-%d %H:%M:%S')
                
            if len(to_str) == 10:  # YYYY-MM-DD
                to_dt = datetime.strptime(to_str, '%Y-%m-%d')
            elif len(to_str) == 16:  # YYYY-MM-DD HH:MM
                to_dt = datetime.strptime(to_str, '%Y-%m-%d %H:%M')
            else:  # YYYY-MM-DD HH:MM:SS
                to_dt = datetime.strptime(to_str, '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            return jsonify({"error": f"Invalid date format: {str(e)}"}), 400
    
    # 버킷 타입 결정
    if not bucket:
        bucket = get_bucket_type(from_dt, to_dt)
    
    # 조회 범위 제한 (최대 180일)
    if (to_dt - from_dt).days > 180:
        return jsonify({"error": "Date range too large (max 180 days)"}), 400
    
    try:
        db = get_db()
        
        # 서비스별 지표 계산
        if service == 'booker':
            metrics, series = calculate_booker_metrics(db, from_dt, to_dt, bucket)
            tables = {}
        elif service == 'calendar':
            metrics, series = calculate_calendar_metrics(db, from_dt, to_dt, bucket)
            tables = {}
        elif service == 'reportit':
            metrics, series = calculate_reportit_metrics(db, from_dt, to_dt, bucket)
            tables = {}
        elif service == 'faq':
            metrics, series, tables = calculate_faq_metrics(db, from_dt, to_dt, bucket)
        elif service == 'noonpick':
            metrics, series, tables = calculate_noonpick_metrics(db, from_dt, to_dt, bucket)
        else:
            return jsonify({"error": "Invalid service"}), 400
        
        # include 필터 적용
        if include and include[0]:  # include가 비어있지 않은 경우
            filtered_metrics = {k: v for k, v in metrics.items() if k in include}
            filtered_series = {k: v for k, v in series.items() if k in include}
        else:
            filtered_metrics = metrics
            filtered_series = series
        
        # 표 데이터에 limit 적용
        limited_tables = {}
        for table_name, table_data in tables.items():
            if isinstance(table_data, list):
                limited_tables[table_name] = table_data[:limit]
            else:
                limited_tables[table_name] = table_data
        
        response = {
            "service": service,
            "range": {
                "from": from_dt.strftime('%Y-%m-%d %H:%M:%S'),
                "to": to_dt.strftime('%Y-%m-%d %H:%M:%S'),
                "bucket": bucket
            },
            "kpis": filtered_metrics,
            "series": filtered_series,
            "tables": limited_tables,
            "last_updated_kst": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Error calculating metrics: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
