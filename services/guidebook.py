import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, redirect, url_for, jsonify
from db import get_db
from i18n import get_language_from_request

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

bp = Blueprint('guidebook', __name__)

# 정적 데이터 로드 함수들
def load_json_data(filename):
    """JSON 데이터 파일을 로드하고 추가 필드 계산"""
    try:
        with open(f'static/guidebook/data/{filename}', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 각 문서에 대해 추가 필드 계산
        for item in data:
            if 'last_reviewed' in item:
                # 마지막 검토일이 90일이 지났는지 확인
                try:
                    last_reviewed = datetime.strptime(item['last_reviewed'], '%Y-%m-%d')
                    days_since_review = (datetime.now() - last_reviewed).days
                    item['is_outdated'] = days_since_review > 90
                    item['days_since_review'] = days_since_review
                except ValueError:
                    item['is_outdated'] = False
                    item['days_since_review'] = 0
            else:
                item['is_outdated'] = False
                item['days_since_review'] = 0
        
        return data
    except FileNotFoundError:
        return []

def get_departments():
    """employees_basic.json에서 부서 정보 추출"""
    try:
        with open('HRIS data/employees_basic.json', 'r', encoding='utf-8') as f:
            employees = json.load(f)
        
        departments = {}
        for emp in employees:
            org_code = emp['org_code']
            org_name = emp['org_name']
            if org_code not in departments:
                departments[org_code] = {
                    'code': org_code,
                    'name': org_name,
                    'employees': []
                }
            departments[org_code]['employees'].append(emp)
        
        return list(departments.values())
    except FileNotFoundError:
        return []

# 라우트 정의
@bp.route('/guidebook')
def guidebook_home():
    """Guidebook 허브 페이지"""
    lang = get_language_from_request(request)
    
    # 5개 섹션의 통계 데이터
    sections = [
        {
            'id': 'policies',
            'name': 'Policies (내규)',
            'description': '회사 규정과 정책의 단일 출처',
            'icon': '📋',
            'count': len(load_json_data('policies.json')),
            'color': '#2759FF'
        },
        {
            'id': 'faqs',
            'name': 'Department FAQs',
            'description': '부서별 자주 묻는 질문',
            'icon': '❓',
            'count': len(load_json_data('faqs.json')),
            'color': '#2759FF'
        },
        {
            'id': 'glossary',
            'name': 'Glossary (용어집)',
            'description': '회사 전문 용어 사전',
            'icon': '📚',
            'count': len(load_json_data('glossary.json')),
            'color': '#2759FF'
        },
        {
            'id': 'procedures',
            'name': 'Procedures & Forms',
            'description': '업무 절차와 양식 안내',
            'icon': '📋',
            'count': len(load_json_data('procedures.json')),
            'color': '#2759FF'
        },
        {
            'id': 'services',
            'name': 'Service Catalog',
            'description': '부서별 서비스 및 연락처',
            'icon': '🏢',
            'count': len(load_json_data('services.json')),
            'color': '#2759FF'
        }
    ]
    
    return render_template('guidebook/index.html', 
                         sections=sections,
                         title='Nota Guidebook',
                         active='guidebook',
                         user={'email': 'lwk9589@gmail.com', 'name': '이원규', 'org_name': 'Service Architect', 'title': 'Developer', 'is_admin': True},
                         lang=lang)

@bp.route('/guidebook/<section>')
def guidebook_section(section):
    """섹션별 페이지"""
    valid_sections = ['policies', 'faqs', 'glossary', 'procedures', 'services']
    if section not in valid_sections:
        return redirect(url_for('guidebook.guidebook_home'))
    
    # 섹션별 데이터 로드
    data = load_json_data(f'{section}.json')
    departments = get_departments()
    
    # 검색 및 필터 처리
    search_query = request.args.get('q', '').strip()
    dept_filter = request.args.get('dept', '')
    
    filtered_data = data
    
    # 부서 필터 적용
    if dept_filter:
        filtered_data = [item for item in filtered_data 
                        if item.get('department') == dept_filter or 
                           item.get('owner_dept') == dept_filter]
    
    # 검색 필터 적용
    if search_query:
        search_lower = search_query.lower()
        filtered_data = [item for item in filtered_data 
                        if search_lower in item.get('title', '').lower() or
                           search_lower in item.get('content', '').lower() or
                           search_lower in item.get('description', '').lower() or
                           search_lower in item.get('summary', '').lower()]
    
    section_info = {
        'policies': {'name': 'Policies (내규)', 'description': '회사 규정과 정책'},
        'faqs': {'name': 'Department FAQs', 'description': '부서별 자주 묻는 질문'},
        'glossary': {'name': 'Glossary (용어집)', 'description': '회사 전문 용어'},
        'procedures': {'name': 'Procedures & Forms', 'description': '업무 절차와 양식'},
        'services': {'name': 'Service Catalog', 'description': '부서별 서비스 및 연락처'}
    }
    
    return render_template(f'guidebook/section_{section}.html',
                         section=section,
                         section_info=section_info[section],
                         data=filtered_data,
                         departments=departments,
                         search_query=search_query,
                         dept_filter=dept_filter,
                         title=f'Guidebook - {section_info[section]["name"]}',
                         active='guidebook',
                         user={'email': 'lwk9589@gmail.com', 'name': '이원규', 'org_name': 'Service Architect', 'title': 'Developer', 'is_admin': True})

@bp.route('/guidebook/<section>/<slug>')
def guidebook_detail(section, slug):
    """문서 상세 페이지"""
    valid_sections = ['policies', 'faqs', 'glossary', 'procedures', 'services']
    if section not in valid_sections:
        return redirect(url_for('guidebook.guidebook_home'))
    
    data = load_json_data(f'{section}.json')
    item = next((item for item in data if item.get('slug') == slug), None)
    
    if not item:
        return redirect(url_for('guidebook.guidebook_section', section=section))
    
    # 관련 문서 찾기 (태그 기반)
    related_items = []
    if 'tags' in item:
        all_sections_data = []
        for sec in valid_sections:
            sec_data = load_json_data(f'{sec}.json')
            for sec_item in sec_data:
                sec_item['section'] = sec
            all_sections_data.extend(sec_data)
        
        # 공통 태그가 있는 문서들 찾기
        item_tags = set(item['tags'])
        for other_item in all_sections_data:
            if other_item.get('slug') != slug and 'tags' in other_item:
                common_tags = item_tags.intersection(set(other_item['tags']))
                if common_tags:
                    other_item['common_tags'] = list(common_tags)
                    related_items.append(other_item)
        
        # 공통 태그 수로 정렬
        related_items.sort(key=lambda x: len(x.get('common_tags', [])), reverse=True)
        related_items = related_items[:5]  # 상위 5개만
    
    return render_template('guidebook/detail.html',
                         section=section,
                         item=item,
                         related_items=related_items,
                         title=f'Guidebook - {item.get("title", "")}',
                         active='guidebook',
                         user={'email': 'lwk9589@gmail.com', 'name': '이원규', 'org_name': 'Service Architect', 'title': 'Developer', 'is_admin': True})

@bp.route('/guidebook/api/search')
def api_search():
    """전체 검색 API (AJAX용)"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    user_email = 'lwk9589@gmail.com'  # 현재 사용자
    
    results = []
    sections = ['policies', 'faqs', 'glossary', 'procedures', 'services']
    
    for section in sections:
        data = load_json_data(f'{section}.json')
        search_lower = query.lower()
        
        for item in data:
            if (search_lower in item.get('title', '').lower() or
                search_lower in item.get('content', '').lower() or
                search_lower in item.get('description', '').lower() or
                search_lower in item.get('summary', '').lower()):
                
                results.append({
                    'section': section,
                    'title': item.get('title', ''),
                    'summary': item.get('summary', item.get('description', ''))[:100] + '...',
                    'slug': item.get('slug', ''),
                    'department': item.get('department', item.get('owner_dept', ''))
                })
    
    # 검색 결과 로깅
    results_count = len(results)
    limited_results = results[:20]  # 상위 20개 결과만 반환
    
    # 검색 로그
    log_event(user_email, 'faq', 'faq_search', f"search-{query}", {
        'q': query,
        'resultsCount': results_count,
        'source': 'user'
    })
    
    # 0건 검색 결과 로그
    if results_count == 0:
        log_event(user_email, 'faq', 'faq_zero_result', f"zero-{query}", {
            'q': query,
            'source': 'user'
        })
    
    return jsonify(limited_results)
