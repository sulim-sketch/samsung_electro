# processor/generate_counts.py — raw JSON → blog_counts_{name}.csv 생성
import argparse
import json
from pathlib import Path

import pandas as pd

import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config


def generate(name: str, start: str = "2024-06-01", end: str = "2026-05-31") -> None:
    raw_dir = config.RAW_DIR / "blog" / name
    if not raw_dir.exists():
        print(f"오류: {raw_dir} 디렉토리가 없습니다.")
        return

    counts = {}
    for f in sorted(raw_dir.glob("*.json")):
        ds    = f.stem                              # YYYYMMDD
        d_fmt = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
        if not (start <= d_fmt <= end):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        cnt  = sum(
            1 for item in data.get("items", [])
            if name in item.get("title", "")
            and not any(kw in item.get("title", "") for kw in config.EXCLUDE_KEYWORDS)
        )
        counts[d_fmt] = cnt

    full_idx = pd.date_range(start, end, freq="D")
    series   = pd.Series(counts).reindex(full_idx.strftime("%Y-%m-%d"), fill_value=0)
    series.index = full_idx

    df = series.reset_index()
    df.columns = ["date", "count"]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = config.PROCESSED_DIR / f"blog_counts_{name}.csv"
    df.to_csv(out, index=False, encoding="utf-8")

    print(f"저장 완료: {out}")
    print(f"  기간:     {start} ~ {end} ({len(df)}일)")
    print(f"  총 건수:  {df['count'].sum():,}건")
    print(f"  제외 키워드: {len(config.EXCLUDE_KEYWORDS)}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="raw JSON → blog_counts_{name}.csv 생성")
    parser.add_argument("--name",  required=True, help="종목명 (예: 삼성전기)")
    parser.add_argument("--start", default="2024-06-01", help="시작일 YYYY-MM-DD (기본: 2024-06-01)")
    parser.add_argument("--end",   default="2026-05-31", help="종료일 YYYY-MM-DD (기본: 2026-05-31)")
    args = parser.parse_args()

    generate(args.name, args.start, args.end)
