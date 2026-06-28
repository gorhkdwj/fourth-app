"""M0 - 받은날짜를 YYYY-MM-DD 한 형식으로 통일.

4가지 입력 형식을 규칙으로 한 번에 처리한다:
  2026-05-02  (ISO)
  2026/05/03  (슬래시)
  5월 4일     (한글, 연도 없음 -> 2026 가정)
  26.5.6      (점, 2자리 연도)
표준 라이브러리만 사용.
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate

DEFAULT_YEAR = 2026
SRC = Path(__file__).resolve().parent.parent / "data" / "feedback_raw.csv"
DST = Path(__file__).resolve().parent.parent / "data" / "feedback_step1_dates.csv"


def normalize(raw: str) -> str:
    s = raw.strip()
    # 2026-05-02 또는 2026/05/03
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    # 26.5.6  (2자리 연도)
    m = re.fullmatch(r"(\d{2})\.(\d{1,2})\.(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{2000 + y:04d}-{mo:02d}-{d:02d}"
    # 5월 4일  (연도 없음)
    m = re.fullmatch(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", s)
    if m:
        mo, d = map(int, m.groups())
        return f"{DEFAULT_YEAR:04d}-{mo:02d}-{d:02d}"
    raise ValueError(f"알 수 없는 날짜 형식: {raw!r}")


def main() -> None:
    rows = validate.load_raw(SRC)  # ① 파일 ② 컬럼 ③ 별점범위 검증
    for r in rows:
        r["받은날짜"] = normalize(r["받은날짜"])
    with DST.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"OK: {len(rows)}행 -> {DST.name}")
    for r in rows:
        print(f"  {r['id']:>2} {r['받은날짜']} {r['경로']}")


if __name__ == "__main__":
    main()
