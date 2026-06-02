# main.py — 종목별 온라인 추천 데이터 수집 파이프라인 진입점
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

_ROOT = Path(__file__).parent
load_dotenv(_ROOT / ".env")

import config
from collector.naver_web import collect_blog_for_date, quit_driver
from collector.utils import setup_logging
from processor.aggregator import build_and_save_summary

logger = setup_logging("pipeline")


# ── CLI 인수 파싱 ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="종목별 온라인 추천 데이터 수집 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py --days 7                          # 기본 종목(009150) 최근 7일
  python main.py --ticker 009150 --days 7          # 종목 명시
  python main.py --ticker 009150 --range 20240601 20241231
  python main.py --ticker 009150 --backfill
  python main.py --ticker 009150 --days 30 --force
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date",     metavar="YYYYMMDD", help="특정 날짜 1일치 수집")
    group.add_argument("--backfill", action="store_true", help=f"최근 2년 전체 수집")
    group.add_argument("--days",     type=int, metavar="N", help="오늘부터 N일 전까지 수집")
    group.add_argument("--range",    nargs=2, metavar=("FROM", "TO"), help="날짜 범위 수집")

    parser.add_argument(
        "--ticker",
        default=config.DEFAULT_TICKER,
        choices=list(config.STOCKS.keys()),
        help=f"종목 코드 (기본: {config.DEFAULT_TICKER})",
    )
    parser.add_argument("--force", action="store_true", help="이미 수집된 날짜도 강제 재수집")
    return parser.parse_args()


# ── 날짜 목록 생성 ────────────────────────────────────────────────────────────

def build_date_list(args: argparse.Namespace) -> list[date]:
    if args.date:
        ds = args.date
        try:
            return [date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))]
        except (ValueError, IndexError):
            logger.error(f"날짜 형식 오류: '{ds}'")
            sys.exit(1)

    if args.backfill:
        delta = (config.TODAY - config.START_DATE).days
        return [config.START_DATE + timedelta(days=i) for i in range(delta + 1)]

    if args.days:
        if args.days < 1:
            logger.error("--days 값은 1 이상이어야 합니다.")
            sys.exit(1)
        return [config.TODAY - timedelta(days=i) for i in range(args.days - 1, -1, -1)]

    if args.range:
        from_str, to_str = args.range
        try:
            from_date = date(int(from_str[:4]), int(from_str[4:6]), int(from_str[6:]))
            to_date   = date(int(to_str[:4]),   int(to_str[4:6]),   int(to_str[6:]))
            return [from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)]
        except (ValueError, IndexError):
            logger.error("날짜 형식 오류 — YYYYMMDD 형식으로 입력하세요.")
            sys.exit(1)

    return []


def is_collected(target_date: date, ticker: str) -> bool:
    date_str = target_date.strftime("%Y%m%d")
    return (config.RAW_DIR / "blog" / ticker / f"{date_str}.json").exists()


# ── 파이프라인 실행 ───────────────────────────────────────────────────────────

def run_pipeline(date_list: list[date], ticker: str, force: bool = False) -> None:
    stock_name = config.STOCKS[ticker]["name"]
    logger.info(
        f"파이프라인 시작: [{ticker}] {stock_name} | "
        f"총 {len(date_list)}일 ({date_list[0]} ~ {date_list[-1]}) | force={force}"
    )

    collected_dates: list[date] = []
    skip_count  = 0
    error_count = 0

    with tqdm(date_list, desc=f"[{ticker}] 수집", unit="일", ncols=80) as pbar:
        for target_date in pbar:
            pbar.set_postfix(date=str(target_date), skip=skip_count)

            if not force and is_collected(target_date, ticker):
                skip_count += 1
                collected_dates.append(target_date)
                continue

            try:
                collect_blog_for_date(target_date, ticker=ticker, force=force)
                collected_dates.append(target_date)
            except Exception as e:
                error_count += 1
                logger.error(f"{target_date} 수집 오류: {e}", exc_info=True)

    logger.info(f"수집 완료: {len(collected_dates)}일 (skip {skip_count}일, 오류 {error_count}일)")

    if not collected_dates:
        logger.warning("집계할 날짜가 없습니다.")
        quit_driver()
        return

    csv_name = f"daily_summary_{ticker}.csv"
    print(f"\n[집계] {csv_name} 생성 중...")
    df = build_and_save_summary(sorted(collected_dates), ticker=ticker)

    if df.empty:
        print("집계 결과 없음")
    else:
        print(f"\n[완료] {len(df)}일치 집계 저장: data/processed/{csv_name}\n")
        print(df.tail(10).to_string(index=False))

    quit_driver()


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main() -> None:
    args      = parse_args()
    date_list = build_date_list(args)

    if not date_list:
        print("수집 대상 날짜가 없습니다.")
        sys.exit(1)

    stock_name = config.STOCKS[args.ticker]["name"]
    print(
        f"종목: [{args.ticker}] {stock_name} | "
        f"수집 대상: {len(date_list)}일 ({date_list[0]} ~ {date_list[-1]})"
        + (" [강제 재수집]" if args.force else "")
    )
    run_pipeline(date_list, ticker=args.ticker, force=args.force)


if __name__ == "__main__":
    main()
