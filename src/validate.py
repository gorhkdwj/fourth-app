"""입력 검증·에러 처리 — 핵심 4가지를 한 곳에서.

  ① 파일 존재   ② 필수 컬럼 존재   ③ 별점 범위(빈칸 또는 1~5)   ④ 분류 누락(CLS) id
검증 실패 시 DataValidationError를 '사람이 읽을 수 있는' 메시지와 함께 던진다.
검증 통과 후에만 다음 단계가 진행되도록(원자성) 파이프라인 앞단에서 호출한다.
"""
import csv
import hashlib
from pathlib import Path

REQUIRED_COLUMNS = ("id", "받은날짜", "경로", "별점", "내용")
REQUIRED_FEEDBACK_COLUMNS = ("받은날짜", "경로", "별점", "내용")  # 유입 CSV는 id 없어도 됨
VALID_STARS = {"", "1", "2", "3", "4", "5"}


class DataValidationError(Exception):
    """입력 데이터가 기대 형식을 벗어났을 때."""


def natural_key(받은날짜, 경로, 별점, 내용) -> str:
    """파일내 id가 아닌 '내용 기반' 자연키 — 데이터 누적·재업로드·분류 병합에 안정적.
    별점은 '2'/'2.0'/2/빈칸/NaN을 같은 값으로 정규화해 어디서 불러도 동일 키 생성."""
    s = str(별점).strip()
    star = "" if s in ("", "nan", "None") else str(int(float(s)))
    return hashlib.sha1(f"{받은날짜}|{경로}|{star}|{내용}".encode("utf-8")).hexdigest()[:12]


def read_csv(path) -> tuple[list[dict], list[str]]:
    """① 파일 존재 확인 후 (행, 컬럼명) 반환."""
    p = Path(path)
    if not p.exists():
        raise DataValidationError(
            f"파일을 찾을 수 없습니다: {p}\n  → 원본 CSV를 해당 위치에 두고 다시 실행하세요."
        )
    with p.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def require_columns(fields, path, required=REQUIRED_COLUMNS) -> None:
    """② 필수 컬럼 존재 확인."""
    missing = [c for c in required if c not in fields]
    if missing:
        raise DataValidationError(
            f"필수 컬럼 누락: {missing} (파일: {Path(path).name})\n  현재 컬럼: {fields}"
        )


def load_raw(path) -> list[dict]:
    """원본 CSV 로드 + 검증(① 파일 ② 컬럼 ③ 별점범위 + id 정수·유니크·행존재)."""
    rows, fields = read_csv(path)
    require_columns(fields, path)
    if not rows:
        raise DataValidationError(f"데이터가 0행입니다: {Path(path).name}")

    problems = []
    ids = [str(r["id"]).strip() for r in rows]
    for r in rows:
        if not str(r["id"]).strip().isdigit():
            problems.append(f"id 비정수: {r['id']!r}")
        star = (r["별점"] or "").strip()
        if star not in VALID_STARS:  # ③ 별점 범위
            problems.append(f"id{r['id']} 별점 범위 이상: {r['별점']!r} (빈칸 또는 1~5만 허용)")
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        problems.append(f"id 중복: {dups}")

    if problems:
        raise DataValidationError("입력 검증 실패:\n  - " + "\n  - ".join(problems))
    return rows


def require_classified(ids, cls_keys) -> None:
    """④ 분류 누락 id 확인 — 모든 입력 id가 CLS에 있어야 함."""
    missing = sorted(int(i) for i in ids if int(i) not in cls_keys)
    if missing:
        raise DataValidationError(
            f"분류 누락 id: {missing}\n"
            f"  → src/classify.py의 CLS에 해당 id의 (유형, 감정, 실패차원, 급한이유)를 추가하세요.\n"
            f"  (신규 데이터는 분류 Skill로 이 자리를 채웁니다 — 태스크 #8)"
        )
