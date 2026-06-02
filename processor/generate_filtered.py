# processor/generate_filtered.py — raw JSON 필터링 후 filtered JSON 생성
#
# 필터 조건:
#   1. title에 종목명 포함 (수집 단계에서 이미 적용, 재확인)
#   2. title에 EXCLUDE_KEYWORDS 미포함
#
# 출력: data/filtered/blog/{name}/YYYYMMDD.json

import argparse
import json
from pathlib import Path

import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config


def filter_items(items: list[dict], name: str) -> list[dict]:
    """필터링 조건 적용 후 통과 항목 반환"""
    result = []
    for item in items:
        title = item.get("title", "")
        if name not in title:
            continue
        if any(kw in title for kw in config.EXCLUDE_KEYWORDS):
            continue
        result.append(item)
    return result


def generate(name: str, start: str = "2024-06-01", end: str = "2026-05-31") -> None:
    raw_dir      = config.RAW_DIR      / "blog" / name
    filtered_dir = config.FILTERED_DIR / "blog" / name

    if not raw_dir.exists():
        print(f"오류: {raw_dir} 디렉토리가 없습니다.")
        return

    filtered_dir.mkdir(parents=True, exist_ok=True)

    total_raw = total_filtered = file_count = 0

    for f in sorted(raw_dir.glob("*.json")):
        ds    = f.stem                              # YYYYMMDD
        d_fmt = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
        if not (start <= d_fmt <= end):
            continue

        raw_data = json.loads(f.read_text(encoding="utf-8"))
        items    = raw_data.get("items", [])
        filtered = filter_items(items, name)

        out = {
            "date":           ds,
            "name":           name,
            "total_raw":      len(items),
            "total_filtered": len(filtered),
            "items":          filtered,
        }

        out_path = filtered_dir / f"{ds}.json"
        out_path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        total_raw      += len(items)
        total_filtered += len(filtered)
        file_count     += 1

    print(f"생성 완료: {filtered_dir}")
    print(f"  처리 파일:  {file_count}개")
    print(f"  raw 총계:   {total_raw:,}건")
    print(f"  필터 통과:  {total_filtered:,}건 ({total_filtered/total_raw*100:.1f}%)" if total_raw else "  데이터 없음")
    print(f"  제외 키워드: {len(config.EXCLUDE_KEYWORDS)}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="raw JSON → filtered JSON 생성")
    parser.add_argument("--name",  required=True, help="종목명 (예: 삼성전기)")
    parser.add_argument("--start", default="2024-06-01", help="시작일 YYYY-MM-DD")
    parser.add_argument("--end",   default="2026-05-31", help="종료일 YYYY-MM-DD")
    args = parser.parse_args()

    generate(args.name, args.start, args.end)
