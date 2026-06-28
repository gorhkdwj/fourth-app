"""지속 유입(경량) — 새 피드백 CSV를 feedback_raw.csv에 append + 자연키 dedup.

  py src/ingest.py <새_피드백.csv>
  (그 뒤) 분류 Skill로 classifications.csv를 채우고  →  py src/run_pipeline.py

DB 없이 단일 CSV 누적 — 소규모 매장 규모(연 수천 건)에 맞춘 적정 설계.
멱등: 같은 파일을 다시 넣어도 중복 0. 날짜는 정규화해 비교하므로 형식이 달라도 같은 건은 중복 처리.
유입 CSV는 id가 없어도 되며(자동 부여), 받은날짜·경로·별점·내용만 있으면 된다.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import normalize_dates
import validate

BASE = Path(__file__).resolve().parent.parent / "data"
RAW = BASE / "feedback_raw.csv"
CLS_FILE = BASE / "classifications.csv"
RAW_FIELDS = ["id", "받은날짜", "경로", "별점", "내용"]


def _key(받은날짜, 경로, 별점, 내용) -> str:
    """날짜를 정규화한 자연키 — 형식 차이(5월 4일 vs 2026-05-04)에도 같은 건은 같은 키."""
    return validate.natural_key(normalize_dates.normalize(받은날짜), 경로, 별점, 내용)


def main(incoming_path, raw_path=RAW, cls_path=CLS_FILE) -> int:
    existing = validate.load_raw(raw_path)
    existing_keys = {_key(r["받은날짜"], r["경로"], r["별점"], r["내용"]) for r in existing}
    next_id = max(int(r["id"]) for r in existing) + 1

    incoming, fields = validate.read_csv(incoming_path)
    validate.require_columns(fields, incoming_path, validate.REQUIRED_FEEDBACK_COLUMNS)

    added, dups, bad = [], 0, []
    for r in incoming:
        star = (r.get("별점") or "").strip()
        if star not in validate.VALID_STARS:
            bad.append(f"별점 '{star}' (내용: {r['내용'][:20]})"); continue
        try:
            k = _key(r["받은날짜"], r["경로"], r["별점"], r["내용"])
        except ValueError as e:
            bad.append(str(e)); continue
        if k in existing_keys:
            dups += 1; continue
        existing_keys.add(k)
        added.append({"id": next_id, "받은날짜": r["받은날짜"], "경로": r["경로"],
                      "별점": r.get("별점", ""), "내용": r["내용"]})
        next_id += 1

    if added:
        with Path(raw_path).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=RAW_FIELDS)
            w.writeheader()
            w.writerows(existing + added)

    print(f"추가 {len(added)}건 · 중복 스킵 {dups}건 · 형식오류 {len(bad)}건")
    for b in bad:
        print("  [무시]", b)

    # 신규 행 중 분류가 아직 없는 것 안내(증분 분류 대상)
    if added:
        cls_rows, _ = validate.read_csv(cls_path)
        cls_keys = {validate.natural_key(c["받은날짜"], c["경로"], c["별점"], c["내용"]) for c in cls_rows}
        todo = [a for a in added
                if validate.natural_key(normalize_dates.normalize(a["받은날짜"]),
                                        a["경로"], a["별점"], a["내용"]) not in cls_keys]
        if todo:
            print(f"\n분류 필요 {len(todo)}건 → 분류 Skill로 classifications.csv를 채운 뒤 run_pipeline 실행:")
            for a in todo:
                print(f"  id{a['id']} {a['내용'][:30]}")
        else:
            print("\n신규 행이 모두 분류돼 있음 → 바로 run_pipeline 실행 가능")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: py src/ingest.py <새_피드백.csv>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
