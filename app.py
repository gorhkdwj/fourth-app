"""M2 - VoC 한 화면 대시보드.
분류는 하지 않는다. 이미 Claude가 분류한 feedback_classified.csv를 읽어 '계산/표시'만 한다.
사장님의 요청("지금 가장 급한 불만이 뭔지 한 화면에서") 하나에 집중 — 나머지는 덜어냄.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import validate

DATA = Path(__file__).resolve().parent / "data" / "feedback_classified.csv"
RESOLVED_PATH = Path(__file__).resolve().parent / "data" / "resolved.json"
SEVERITY = {"신뢰성": 4, "응답성": 3, "유형성": 2, "제품기호": 1, "해당없음": 0}
URGENT_FLOOR = 4   # 메인 노출 임계: 긴급도 ≥ 4(주시 이상) = '실제 영역 실패 × 실제 불만족'
TOP_N = 3          # 한 번에 보여줄 개수(인지 부하 손잡이, 임계와 별개)


def natural_key(row) -> str:
    """내용 기반 자연키 — classify와 동일한 공통 모듈을 써서 같은 키를 보장."""
    return validate.natural_key(row["받은날짜"], row["경로"], row["별점"], row["내용"])


def load_resolved() -> dict:
    if RESOLVED_PATH.exists():
        return json.loads(RESOLVED_PATH.read_text(encoding="utf-8"))
    return {}


def save_resolved(d: dict) -> None:
    RESOLVED_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

st.set_page_config(page_title="카페 VoC — 가장 급한 불만", page_icon="☕", layout="centered")

if not DATA.exists():
    st.error("분류본(data/feedback_classified.csv)이 없습니다.\n\n"
             "터미널에서 `py src/run_pipeline.py`를 먼저 실행하세요.")
    st.stop()

df = pd.read_csv(DATA, encoding="utf-8-sig")
_required = ["유형", "긴급도", "실패차원", "불만강도", "별점신호", "텍스트신호", "내용", "급한이유"]
_missing = [c for c in _required if c not in df.columns]
if _missing:
    st.error(f"필수 컬럼 누락: {_missing}\n\n`py src/run_pipeline.py`로 분류본을 다시 생성하세요.")
    st.stop()

df["긴급도"] = pd.to_numeric(df["긴급도"], errors="coerce")  # 비불만은 공백 -> NaN

# ── 헤더 ───────────────────────────────────────────────
st.title("☕ 카페 VoC — 지금 가장 급한 불만")
기간 = f"{df['받은날짜'].min()} ~ {df['받은날짜'].max()}"
st.caption(f"기간 {기간} · 피드백 {len(df)}건  ·  분류는 Claude가 사전 수행, 화면은 결과만 표시")

# ── 유형별 지표 ────────────────────────────────────────
counts = df["유형"].value_counts()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🔴 불만", int(counts.get("불만", 0)))
c2.metric("🟡 요청", int(counts.get("요청", 0)))
c3.metric("🟢 칭찬", int(counts.get("칭찬", 0)))
c4.metric("🔵 문의", int(counts.get("문의", 0)))

st.divider()

# ── 가장 급한 불만: 미처리 워크큐 (화면의 주인공) ─────
resolved = load_resolved()

cand = df[(df["유형"] == "불만") & (df["긴급도"] >= URGENT_FLOOR)].copy()
cand["_key"] = cand.apply(natural_key, axis=1)
active = cand[~cand["_key"].isin(resolved)].sort_values(
    ["긴급도", "금전손실", "받은날짜"], ascending=[False, False, False])
top = active.head(TOP_N)

st.subheader(f"🔥 가장 급한 불만 (미처리 TOP {TOP_N})")
st.caption(f"긴급도 ≥ {URGENT_FLOOR}(주시 이상)인 미처리 불만만 표시 · 미처리 {len(active)}건 · "
           f"처리 완료하면 다음 건이 올라옵니다. (긴급도 = 심각도 × 불만강도)")

if top.empty:
    st.success("🎉 처리할 급한 불만이 없습니다.")
else:
    for rank, (_, r) in enumerate(top.iterrows(), start=1):
        별점 = "★" * int(r["별점"]) if pd.notna(r["별점"]) else "별점없음"
        S = SEVERITY[r["실패차원"]]
        ss = "없음" if str(r["별점신호"]).strip() in ("", "nan") else str(r["별점신호"]).split(".")[0]
        ts = str(r["텍스트신호"]).split(".")[0]
        with st.container(border=True):
            st.markdown(f"### {rank}. {r['급한이유']}")
            st.markdown(
                f"**긴급도 {int(r['긴급도'])}**  =  심각도 {S}(`{r['실패차원']}`) × 불만강도 {int(r['불만강도'])}  "
                f"<span style='color:gray'>· 별점신호 {ss} / 텍스트신호 {ts}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"{별점} · {r['경로']} · {r['받은날짜']}")
            st.write(f"💬 {r['내용']}")
            if st.button("✅ 처리 완료", key=f"resolve_{r['_key']}"):
                resolved[r["_key"]] = {
                    "받은날짜": r["받은날짜"], "경로": r["경로"], "내용": r["내용"],
                    "처리시각": datetime.now().isoformat(timespec="seconds"),
                }
                save_resolved(resolved)
                st.rerun()

# 처리 완료 목록 (되돌리기)
if resolved:
    with st.expander(f"✅ 처리 완료 {len(resolved)}건 — 되돌리기"):
        for k, meta in list(resolved.items()):
            cc1, cc2 = st.columns([5, 1])
            cc1.write(f"{meta.get('처리시각', '')} · {meta.get('내용', '')[:40]}")
            if cc2.button("되돌리기", key=f"reopen_{k}"):
                del resolved[k]
                save_resolved(resolved)
                st.rerun()

st.divider()

# ── 실패차원별 불만 분포 (구조적 약점 진단) ───────────
st.subheader("📊 불만은 어느 영역에서 — 실패차원별 분포")
st.caption(f"불만 {int(counts.get('불만', 0))}건을 서비스 영역별로 집계 (드릴다운). "
           f"TOP3는 개별 우선 처리 대상이고, 이 분포는 불만이 집중된 영역을 보여줍니다.")
_order = ["신뢰성", "응답성", "유형성", "제품기호"]
dim = (df[df["유형"] == "불만"]["실패차원"]
       .value_counts()
       .reindex(_order)
       .dropna()
       .astype(int))
if not dim.empty:
    st.bar_chart(dim, horizontal=True, color="#c0504d")
    st.caption(f"불만이 가장 많은 영역: {dim.idxmax()} ({int(dim.max())}건)")
else:
    st.write("집계할 불만이 없습니다.")

st.divider()

# ── 전체 표 (접어둠 — 덜어내기) ───────────────────────
with st.expander("전체 피드백 표 보기"):
    def _status(row):
        if row["유형"] == "불만" and pd.notna(row["긴급도"]) and row["긴급도"] >= URGENT_FLOOR:
            return "✅ 처리됨" if natural_key(row) in resolved else "⏳ 미처리"
        return "—"  # 큐 대상 아님(비불만 또는 긴급도 < 임계)

    df_disp = df.copy()
    df_disp["처리"] = df_disp.apply(_status, axis=1)
    cols = ["처리", "받은날짜", "경로", "별점", "유형", "감정", "실패차원", "불만강도", "긴급도", "내용"]
    disp = df_disp[cols].sort_values("긴급도", ascending=False, na_position="last")
    st.caption("처리: ✅ 처리됨 / ⏳ 미처리(긴급도 ≥ 4 불만) / — 큐 대상 아님 · "
               "긴급도·불만강도는 '불만' 행에만 부여")
    st.dataframe(
        disp.style.format(na_rep="—", precision=0),
        width="stretch", hide_index=True,
    )
