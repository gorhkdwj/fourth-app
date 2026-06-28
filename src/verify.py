"""회귀 검증 안전망 — classify/normalize 코드를 재사용하지 않고 별도 로직으로 교차 검증.

매 변경 후 `py src/verify.py`로 무결성·날짜·긴급도·분류값·TOP3가 깨지지 않았는지 즉시 확인.
실패 시 종료코드 1 (원클릭 파이프라인의 게이트로 사용 가능).
"""
import csv
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"

# 검증 기준이 되는 모델 상수 (classify.py와 독립적으로 재선언)
SEVERITY = {"신뢰성": 4, "응답성": 3, "유형성": 2, "제품기호": 1, "해당없음": 0}
URGENT_KEYWORDS = ("환불", "결제", "포인트", "오류", "두 번")
STRONG_NEG_KEYWORDS = ("불만", "다 식", "최악", "엉망", "화가")
VALID_TYPE = {"불만", "요청", "칭찬", "문의"}
VALID_SENT = {"긍정", "부정", "중립"}


def load(name):
    with (BASE / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_date_indep(s: str):
    s = s.strip()
    if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", s):
        y, mo, d = map(int, re.split(r"[-/]", s))
    elif re.fullmatch(r"\d{2}\.\d{1,2}\.\d{1,2}", s):
        y, mo, d = map(int, s.split(".")); y += 2000
    elif re.fullmatch(r"\d{1,2}\s*월\s*\d{1,2}\s*일", s):
        mo, d = map(int, re.findall(r"\d+", s)); y = 2026
    else:
        return None
    return date(y, mo, d).isoformat()


def star_signal(star: str):
    return {"1": 3, "2": 2, "3": 1, "4": 0, "5": 0}.get(star.strip())


def text_signal(content: str, sentiment: str) -> int:
    if any(k in content for k in URGENT_KEYWORDS) or any(k in content for k in STRONG_NEG_KEYWORDS):
        return 3
    return {"부정": 2, "중립": 1, "긍정": 0}[sentiment]


def main() -> int:
    raw = load("feedback_raw.csv")
    step1 = load("feedback_step1_dates.csv")
    cls = load("feedback_classified.csv")
    fails: list[str] = []

    # 1. 무결성
    if not (len(raw) == len(step1) == len(cls)):
        fails.append(f"행수 불일치 raw={len(raw)} step1={len(step1)} cls={len(cls)}")
    ids = [r["id"] for r in raw]
    if len(set(ids)) != len(ids):
        fails.append("raw id 중복")
    rawmap = {r["id"]: r for r in raw}
    for c in cls:
        rr = rawmap.get(c["id"])
        if rr is None:
            fails.append(f"id{c['id']} raw에 없음"); continue
        if c["내용"] != rr["내용"] or c["경로"] != rr["경로"] or (c["별점"] or "") != (rr["별점"] or ""):
            fails.append(f"id{c['id']} 원본 보존 위반")

    # 2. 날짜 ① 독립 재변환
    s1map = {r["id"]: r["받은날짜"] for r in step1}
    for r in raw:
        exp = parse_date_indep(r["받은날짜"])
        got = s1map.get(r["id"])
        if exp is None:
            fails.append(f"id{r['id']} 알 수 없는 날짜 형식: {r['받은날짜']!r}")
        elif exp != got:
            fails.append(f"id{r['id']} 날짜 {r['받은날짜']!r}->{got!r} (기대 {exp!r})")
        if got and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", got):
            fails.append(f"id{r['id']} 날짜 형식 위반: {got!r}")

    # 3. 분류 ② 값 유효성 + 긴급도 독립 재계산
    for c in cls:
        if c["유형"] not in VALID_TYPE:
            fails.append(f"id{c['id']} 유형값 이상: {c['유형']}")
        if c["감정"] not in VALID_SENT:
            fails.append(f"id{c['id']} 감정값 이상: {c['감정']}")
        if c["별점"] and c["별점"] not in {"1", "2", "3", "4", "5"}:
            fails.append(f"id{c['id']} 별점 범위 이상: {c['별점']}")
        if c["유형"] != "불만":
            if c["긴급도"] != "":
                fails.append(f"id{c['id']} 비불만인데 긴급도 값 있음")
            continue
        if c["실패차원"] not in SEVERITY:
            fails.append(f"id{c['id']} 실패차원 이상: {c['실패차원']}"); continue
        ss = star_signal(c["별점"])
        ts = text_signal(c["내용"], c["감정"])
        exp_I = ts if ss is None else max(ss, ts)
        exp_U = SEVERITY[c["실패차원"]] * exp_I
        exp_money = 1 if "환불" in c["내용"] else 0
        if int(c["텍스트신호"]) != ts:
            fails.append(f"id{c['id']} 텍스트신호 불일치 csv={c['텍스트신호']} 기대={ts}")
        if (c["별점신호"] or None) != (None if ss is None else str(ss)):
            fails.append(f"id{c['id']} 별점신호 불일치 csv={c['별점신호']!r} 기대={ss}")
        if int(c["불만강도"]) != exp_I:
            fails.append(f"id{c['id']} 불만강도 불일치 csv={c['불만강도']} 기대={exp_I}")
        if int(c["긴급도"]) != exp_U:
            fails.append(f"id{c['id']} 긴급도 불일치 csv={c['긴급도']} 기대={exp_U}")
        if int(c["금전손실"]) != exp_money:
            fails.append(f"id{c['id']} 금전손실 불일치")

    # 4. TOP3 출력 (참고)
    top = sorted([c for c in cls if c["유형"] == "불만"],
                 key=lambda c: (int(c["긴급도"]), int(c["금전손실"]), c["받은날짜"]), reverse=True)[:3]

    print(f"검증 대상: raw {len(raw)} · classified {len(cls)}행")
    print("TOP3:")
    for i, c in enumerate(top, 1):
        print(f"  {i}. id{c['id']} U={c['긴급도']} (별점{c['별점신호'] or '-'}/텍스트{c['텍스트신호']}) "
              f"{c['실패차원']} | {c['급한이유']}")

    if fails:
        print(f"\n[FAIL] {len(fails)}건")
        for f in fails:
            print("  -", f)
        return 1
    print("\n[PASS] 모든 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
