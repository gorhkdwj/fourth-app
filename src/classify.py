"""M1 - Claude가 직접 분류한 결과 + 업계 표준(B) 긴급도 점수 산출.

분류 자체는 data/classifications.csv 에 있다(자연키로 매칭). 그 파일은 분류 Skill(#8)이
새 데이터에 대해 채운다 — classify.py는 분류를 '적용'하고 긴급도만 '계산'한다(재판단 X).
  유형 ∈ {불만, 요청, 칭찬, 문의} · 감정 ∈ {긍정, 부정, 중립}

긴급도 모델 (업계 표준 B) = 심각도 S × 불만강도 I  (불만일 때만, 그 외 0)
  · S : 서비스 실패 심각도. SERVQUAL 5차원 중요도(신뢰성 최우선) 근거로 차등.
  · I : 불만 강도 = max(별점신호, 텍스트신호)
        - 별점은 제외되지 않고 한 입력으로 참여(결측 시 그 항만 빠짐)
        - 두 신호 중 '더 위험한 쪽' 채택 → '급한 불만을 놓치지 않기'에 부합
  · 텍스트신호는 카테고리+키워드+감정강도로 산정(Zendesk/IrisAgent/edesk 류 실무 방식)
  · 동점: 금전 손실/환불 요구 우선 → 최근 날짜순
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate

BASE = Path(__file__).resolve().parent.parent / "data"
SRC = BASE / "feedback_step1_dates.csv"
DST = BASE / "feedback_classified.csv"

# 실패 차원별 심각도 (SERVQUAL 근거) — 조정 가능한 상수
SEVERITY = {"신뢰성": 4, "응답성": 3, "유형성": 2, "제품기호": 1, "해당없음": 0}

# 텍스트신호를 최고치(3)로 끌어올리는 키워드 — 조정 가능한 상수
URGENT_KEYWORDS = ("환불", "결제", "포인트", "오류", "두 번")   # 금전/신뢰성 긴급
STRONG_NEG_KEYWORDS = ("불만", "다 식", "최악", "엉망", "화가")  # 강한 부정 표현

CLS_FILE = BASE / "classifications.csv"  # 분류 데이터(Claude/Skill 산출) — 자연키로 매칭


def load_classifications() -> dict:
    """classifications.csv → {자연키: (유형, 감정, 실패차원, 급한이유)}."""
    rows, fields = validate.read_csv(CLS_FILE)
    needed = ("받은날짜", "경로", "별점", "내용", "유형", "감정", "실패차원", "급한이유")
    miss = [c for c in needed if c not in fields]
    if miss:
        raise validate.DataValidationError(f"classifications.csv 컬럼 누락: {miss}")
    out = {}
    for cr in rows:
        k = validate.natural_key(cr["받은날짜"], cr["경로"], cr["별점"], cr["내용"])
        out[k] = (cr["유형"], cr["감정"], cr["실패차원"], cr["급한이유"])
    return out


def star_signal(star: str):
    """별점신호: 1->3, 2->2, 3->1, 4·5->0. 결측이면 None(미적용)."""
    return {"1": 3, "2": 2, "3": 1, "4": 0, "5": 0}.get(star.strip())


def text_signal(content: str, sentiment: str) -> int:
    """텍스트신호: 긴급/금전 키워드·강한 부정 -> 3, 그 외 감정 기반(부정2/중립1/긍정0)."""
    if any(k in content for k in URGENT_KEYWORDS) or any(k in content for k in STRONG_NEG_KEYWORDS):
        return 3
    return {"부정": 2, "중립": 1, "긍정": 0}[sentiment]


def dissatisfaction(star: str, content: str, sentiment: str) -> int:
    """불만강도 I = max(별점신호, 텍스트신호). 별점 결측 시 텍스트신호만."""
    ts = text_signal(content, sentiment)
    ss = star_signal(star)
    return ts if ss is None else max(ss, ts)


def main() -> None:
    rows, fields = validate.read_csv(SRC)            # ① 파일 존재
    validate.require_columns(fields, SRC)            # ② 필수 컬럼
    cls = load_classifications()                     # 분류 데이터 로드
    miss = [r["id"] for r in rows                    # ④ 분류 누락
            if validate.natural_key(r["받은날짜"], r["경로"], r["별점"], r["내용"]) not in cls]
    if miss:
        raise validate.DataValidationError(
            f"분류 누락 id: {miss}\n"
            f"  → 분류 Skill로 data/classifications.csv에 해당 피드백 분류를 추가하세요.")

    out_fields = ["id", "받은날짜", "경로", "별점", "내용", "유형", "감정", "실패차원",
                  "별점신호", "텍스트신호", "불만강도", "긴급도", "금전손실", "급한이유"]
    out = []
    for r in rows:
        rid = int(r["id"])
        k = validate.natural_key(r["받은날짜"], r["경로"], r["별점"], r["내용"])
        유형, 감정, 실패차원, 이유 = cls[k]
        if 유형 == "불만":
            ss = star_signal(r["별점"])
            ts = text_signal(r["내용"], 감정)
            강도 = ts if ss is None else max(ss, ts)
            긴급도 = SEVERITY[실패차원] * 강도
            금전손실 = 1 if "환불" in r["내용"] else 0  # 직접 환불 요구 = 재무·법적 리스크
            ss_out = "" if ss is None else ss
        else:
            ss_out = ts = 강도 = 긴급도 = 금전손실 = ""  # 점수화는 불만만
        out.append({
            "id": rid, "받은날짜": r["받은날짜"], "경로": r["경로"],
            "별점": r["별점"], "내용": r["내용"],
            "유형": 유형, "감정": 감정, "실패차원": 실패차원,
            "별점신호": ss_out, "텍스트신호": ts, "불만강도": 강도,
            "긴급도": 긴급도, "금전손실": 금전손실, "급한이유": 이유,
        })

    with DST.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out)

    # 검증 출력
    print(f"OK: {len(out)}행 -> {DST.name}")
    print("유형별:", dict(Counter(o["유형"] for o in out)))
    top = sorted([o for o in out if o["유형"] == "불만"],
                 key=lambda o: (o["긴급도"], o["금전손실"], o["받은날짜"]), reverse=True)[:5]
    print("긴급도 상위 5(불만):")
    for o in top:
        ss = o["별점신호"] if o["별점신호"] != "" else "-"
        print(f"  id{o['id']:>2} 긴급도{o['긴급도']:>2} = S{SEVERITY[o['실패차원']]}({o['실패차원']}) "
              f"x I{o['불만강도']} [별점{ss}/텍스트{o['텍스트신호']}] | {o['급한이유']}")


if __name__ == "__main__":
    main()
