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
  # 단일 실행
  python main.py --name 삼성전기 --ticker 009150 --range 20240601 20260531

  # 병렬 실행 (3분할) — 수집만
  python main.py --name 삼성전기 --ticker 009150 --range 20240601 20250131 --collect-only
  python main.py --name 삼성전기 --ticker 009150 --range 20250201 20251031 --collect-only
  python main.py --name 삼성전기 --ticker 009150 --range 20251101 20260531 --collect-only

  # 병렬 완료 후 집계
  python main.py --name 삼성전기 --ticker 009150 --aggregate

  # 특정 날짜 1일
  python main.py --name 삼성전기 --ticker 009150 --date 20240601
        """,
    )

    parser.add_argument("--name",   required=True, help="종목명 (예: 삼성전기)")
    parser.add_argument("--ticker", required=True,
                        help="종목 코드 6자리 (예: 009150, 뒤에 .KS 자동 추가)")

    # 실행 모드 (셋 중 하나)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--date",     metavar="YYYYMMDD", help="특정 날짜 1일치 수집 후 집계")
    mode.add_argument("--range",    nargs=2, metavar=("FROM", "TO"),
                      help="날짜 범위 수집 후 집계")
    mode.add_argument("--collect-only", nargs=2, metavar=("FROM", "TO"),
                      help="날짜 범위 수집만 (집계 생략, 병렬 실행용)")
    mode.add_argument("--aggregate", action="store_true",
                      help="수집 없이 집계만 수행 (전체 raw 파일 기준)")

    parser.add_argument("--force", action="store_true", help="이미 수집된 날짜도 강제 재수집")
    return parser.parse_args()


# ── 날짜 목록 생성 ────────────────────────────────────────────────────────────

def build_date_list(date_arg=None, range_arg=None) -> list[date]:
    if date_arg:
        ds = date_arg
        try:
            return [date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))]
        except (ValueError, IndexError):
            logger.error(f"날짜 형식 오류: '{ds}'")
            sys.exit(1)

    if range_arg:
        from_str, to_str = range_arg
        try:
            from_date = date(int(from_str[:4]), int(from_str[4:6]), int(from_str[6:]))
            to_date   = date(int(to_str[:4]),   int(to_str[4:6]),   int(to_str[6:]))
            return [from_date + timedelta(days=i)
                    for i in range((to_date - from_date).days + 1)]
        except (ValueError, IndexError):
            logger.error("날짜 형식 오류 — YYYYMMDD 형식으로 입력하세요.")
            sys.exit(1)

    return []


def is_collected(target_date: date, name: str) -> bool:
    date_str = target_date.strftime("%Y%m%d")
    return (config.RAW_DIR / "blog" / name / f"{date_str}.json").exists()


# ── 수집 ─────────────────────────────────────────────────────────────────────

def collect(date_list: list[date], name: str, force: bool = False) -> list[date]:
    collected: list[date] = []
    skip_count = error_count = 0

    with tqdm(date_list, desc=f"[{name}] 수집", unit="일", ncols=80) as pbar:
        for target_date in pbar:
            pbar.set_postfix(date=str(target_date), skip=skip_count)
            if not force and is_collected(target_date, name):
                skip_count += 1
                collected.append(target_date)
                continue
            try:
                collect_blog_for_date(target_date, name=name, force=force)
                collected.append(target_date)
            except Exception as e:
                error_count += 1
                logger.error(f"{target_date} 수집 오류: {e}", exc_info=True)

    logger.info(f"수집 완료: {len(collected)}일 (skip {skip_count}일, 오류 {error_count}일)")
    return collected


# ── 집계 ─────────────────────────────────────────────────────────────────────

def aggregate(name: str, date_list: list[date] | None = None) -> None:
    csv_name = f"daily_summary_{name}.csv"
    print(f"\n[집계] {csv_name} 생성 중...")
    df = build_and_save_summary(date_list, name=name)
    if df.empty:
        print("집계 결과 없음")
    else:
        print(f"[완료] {len(df)}일치 집계 저장: data/processed/{csv_name}\n")
        print(df.tail(10).to_string(index=False))


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main() -> None:
    args         = parse_args()
    name         = args.name
    yahoo_ticker = f"{args.ticker}.KS"   # 6자리 → Yahoo 형식 자동 변환

    # 종목 메타 저장 (최초 1회, 이후 동일 내용 덮어써도 안전)
    config.save_stock_meta(name, yahoo_ticker)
    logger.info(f"종목: {name} ({yahoo_ticker})")

    # ── 집계만
    if args.aggregate:
        aggregate(name)
        return

    # ── 날짜 목록 결정
    if args.date:
        date_list  = build_date_list(date_arg=args.date)
        do_aggregate = True
    elif args.range:
        date_list  = build_date_list(range_arg=args.range)
        do_aggregate = True
    elif args.collect_only:
        date_list  = build_date_list(range_arg=args.collect_only)
        do_aggregate = False
    else:
        sys.exit(1)

    if not date_list:
        print("수집 대상 날짜가 없습니다.")
        sys.exit(1)

    print(
        f"종목: {name} ({yahoo_ticker}) | "
        f"수집 대상: {len(date_list)}일 ({date_list[0]} ~ {date_list[-1]})"
        + (" [수집만]" if not do_aggregate else "")
        + (" [강제 재수집]" if args.force else "")
    )

    collected = collect(date_list, name, force=args.force)
    quit_driver()

    if do_aggregate and collected:
        aggregate(name, sorted(collected))


if __name__ == "__main__":
    main()
