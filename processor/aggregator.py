# processor/aggregator.py — 일별 추천 게시물 집계 및 CSV 저장 모듈
import json
from datetime import date
from pathlib import Path

import pandas as pd

import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from collector.utils import setup_logging
from processor.filter import filter_recommendations

logger = setup_logging("pipeline.processor.aggregator")


def load_raw(date_str: str, channel: str, ticker: str = config.DEFAULT_TICKER) -> list[dict]:
    """raw JSON 파일 로드 (ticker 하위 디렉토리 기준)"""
    path = config.RAW_DIR / channel / ticker / f"{date_str}.json"
    if not path.exists():
        logger.debug(f"raw 파일 없음: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("items", [])


def aggregate_date(
    target_date: date,
    ticker: str = config.DEFAULT_TICKER,
) -> dict | None:
    """특정 날짜의 블로그 raw 데이터를 집계하여 딕셔너리 반환"""
    date_str = target_date.strftime("%Y%m%d")
    blog_raw = load_raw(date_str, "blog", ticker)

    if not blog_raw:
        return None

    blog_filtered = filter_recommendations(blog_raw)

    if not blog_filtered:
        return {
            "date":       target_date.strftime("%Y-%m-%d"),
            "blog_count": 0,
            "top_title":  "",
            "top_link":   "",
        }

    top_item = blog_filtered[0]
    return {
        "date":       target_date.strftime("%Y-%m-%d"),
        "blog_count": len(blog_filtered),
        "top_title":  top_item.get("title", ""),
        "top_link":   top_item.get("link", ""),
    }


def build_and_save_summary(
    date_list: list[date] | None = None,
    ticker: str = config.DEFAULT_TICKER,
) -> pd.DataFrame:
    """일별 집계 수행 후 daily_summary_{ticker}.csv 저장"""
    if date_list is None:
        blog_dir   = config.RAW_DIR / "blog" / ticker
        blog_stems = {p.stem for p in blog_dir.glob("*.json")} if blog_dir.exists() else set()
        date_list  = []
        for ds in sorted(blog_stems):
            try:
                date_list.append(date(int(ds[:4]), int(ds[4:6]), int(ds[6:8])))
            except (ValueError, IndexError):
                logger.warning(f"날짜 파싱 실패: {ds}")

    rows: list[dict] = []
    for d in sorted(date_list):
        row = aggregate_date(d, ticker)
        if row is not None:
            rows.append(row)
            logger.debug(f"집계: {d} → 블로그 {row['blog_count']}건")

    if not rows:
        logger.warning("집계할 데이터가 없습니다.")
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.PROCESSED_DIR / f"daily_summary_{ticker}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"일별 집계 저장: {out_path} | {len(df)}일치")
    return df


if __name__ == "__main__":
    print("수집된 전체 날짜 집계 시작...")
    df = build_and_save_summary()
    if not df.empty:
        print(f"\n집계 완료: {len(df)}일치")
        print(df.tail(10).to_string(index=False))
    else:
        print("집계 가능한 데이터 없음")
