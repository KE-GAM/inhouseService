import os
import json
import hashlib
import requests
import random
import math
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, jsonify
from db import get_db
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from i18n import get_language_from_request
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def validate_api_keys():
    """API 키가 모두 설정되었는지 검증"""
    required_keys = [
        'KAKAO_REST_API_KEY',
        'KAKAO_JAVASCRIPT_KEY', 
        'GOOGLE_PLACES_API_KEY'
    ]
    
    missing_keys = []
    for key in required_keys:
        if not os.environ.get(key):
            missing_keys.append(key)
    
    if missing_keys:
        print(f"경고: 다음 API 키가 설정되지 않았습니다: {', '.join(missing_keys)}")
        print("env.example 파일을 참고하여 .env 파일을 생성하세요.")
        return False
    
    return True

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

bp = Blueprint('noonpick', __name__)

# 카테고리 매핑 (카카오 category_name → 우리 분류)
CATEGORY_MAP = [
    ("KOREAN",   ["한식","국밥","찌개","백반","분식","비빔밥","국수","냉면"]),
    ("JAPANESE", ["일식","스시","초밥","라멘","우동","돈카츠","소바","덮밥"]),
    ("CHINESE",  ["중식","짜장","짬뽕","탕수육","마라"]),
    ("WESTERN",  ["양식","파스타","피자","버거","스테이크","브런치"]),
    ("MEAT",     ["고기","구이","삼겹","갈비","정육","솥뚜껑"]),
    ("NOODLE",   ["국수","라면","라멘","우동","소바","짜장","짬뽕"]),
    ("RICE",     ["덮밥","비빔밥","백반","카레","김밥","국밥"]),
    ("SOUP",     ["국","탕","찌개","전골"]),
    ("CAFE",     ["카페","디저트","빵","베이커리"])
]

# 환경 변수에서 API 키 로드 (기본값 없음 - 보안상 안전)
KAKAO_REST_API_KEY = os.environ.get('KAKAO_REST_API_KEY')
KAKAO_JAVASCRIPT_KEY = os.environ.get('KAKAO_JAVASCRIPT_KEY')
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY')

def map_category_to_big_categories(category_name):
    """카카오 카테고리를 대분류로 매핑"""
    big_cats = []
    for big_cat, keywords in CATEGORY_MAP:
        for keyword in keywords:
            if keyword in category_name:
                big_cats.append(big_cat)
    return list(set(big_cats))  # 중복 제거

def geocode_address(address):
    """카카오 지오코딩 API로 주소를 좌표로 변환"""
    if not KAKAO_REST_API_KEY:
        print("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        return None, None
        
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": address}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if data.get('documents'):
            doc = data['documents'][0]
            return float(doc['y']), float(doc['x'])  # lat, lng
    except Exception as e:
        print(f"Geocoding error: {e}")
    
    return None, None

def search_places_by_category(lat, lng, radius, category="음식점", page=1):
    """카카오 Local API로 장소 검색"""
    if not KAKAO_REST_API_KEY:
        print("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        return None
        
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "category_group_code": "FD6",  # 음식점
        "x": lng,
        "y": lat,
        "radius": radius,
        "page": page,
        "size": 15,
        "sort": "distance"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json()
    except Exception as e:
        print(f"Kakao API error: {e}")
        return None

def get_place_photos(place_id):
    """카카오 Place API로 장소 사진 정보 조회"""
    if not KAKAO_REST_API_KEY:
        print("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        return None
        
    url = f"https://dapi.kakao.com/v2/local/place/{place_id}.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get('documents'):
            place_info = data['documents'][0]
            
            # 사진 정보가 있으면 첫 번째 사진 URL 반환
            if 'photo' in place_info and place_info['photo'].get('photoList'):
                photo_list = place_info['photo']['photoList']
                if photo_list and len(photo_list) > 0:
                    # 가장 큰 크기의 사진 선택
                    best_photo = max(photo_list, key=lambda x: int(x.get('width', 0)) * int(x.get('height', 0)))
                    return best_photo.get('originurl')
    except Exception as e:
        print(f"Place photos API error: {e}")
    
    return None

def search_google_place(place_name, lat, lng):
    """Google Places API로 장소 검색"""
    if not GOOGLE_PLACES_API_KEY:
        print("GOOGLE_PLACES_API_KEY가 설정되지 않았습니다.")
        return None
        
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        'location': f"{lat},{lng}",
        'radius': 100,  # 100m 반경
        'keyword': place_name,
        'type': 'restaurant',
        'key': GOOGLE_PLACES_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get('status') == 'OK' and data.get('results'):
            # 가장 유사한 장소 선택 (거리 기반)
            best_place = min(data['results'], 
                           key=lambda x: abs(float(x['geometry']['location']['lat']) - lat) + 
                                       abs(float(x['geometry']['location']['lng']) - lng))
            return best_place.get('place_id')
    except Exception as e:
        print(f"Google Places search error: {e}")
    
    return None

def get_google_place_photos(place_id):
    """Google Places API로 장소 사진 정보 조회"""
    if not GOOGLE_PLACES_API_KEY:
        print("GOOGLE_PLACES_API_KEY가 설정되지 않았습니다.")
        return None
        
    url = f"https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        'place_id': place_id,
        'fields': 'photos',
        'key': GOOGLE_PLACES_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get('status') == 'OK' and data.get('result', {}).get('photos'):
            photos = data['result']['photos']
            if photos:
                # 가장 큰 크기의 사진 선택
                best_photo = max(photos, key=lambda x: x.get('width', 0) * x.get('height', 0))
                photo_reference = best_photo.get('photo_reference')
                
                # 실제 이미지 URL 생성
                return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={GOOGLE_PLACES_API_KEY}"
    except Exception as e:
        print(f"Google Places photos API error: {e}")
    
    return None

def search_food_image(place_name, categories=None):
    """음식점 카테고리별 이미지 생성"""
    try:
        # 카테고리별 고정 이미지 사용
        category_images = {
            'KOREAN': 'https://images.unsplash.com/photo-1551218808-94e220e084d2?w=300&h=200&fit=crop',
            'JAPANESE': 'https://images.unsplash.com/photo-1579952363873-27d3bfad9c0d?w=300&h=200&fit=crop',
            'CHINESE': 'https://images.unsplash.com/photo-1563379091339-03246963d4d4?w=300&h=200&fit=crop',
            'WESTERN': 'https://images.unsplash.com/photo-1551782450-17144efb9c50?w=300&h=200&fit=crop',
            'MEAT': 'https://images.unsplash.com/photo-1529692236671-f1f6cf9683ba?w=300&h=200&fit=crop',
            'SOUP': 'https://images.unsplash.com/photo-1547592180-85f173990554?w=300&h=200&fit=crop',
            'NOODLE': 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=300&h=200&fit=crop',
            'RICE': 'https://images.unsplash.com/photo-1512058564366-18510be2db19?w=300&h=200&fit=crop',
            'CAFE': 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=300&h=200&fit=crop'
        }
        
        if categories:
            # 카테고리별 이미지 선택
            for cat in categories:
                if cat in category_images:
                    return category_images[cat]
        
        # 기본 음식 이미지
        return 'https://images.unsplash.com/photo-1551218808-94e220e084d2?w=300&h=200&fit=crop'
    except:
        return None

def search_places_by_keyword(lat, lng, radius, keyword, page=1):
    """카카오 Local API로 키워드 검색"""
    if not KAKAO_REST_API_KEY:
        print("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        return None
        
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "query": keyword,
        "x": lng,
        "y": lat,
        "radius": radius,
        "page": page,
        "size": 15,
        "sort": "distance"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json()
    except Exception as e:
        print(f"Kakao API error: {e}")
        return None

def fetch_og_meta(url):
    """Open Graph 메타 데이터 파싱"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.find('meta', property='og:title')
        description = soup.find('meta', property='og:description')
        image = soup.find('meta', property='og:image')
        
        return {
            'title': title['content'] if title else '',
            'description': description['content'] if description else '',
            'image': image['content'] if image else ''
        }
    except Exception as e:
        print(f"OG meta parsing error: {e}")
        return {'title': '', 'description': '', 'image': ''}

def get_or_create_og_cache(url):
    """OG 메타 캐시 조회 또는 생성"""
    db = get_db()
    
    # 캐시 조회 (7일 이내)
    cached = db.execute("""
        SELECT title, description, image FROM og_cache 
        WHERE url = ? AND cached_at > datetime('now', '-7 days')
    """, (url,)).fetchone()
    
    if cached:
        return dict(cached)
    
    # 새로 파싱
    og_meta = fetch_og_meta(url)
    
    # 캐시 저장
    db.execute("""
        INSERT OR REPLACE INTO og_cache (url, title, description, image, cached_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (url, og_meta['title'], og_meta['description'], og_meta['image']))
    db.commit()
    
    return og_meta

def distance_score(d_m, r_m):
    """거리 점수 계산 (0.4 ~ 1.0)"""
    if d_m >= r_m:
        return 0.4
    return 0.4 + 0.6 * (1.0 - d_m / max(1, r_m))

def category_match(place_cats, selected_cats):
    """카테고리 매칭 점수"""
    if not selected_cats:
        return 0.5  # 미선택이면 중립
    place_set = set(place_cats) if place_cats else set()
    selected_set = set(selected_cats)
    return 1.0 if place_set & selected_set else 0.0

def calculate_score(place, radius, selected_categories):
    """장소 점수 계산"""
    big_cats = json.loads(place['big_categories']) if place['big_categories'] else []
    
    cat_score = category_match(big_cats, selected_categories)
    dist_score = distance_score(place['distance_m'], radius)
    
    return 0.6 * cat_score + 0.4 * dist_score

def weighted_random_sample(places_with_scores, count=3, temperature=0.08):
    """가중 랜덤 샘플링"""
    if not places_with_scores:
        return []
    
    # 소프트맥스로 확률 계산
    scores = [score for _, score in places_with_scores]
    max_score = max(scores)
    exp_scores = [math.exp((score - max_score) / temperature) for score in scores]
    total = sum(exp_scores)
    probabilities = [exp_score / total for exp_score in exp_scores]
    
    # 가중 랜덤 샘플링
    sampled = []
    available_indices = list(range(len(places_with_scores)))
    
    for _ in range(min(count, len(places_with_scores))):
        if not available_indices:
            break
            
        # 확률에 따라 인덱스 선택
        r = random.random()
        cumsum = 0
        selected_idx = None
        
        for i, idx in enumerate(available_indices):
            if idx < len(probabilities):  # 인덱스 범위 확인
                cumsum += probabilities[idx]
                if r <= cumsum:
                    selected_idx = i
                    break
        
        if selected_idx is None:
            selected_idx = 0
        
        # 선택된 장소 추가
        actual_idx = available_indices[selected_idx]
        sampled.append(places_with_scores[actual_idx])
        
        # 선택된 인덱스 제거
        available_indices.pop(selected_idx)
        
        # 확률 배열에서 해당 인덱스 제거
        if actual_idx < len(probabilities):
            probabilities.pop(actual_idx)
        
        # 확률 재정규화
        if probabilities:
            total = sum(probabilities)
            if total > 0:
                probabilities = [p / total for p in probabilities]
    
    return sampled

@bp.route('/lunch')
def lunch_home():
    """NoonPick 메인 페이지"""
    lang = get_language_from_request(request)
    
    # 오피스 목록 조회
    db = get_db()
    offices = db.execute("SELECT code, name FROM offices ORDER BY is_default DESC, code").fetchall()
    
    user_info = {
        'email': 'lwk9589@gmail.com',
        'name': '이원규',
        'org_name': 'Service Architect',
        'title': 'Developer',
        'is_admin': True
    }
    
    return render_template('noonpick/main.html', 
                         offices=offices,
                         kakao_js_key=KAKAO_JAVASCRIPT_KEY,
                         active='noonpick', 
                         user=user_info,
                         lang=lang)

@bp.route('/api/lunch/reco')
def recommend_lunch():
    """점심 추천 API"""
    office_code = request.args.get('office', 'seoul')
    radius = int(request.args.get('radius', 300))
    categories = request.args.get('cats', '').split(',') if request.args.get('cats') else []
    exclude_ids = [int(x) for x in request.args.get('exclude', '').split(',') if x.strip()]
    
    db = get_db()
    
    # 오피스 정보 조회
    office = db.execute("SELECT lat, lng FROM offices WHERE code = ?", (office_code,)).fetchone()
    if not office:
        return jsonify({'error': '오피스를 찾을 수 없습니다.'}), 404
    
    # 후보 장소 조회
    excluded_clause = ""
    params = [office['lat'], office['lng'], radius]
    
    if exclude_ids:
        excluded_clause = f"AND id NOT IN ({','.join(['?' for _ in exclude_ids])})"
        params.extend(exclude_ids)
    
    places = db.execute(f"""
        SELECT id, name, lat, lng, big_categories, address, road_address, 
               distance_m, kakao_place_url, phone, photo_url
        FROM places 
        WHERE distance_m <= ? {excluded_clause}
        ORDER BY distance_m
    """, [radius] + (exclude_ids if exclude_ids else [])).fetchall()
    
    if not places:
        return jsonify({'error': '추천할 장소가 없습니다.'}), 404
    
    # 점수 계산 및 상위 N개 선택
    places_with_scores = []
    for place in places:
        score = calculate_score(place, radius, categories)
        if score > 0.1:  # 최소 점수 필터
            places_with_scores.append((dict(place), score))
    
    # 점수순 정렬 후 상위 10개
    places_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_places = places_with_scores[:10]
    
    # 가중 랜덤 샘플링으로 3개 선택
    selected = weighted_random_sample(top_places, 3)
    
    if not selected:
        return jsonify({'error': '추천할 장소가 없습니다.'}), 404
    
    # OG 메타 정보 추가
    result_places = []
    for place, score in selected:
        og_meta = get_or_create_og_cache(place['kakao_place_url'])
        place['og'] = og_meta
        place['score'] = round(score, 3)
        result_places.append(place)
    
    # 결과 구성
    primary = result_places[0]
    alternatives = result_places[1:] if len(result_places) > 1 else []
    excluded_suggestion = exclude_ids + [place['id'] for place, _ in selected]
    
    # 메뉴 추천 로그
    user_email = 'lwk9589@gmail.com'  # 현재 사용자
    noon_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    candidates = [place['name'] for place in result_places]
    
    log_event(user_email, 'noonpick', 'menu_recommended', f"NOON-{noon_time}", {
        'ts_noon': noon_time,
        'candidates': candidates,
        'office': office_code,
        'radius': radius,
        'categories': categories,
        'source': 'user'
    })
    
    return jsonify({
        'primary': primary,
        'alternatives': alternatives,
        'excluded_suggestion': excluded_suggestion
    })

@bp.route('/api/lunch/visit', methods=['POST'])
def record_visit():
    """방문 기록 저장"""
    data = request.get_json()
    place_id = data.get('place_id')
    user_id = data.get('user_id', 1)  # 임시 사용자 ID
    
    if not place_id:
        return jsonify({'error': '장소 ID가 필요합니다.'}), 400
    
    db = get_db()
    
    # 메뉴 이름 조회
    place = db.execute("SELECT name FROM places WHERE id = ?", (place_id,)).fetchone()
    menu_name = place['name'] if place else f"place_{place_id}"
    
    db.execute("""
        INSERT INTO visits (user_id, place_id, visited_at)
        VALUES (?, ?, datetime('now'))
    """, (user_id, place_id))
    db.commit()
    
    # 메뉴 선택 로그
    user_email = 'lwk9589@gmail.com'  # 현재 사용자
    log_event(user_email, 'noonpick', 'menu_selected', str(place_id), {
        'menuId': str(place_id),
        'menuName': menu_name,
        'source': 'user'
    })
    
    return jsonify({'success': True})

@bp.route('/internal/lunch/ingest', methods=['POST'])
def ingest_places():
    """카카오 API로 장소 데이터 수집"""
    data = request.get_json()
    office_code = data.get('office_code', 'seoul')
    radius = data.get('radius', 500)
    keywords = data.get('keywords', ['맛집', '한식', '중식', '일식', '양식', '카페'])
    
    db = get_db()
    
    # 오피스 정보 조회
    office = db.execute("SELECT lat, lng FROM offices WHERE code = ?", (office_code,)).fetchone()
    if not office:
        return jsonify({'error': '오피스를 찾을 수 없습니다.'}), 404
    
    lat, lng = office['lat'], office['lng']
    total_places = 0
    
    # 키워드별 검색
    for keyword in keywords:
        try:
            # 카테고리 검색
            category_result = search_places_by_category(lat, lng, radius)
            if category_result and category_result.get('documents'):
                for doc in category_result['documents']:
                    place_key = hashlib.md5(doc['place_url'].encode()).hexdigest()
                    big_cats = map_category_to_big_categories(doc['category_name'])
                    
                    # 사진 URL 생성 (Google Places API 우선, 카카오 API, 카테고리 기반 순)
                    big_cats = map_category_to_big_categories(doc['category_name'])
                    photo_url = None
                    
                    # 1. Google Places API로 실제 가게 사진 시도
                    google_place_id = search_google_place(doc['place_name'], float(doc['y']), float(doc['x']))
                    if google_place_id:
                        photo_url = get_google_place_photos(google_place_id)
                    
                    # 2. Google 사진이 없으면 카카오 API 시도
                    if not photo_url and 'id' in doc:
                        photo_url = get_place_photos(doc['id'])
                    
                    # 3. 실제 사진이 없으면 카테고리 기반 이미지 사용
                    if not photo_url:
                        photo_url = search_food_image(doc['place_name'], big_cats)
                    
                    db.execute("""
                        INSERT OR REPLACE INTO places 
                        (provider, provider_key, name, lat, lng, raw_category, big_categories,
                         phone, address, road_address, distance_m, kakao_place_url, photo_url, last_seen_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        'kakao', place_key, doc['place_name'], 
                        float(doc['y']), float(doc['x']),
                        doc['category_name'], json.dumps(big_cats),
                        doc.get('phone', ''), doc['address_name'], doc['road_address_name'],
                        int(doc['distance']), doc['place_url'], photo_url
                    ))
                    total_places += 1
            
            # 키워드 검색
            keyword_result = search_places_by_keyword(lat, lng, radius, keyword)
            if keyword_result and keyword_result.get('documents'):
                for doc in keyword_result['documents']:
                    place_key = hashlib.md5(doc['place_url'].encode()).hexdigest()
                    big_cats = map_category_to_big_categories(doc['category_name'])
                    
                    # 사진 URL 생성 (Google Places API 우선, 카카오 API, 카테고리 기반 순)
                    big_cats = map_category_to_big_categories(doc['category_name'])
                    photo_url = None
                    
                    # 1. Google Places API로 실제 가게 사진 시도
                    google_place_id = search_google_place(doc['place_name'], float(doc['y']), float(doc['x']))
                    if google_place_id:
                        photo_url = get_google_place_photos(google_place_id)
                    
                    # 2. Google 사진이 없으면 카카오 API 시도
                    if not photo_url and 'id' in doc:
                        photo_url = get_place_photos(doc['id'])
                    
                    # 3. 실제 사진이 없으면 카테고리 기반 이미지 사용
                    if not photo_url:
                        photo_url = search_food_image(doc['place_name'], big_cats)
                    
                    db.execute("""
                        INSERT OR REPLACE INTO places 
                        (provider, provider_key, name, lat, lng, raw_category, big_categories,
                         phone, address, road_address, distance_m, kakao_place_url, photo_url, last_seen_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (
                        'kakao', place_key, doc['place_name'], 
                        float(doc['y']), float(doc['x']),
                        doc['category_name'], json.dumps(big_cats),
                        doc.get('phone', ''), doc['address_name'], doc['road_address_name'],
                        int(doc['distance']), doc['place_url'], photo_url
                    ))
                    total_places += 1
                    
        except Exception as e:
            print(f"Error processing keyword '{keyword}': {e}")
    
    db.commit()
    return jsonify({'success': True, 'total_places': total_places})

def init_offices():
    """기본 오피스 데이터 초기화"""
    db = get_db()
    
    # 기존 오피스 확인
    existing = db.execute("SELECT COUNT(*) as count FROM offices").fetchone()
    if existing['count'] > 0:
        return
    
    # 서울 오피스 (정확한 좌표 사용)
    db.execute("""
        INSERT INTO offices (code, name, address, lat, lng, is_default)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('seoul', 'Seoul Office', '서울특별시 강남구 테헤란로 521, 파르나스 타워 16층', 
          37.5093056, 127.0610611, 1))
    
    # 대전 오피스 (정확한 좌표 사용)
    db.execute("""
        INSERT INTO offices (code, name, address, lat, lng, is_default)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('daejeon', 'Daejeon Office', '대전광역시 유성구 문지로 272-16 502호', 
          36.39116, 127.40800, 0))
    
    db.commit()
