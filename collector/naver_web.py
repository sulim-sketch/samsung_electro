# collector/naver_web.py — Selenium 기반 네이버 웹 검색 크롤링 (날짜 필터 지원)
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import config
from collector.utils import setup_logging
from processor.filter import strip_html_tags

logger = setup_logging("pipeline.collector.web")

RESULTS_PER_PAGE  = 10
MAX_PAGES         = 20   # 키워드당 최대 페이지 수 (상한선)
PAGE_LOAD_TIMEOUT = 10   # 페이지 로드 대기 최대 시간 (초)

_POST_URL_RE = re.compile(r"https://blog\.naver\.com/[^/]+/\d+")
_driver: webdriver.Chrome | None = None


def _create_driver() -> webdriver.Chrome:
    """헤드리스 Chrome 드라이버 생성"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def get_driver() -> webdriver.Chrome:
    """드라이버 싱글톤 — 최초 호출 시 생성"""
    global _driver
    if _driver is None:
        logger.info("Chrome 드라이버 초기화")
        _driver = _create_driver()
    return _driver


def quit_driver() -> None:
    """드라이버 종료 (파이프라인 완료 후 호출)"""
    global _driver
    if _driver:
        _driver.quit()
        _driver = None
        logger.info("Chrome 드라이버 종료")


def _build_url(keyword: str, date_str: str, start: int = 1) -> str:
    """날짜 필터가 적용된 네이버 블로그 검색 URL (실제 네이버 URL 형식 기준)"""
    return (
        "https://search.naver.com/search.naver"
        f"?ssc=tab.blog.all"
        f"&sm=tab_jum"
        f"&query={quote(keyword)}"
        f"&nso=p:from{date_str}to{date_str}"
        f"&start={start}"
    )


_UGCITEM_CSS = "div[data-template-id='ugcItem']"
_JS_RENDER_WAIT = 3  # readyState 완료 후 ugcItem 추가 대기 시간 (초)


def _fetch_page(url: str) -> str | None:
    """Selenium으로 페이지 로드 후 JS 렌더링 완료된 HTML 반환

    2단계 대기 전략:
    1. document.readyState == 'complete' 대기 (빠름, 1~2초)
    2. ugcItem 없으면 _JS_RENDER_WAIT초만 추가 대기
       → 결과 없는 페이지: 총 ~4초 (기존 10초에서 단축)
       → 결과 있는 페이지: ugcItem 등장 즉시 반환
    """
    driver = get_driver()
    try:
        driver.get(url)

        # 1단계: 페이지 로드 완료 대기
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # 2단계: ugcItem이 아직 없으면 짧게 추가 대기
        if not driver.find_elements(By.CSS_SELECTOR, _UGCITEM_CSS):
            try:
                WebDriverWait(driver, _JS_RENDER_WAIT).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, _UGCITEM_CSS)
                )
            except Exception:
                pass  # 추가 대기 후에도 없음 → 결과 없음으로 처리

        return driver.page_source
    except Exception as e:
        logger.warning(f"페이지 로드 실패: {url[:80]} | {e}")
        return None


def _parse_results(html: str) -> list[dict]:
    """렌더링된 HTML에서 블로그 게시물 정보 추출"""
    soup  = BeautifulSoup(html, "html.parser")
    items = []

    for item in soup.select("div[data-template-id='ugcItem']"):
        # 제목 & 링크: blog.naver.com/{blogId}/{postNo} 형태
        title_a = item.find("a", href=_POST_URL_RE)
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        link  = title_a["href"]
        if not title or not link:
            continue

        # 설명 (스니펫)
        desc_el = item.select_one(".sds-comps-text-type-body1")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # 블로거 이름: 첫 번째 텍스트 노드
        texts = [t for t in item.stripped_strings]
        bloggername = texts[0] if texts else ""

        # title 필터는 collect_blog_for_date에서 ticker별로 적용
        # 여기서는 제목/링크 유효성만 확인

        items.append({
            "title":       strip_html_tags(title),
            "description": strip_html_tags(description),
            "link":        link,
            "bloggername": bloggername,
        })

    return items


def collect_blog_for_date(
    target_date: date,
    ticker: str = config.DEFAULT_TICKER,
    force: bool = False,
) -> list[dict]:
    """
    Selenium으로 날짜 필터가 적용된 네이버 웹 검색 결과 수집.
    - ticker별 하위 디렉토리에 저장: data/raw/blog/{ticker}/{YYYYMMDD}.json
    """
    date_str     = target_date.strftime("%Y%m%d")
    out_path     = config.RAW_DIR / "blog" / ticker / f"{date_str}.json"
    keywords     = config.get_keywords(ticker)
    title_filter = config.get_title_keyword(ticker)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not force:
        logger.info(f"[WEB] {ticker}/{date_str} 이미 수집됨 — skip")
        with open(out_path, encoding="utf-8") as f:
            return json.load(f).get("items", [])

    seen_links: set[str] = set()
    all_items: list[dict] = []

    for keyword in keywords:
        logger.info(f"[WEB] 키워드='{keyword}' | 날짜={date_str}")
        keyword_count = 0

        for page in range(MAX_PAGES):
            start = page * RESULTS_PER_PAGE + 1
            url   = _build_url(keyword, date_str, start)
            logger.debug(f"[WEB] URL: {url}")

            html = _fetch_page(url)
            time.sleep(config.REQUEST_DELAY)

            if html is None:
                break

            parsed = _parse_results(html)
            if not parsed:
                break

            for item in parsed:
                link  = item["link"]
                title = item.get("title", "")
                # ticker별 title 필터 적용
                if title_filter not in title:
                    continue
                if link not in seen_links:
                    seen_links.add(link)
                    all_items.append({
                        **item,
                        "postdate": target_date.strftime("%Y-%m-%d"),
                        "keyword":  keyword,
                    })
                    keyword_count += 1

        logger.info(f"[WEB] '{keyword}' 완료: {keyword_count}건 (누적 {len(all_items)}건)")

    result = {
        "date":    date_str,
        "ticker":  ticker,
        "channel": "blog_web",
        "total":   len(all_items),
        "items":   all_items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"[WEB] {ticker}/{date_str} 저장 완료: {len(all_items)}건")
    return all_items


if __name__ == "__main__":
    from datetime import timedelta
    test_date = date.today() - timedelta(days=1)
    print(f"[테스트] {test_date} Selenium 크롤링 시작")
    items = collect_blog_for_date(test_date, force=True)
    print(f"수집 결과: {len(items)}건")
    if items:
        print(f"첫 번째: {items[0]}")
    quit_driver()
