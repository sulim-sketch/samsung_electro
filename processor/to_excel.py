# processor/to_excel.py — raw JSON 필터링 후 엑셀 저장
import json
from pathlib import Path

import pandas as pd

import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from collector.utils import setup_logging

logger = setup_logging("pipeline.processor.to_excel")

# title에 이 키워드가 포함된 게시물은 제외
EXCLUDE_KEYWORDS = config.EXCLUDE_KEYWORDS


def is_excluded(title: str) -> bool:
    """제외 키워드가 title에 하나라도 있으면 True"""
    return any(kw in title for kw in EXCLUDE_KEYWORDS)


def load_and_filter() -> list[dict]:
    """
    data/raw/blog/ 의 모든 JSON 파일을 읽어
    - title에 "삼성전기" 포함
    - 제외 키워드 미포함
    조건을 만족하는 게시물만 반환
    """
    raw_dir = config.RAW_DIR / "blog"
    files   = sorted(raw_dir.glob("*.json"))

    rows = []
    for f in files:
        data  = json.loads(f.read_text(encoding="utf-8"))
        date_str = data["date"]  # YYYYMMDD
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        for item in data.get("items", []):
            title = item.get("title", "")

            # 필터 1: title에 "삼성전기" 포함
            if "삼성전기" not in title:
                continue

            # 필터 2: 제외 키워드 없어야 함
            if is_excluded(title):
                continue

            rows.append({
                "날짜":        date_fmt,
                "제목":        title,
                "설명":        item.get("description", ""),
                "링크":        item.get("link", ""),
                "블로거":      item.get("bloggername", ""),
                "검색키워드":  item.get("keyword", ""),
            })

    return rows


def save_to_excel(rows: list[dict], out_path: Path) -> None:
    """필터링된 게시물을 엑셀로 저장"""
    df = pd.DataFrame(rows)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # 시트 1: 전체 게시물 목록
        df.to_excel(writer, sheet_name="게시물 목록", index=False)
        ws = writer.sheets["게시물 목록"]

        # 열 너비 자동 조정
        col_widths = {"날짜": 12, "제목": 60, "설명": 80, "링크": 60, "블로거": 20, "검색키워드": 16}
        for col, width in col_widths.items():
            if col in df.columns:
                col_idx = df.columns.get_loc(col) + 1
                ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = width

        # 시트 2: 날짜별 게시물 수 집계
        daily = (
            df.groupby("날짜")
            .size()
            .reset_index(name="게시물 수")
            .sort_values("날짜")
        )
        daily.to_excel(writer, sheet_name="일별 집계", index=False)
        ws2 = writer.sheets["일별 집계"]
        ws2.column_dimensions["A"].width = 14
        ws2.column_dimensions["B"].width = 12

    logger.info(f"엑셀 저장 완료: {out_path} | {len(df)}건")


if __name__ == "__main__":
    print("raw JSON 필터링 중...")
    rows = load_and_filter()

    total_raw = sum(
        len(json.loads(f.read_text(encoding="utf-8")).get("items", []))
        for f in sorted((config.RAW_DIR / "blog").glob("*.json"))
    )

    print(f"전체 raw: {total_raw:,}건")
    print(f"필터 통과: {len(rows):,}건")
    print(f"  - '삼성전기' title 미포함 제외")
    print(f"  - 제외 키워드 포함 제외: {EXCLUDE_KEYWORDS}")

    if not rows:
        print("저장할 데이터가 없습니다.")
    else:
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out_path = config.PROCESSED_DIR / "samsung_electric_filtered.xlsx"
        save_to_excel(rows, out_path)
        print(f"\n저장 위치: {out_path}")
