# config.py — 키워드, 날짜 범위, API 설정 등 전역 상수 관리
import json
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
DEFAULT_NAME = "삼성전기"

# 추천 의도 suffix — 종목명 뒤에 붙여 검색 키워드를 자동 생성
RECOMMEND_SUFFIXES = ["추천", "매수", "목표주가", "강추", "Buy", "상향"]

def generate_keywords(stock_name: str) -> list[str]:
    """종목명으로 검색 키워드 자동 생성"""
    return [f"{stock_name} {suffix}" for suffix in RECOMMEND_SUFFIXES]

# 하위 호환성 유지
ALL_KEYWORDS = generate_keywords(DEFAULT_NAME)

# ── 종목 메타 (종목명 ↔ Yahoo 티커 매핑) ──────────────────────────────────────
STOCKS_META_PATH = PROCESSED_DIR / "stocks_meta.json"

def load_stocks_meta() -> dict:
    """stocks_meta.json 로드 (없으면 빈 dict 반환)"""
    if STOCKS_META_PATH.exists():
        return json.loads(STOCKS_META_PATH.read_text(encoding="utf-8"))
    return {}

def save_stock_meta(name: str, yahoo_ticker: str) -> None:
    """종목 메타 저장 — 기존 항목 유지하며 추가/갱신 (병렬 실행 시 동일 데이터 중복 저장은 안전)"""
    STOCKS_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    meta = load_stocks_meta()
    meta[name] = {"yahoo_ticker": yahoo_ticker}
    STOCKS_META_PATH.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def get_yahoo_ticker(name: str) -> str | None:
    """종목명으로 Yahoo Finance 티커 조회"""
    return load_stocks_meta().get(name, {}).get("yahoo_ticker")

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
