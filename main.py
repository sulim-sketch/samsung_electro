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

  # 병렬 실행 (3분할) — 각 터미널에서 동시 실행 가능
  python main.py --name 삼성전기 --ticker 009150 --range 20240601 20250131
  python main.py --name 삼성전기 --ticker 009150 --range 20250201 20251031
  python main.py --name 삼성전기 --ticker 009150 --range 20251101 20260531

  # 특정 날짜 1일
  python main.py --name 삼성전기 --ticker 009150 --date 20240601
        """,
    )

    parser.add_argument("--name",   required=True, help="종목명 (예: 삼성전기)")
    parser.add_argument("--ticker", required=True,
                        help="종목 코드 6자리 (예: 009150, 뒤에 .KS 자동 추가)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date",  metavar="YYYYMMDD", help="특정 날짜 1일치 수집")
    group.add_argument("--range", nargs=2, metavar=("FROM", "TO"),
                       help="날짜 범위 수집 (예: --range 20240601 20260531)")

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

    if args.range:
        from_str, to_str = args.range
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


# ── 파이프라인 실행 ───────────────────────────────────────────────────────────

def run_pipeline(date_list: list[date], name: str, force: bool = False) -> None:
    logger.info(
        f"파이프라인 시작: [{name}] 총 {len(date_list)}일 "
        f"({date_list[0]} ~ {date_list[-1]}) | force={force}"
    )

    skip_count = error_count = 0

    with tqdm(date_list, desc=f"[{name}] 수집", unit="일", ncols=80) as pbar:
        for target_date in pbar:
            pbar.set_postfix(date=str(target_date), skip=skip_count)

            if not force and is_collected(target_date, name):
                skip_count += 1
                continue

            try:
                collect_blog_for_date(target_date, name=name, force=force)
            except Exception as e:
                error_count += 1
                logger.error(f"{target_date} 수집 오류: {e}", exc_info=True)

    logger.info(f"수집 완료 (skip {skip_count}일, 오류 {error_count}일)")
    quit_driver()


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main() -> None:
    args         = parse_args()
    date_list    = build_date_list(args)
    yahoo_ticker = f"{args.ticker}.KS"

    if not date_list:
        print("수집 대상 날짜가 없습니다.")
        sys.exit(1)

    # 종목 메타 저장 (동일 내용 중복 저장 안전)
    config.save_stock_meta(args.name, yahoo_ticker)

    print(
        f"종목: {args.name} ({yahoo_ticker}) | "
        f"수집 대상: {len(date_list)}일 ({date_list[0]} ~ {date_list[-1]})"
        + (" [강제 재수집]" if args.force else "")
    )
    run_pipeline(date_list, name=args.name, force=args.force)


if __name__ == "__main__":
    main()
