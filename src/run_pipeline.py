"""원클릭 파이프라인 — raw에서 분류본까지 한 번에 + 자기검증.

  py src/run_pipeline.py        # ① 날짜 통일 → [분류] → ③ 검증
  streamlit run app.py          # 화면(보는 단계는 분리)

단계를 정해진 순서로 자동 실행하고, 각 단계 성공을 확인한 뒤 다음으로 넘어간다.
실패 시 즉시 중단하고 '어느 단계에서 왜' 멈췄는지 출력한다(부분 산출물로 진행하지 않음).
마지막 verify가 게이트 — 검증 실패 시 종료코드 1.

[분류 이음새(seam)]
  현재 '분류' 단계는 코드 classify(정적 CLS 조회)다. 신규 데이터를 받는 환경에서는
  이 자리에 분류 Skill(#8) 산출물을 끼워 넣으면 된다 — 나머지 단계는 그대로 재사용.
"""
import sys
from pathlib import Path

# src/ 를 import 경로에 추가 (다른 cwd에서 실행해도 형제 모듈 import 되도록)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalize_dates
import classify
import verify


def run_step(label: str, fn) -> None:
    print(f"\n[{label}] 실행 ...")
    fn()
    print(f"[{label}] 완료")


def main() -> int:
    print("=== 원클릭 파이프라인 시작 ===")
    try:
        run_step("1/3 날짜 통일", normalize_dates.main)
        # ── 분류 이음새: 지금은 코드 classify, 신규 데이터는 향후 분류 Skill로 교체 ──
        run_step("2/3 분류 + 긴급도", classify.main)
    except Exception as e:
        print(f"\n[중단] 파이프라인 실패: {type(e).__name__}: {e}")
        return 1

    print("\n[3/3 검증] 실행 ...")
    code = verify.main()
    if code != 0:
        print("\n[중단] 검증 실패 — 산출물을 신뢰할 수 없음")
        return code

    print("\n=== 파이프라인 성공: data/feedback_classified.csv 갱신 완료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
