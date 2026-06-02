# config.py — 키워드, 날짜 범위, API 설정 등 전역 상수 관리
from datetime import date, timedelta
from pathlib import Path

# ── 디렉토리 경로 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = BASE_DIR / "logs"

# ── 수집 기간: 오늘 기준 최근 2년 ─────────────────────────────────────────────
TODAY = date.today()
START_DATE = TODAY.replace(year=TODAY.year - 2)

# ── 종목 설정 ─────────────────────────────────────────────────────────────────
DEFAULT_TICKER = "009150"

STOCKS: dict = {
    "009150": {
        "name":          "삼성전기",
        "title_keyword": "삼성전기",       # title에 반드시 포함되어야 하는 단어
        "yahoo_ticker":  "009150.KS",
        "keywords": [                       # 네이버 검색 키워드
            "삼성전기 추천",
            "삼성전기 매수",
            "삼성전기 목표주가",
            "삼성전기 강추",
            "삼성전기 Buy",
            "삼성전기 상향",
        ],
    },
    # 새 종목 추가 예시:
    # "005930": {
    #     "name":          "삼성전자",
    #     "title_keyword": "삼성전자",
    #     "yahoo_ticker":  "005930.KS",
    #     "keywords": ["삼성전자 추천", "삼성전자 매수", ...],
    # },
}

def get_keywords(ticker: str = DEFAULT_TICKER) -> list[str]:
    """종목 코드에 해당하는 검색 키워드 반환"""
    return STOCKS[ticker]["keywords"]

def get_title_keyword(ticker: str = DEFAULT_TICKER) -> str:
    """종목 코드에 해당하는 title 필터 단어 반환"""
    return STOCKS[ticker]["title_keyword"]

# 하위 호환성 유지
ALL_KEYWORDS = get_keywords(DEFAULT_TICKER)

# ── 필터링: title 제외 키워드 ─────────────────────────────────────────────────
# title에 이 키워드가 하나라도 있으면 비추천 글로 분류하여 카운트에서 제외
EXCLUDE_KEYWORDS = [
    # 기존
    "맛집", "취준", "합격", "혼밥", "후문", "매탄동", "채용",
    # 시황·마감·특징주
    "시황", "마감", "특징주", "상한가", "하한가", "장중",
    # 매매일지·단타
    "매매일지", "단타", "익절", "손절",
    # 가전제품
    "오븐", "세탁기", "냉장고", "에어컨", "청소기", "큐커",
    # 취업·공채
    "인턴", "공채", "면접", "성과급", "연봉",
    # 식당·장소
    "와인바", "회식",
    # 기타
    "사모펀드",
]

# ── 수집 채널 ─────────────────────────────────────────────────────────────────
CHANNELS = ["blog", "news"]

# ── 네이버 검색 API 엔드포인트 ────────────────────────────────────────────────
NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
NAVER_NEWS_URL  = "https://openapi.naver.com/v1/search/news.json"

# ── API 파라미터 제한 ─────────────────────────────────────────────────────────
API_DISPLAY   = 100    # 1회 요청 최대 결과 수
API_MAX_START = 1000   # start 파라미터 최대값 (API 정책)
API_MAX_PAGES = 10     # 키워드 1개당 최대 페이지 수

# ── 요청 제어 ─────────────────────────────────────────────────────────────────
REQUEST_DELAY  = 0.1   # 요청 간격 (초) — API 호출 제한 준수
MAX_RETRIES    = 3     # 실패 시 최대 재시도 횟수
BACKOFF_FACTOR = 2.0   # 지수 백오프 배수 (1회=1s, 2회=2s, 3회=4s)
