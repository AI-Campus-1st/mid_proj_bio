"""평가자별 검수 파일을 하나로 합친다 → data/eval/sentiment_sample.csv

입력: data/eval/sentiment_sample_<x>.csv (x = a, b, c, ...) — 각 파일의 annotator_<x> 열만 읽는다.
출력: data/eval/sentiment_sample.csv
      표본 열(sample_id ~ body_excerpt) + annotator_a, annotator_b, annotator_c, ...
      + majority_label(다수결 제안) + agreement(일치 정도) + label_final + note
      - majority_label: 과반이 같은 라벨이면 그 값, 과반이 없으면 빈칸
      - agreement: 만장일치 / 다수 / 불일치 (라벨이 빠진 평가자가 있으면 '미완료')
      - label_final: 사람이 합의해 채운다. 다시 실행해도 이미 채운 label_final·note 는 sample_id 기준으로 보존한다.
원본 평가자 파일은 수정하지 않는다. 평가자 파일의 행 순서·sample_id·url 이 서로 다르면 멈춘다.
실행: python analysis/merge_annotations.py
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from sentiment_prompt import LABELS  # noqa: E402

EVAL = ROOT / "data" / "eval"
OUT = EVAL / "sentiment_sample.csv"
BASE_COLS = ["sample_id", "url", "stratum", "keyword", "lang", "origin", "published_date", "press",
             "input_basis", "kw_basis", "title", "body_excerpt"]


def read(path: Path) -> list:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    files = sorted(p for p in EVAL.glob("sentiment_sample_*.csv") if re.fullmatch(r"sentiment_sample_[a-z]\.csv", p.name))
    if not files:
        raise SystemExit("평가자 파일(data/eval/sentiment_sample_<x>.csv)이 없습니다.")
    data = {}
    for p in files:
        who = p.stem.rsplit("_", 1)[1]
        rows = read(p)
        col = f"annotator_{who}"
        if col not in rows[0]:
            raise SystemExit(f"{p.name} 에 {col} 열이 없습니다.")
        bad = [r["sample_id"] for r in rows if r[col].strip() and r[col].strip() not in LABELS]
        if bad:
            raise SystemExit(f"{p.name} 의 {col} 에 기회/위험/중립이 아닌 값: {bad[:10]}")
        data[who] = rows

    base = next(iter(data.values()))
    for who, rows in data.items():
        if [(r["sample_id"], r["url"]) for r in rows] != [(r["sample_id"], r["url"]) for r in base]:
            raise SystemExit(f"sentiment_sample_{who}.csv 의 행 순서나 sample_id·url 이 다른 파일과 다릅니다.")

    # 이미 합의해 둔 label_final·note 보존
    kept = {}
    if OUT.exists():
        for r in read(OUT):
            if r.get("label_final", "").strip() or r.get("note", "").strip():
                kept[r["sample_id"]] = (r.get("label_final", "").strip(), r.get("note", "").strip())

    whos = sorted(data)
    cols = BASE_COLS + [f"annotator_{w}" for w in whos] + ["majority_label", "agreement", "label_final", "note"]
    out, agree = [], Counter()
    for i, b in enumerate(base):
        row = {c: b[c] for c in BASE_COLS}
        labels = []
        for w in whos:
            v = data[w][i][f"annotator_{w}"].strip()
            row[f"annotator_{w}"] = v
            labels.append(v)
        given = [v for v in labels if v]
        top, n = Counter(given).most_common(1)[0] if given else ("", 0)
        row["majority_label"] = top if n > len(whos) / 2 else ""
        if len(given) < len(whos):
            row["agreement"] = "미완료"
        elif n == len(whos):
            row["agreement"] = "만장일치"
        elif n > len(whos) / 2:
            row["agreement"] = "다수"
        else:
            row["agreement"] = "불일치"
        row["label_final"], row["note"] = kept.get(b["sample_id"], ("", ""))
        agree[row["agreement"]] += 1
        out.append(row)

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"평가자 {len(whos)}명({', '.join(whos)}) · {len(out)}건 → {OUT.relative_to(ROOT)}")
    print("일치 정도:", dict(agree), f"· 보존한 label_final/note {len(kept)}건")


if __name__ == "__main__":
    main()
