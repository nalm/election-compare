#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8회·9회 서울시장 선거 동별 비교 데이터 생성.

입력:
  - data/서울시장8회_동별개표결과.csv   (구분='소계' = 동별 합계)
  - nec_prevote/data/서울시장_동별개표결과_전체_20260605_0139.csv (구분='계' = 동별 합계)

출력:
  - data/서울시장_8회9회_동별비교.csv
컬럼: 구명, 읍면동명, 투표수_8회, 오세훈_8회, 오세훈율_8회,
      투표수_9회, 오세훈_9회, 오세훈율_9회, 득표수증감, 득표율증감
"""
import sys, csv
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CSV_8 = Path("data/서울시장8회_동별개표결과.csv")
CSV_9 = Path("../nec_prevote/data/서울시장_동별개표결과_전체_20260605_0139.csv")
OUT   = Path("data/서울시장_8회9회_동별비교.csv")


def load_csv(path: Path, encoding="utf-8-sig") -> list[dict]:
    with open(path, encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def to_int(v: str) -> int:
    v = v.replace(",", "").strip()
    return int(v) if v.lstrip("-").isdigit() else 0


def vote_rate(votes: int, total: int) -> float:
    return round(votes / total * 100, 2) if total > 0 else 0.0


def normalize_dong(dong: str) -> str:
    """동 이름 정규화 (비교 키로 사용)."""
    return dong.strip().replace(" ", "")


def main():
    print("▶ 8회 데이터 로드")
    rows8 = load_csv(CSV_8)
    dong8 = {
        (r["구명"], normalize_dong(r["읍면동명"])): r
        for r in rows8 if r["구분"] == "소계"
    }
    print(f"  8회 동 수: {len(dong8)}")

    print("▶ 9회 데이터 로드")
    rows9 = load_csv(CSV_9)
    dong9 = {
        (r["구명"], normalize_dong(r["읍면동명"])): r
        for r in rows9 if r["구분"] == "계"
    }
    print(f"  9회 동 수: {len(dong9)}")

    # 매칭 분석
    keys8 = set(dong8)
    keys9 = set(dong9)
    matched = keys8 & keys9
    only8   = keys8 - keys9
    only9   = keys9 - keys8

    print(f"\n매칭 현황:")
    print(f"  양쪽 모두: {len(matched)}개")
    print(f"  8회만: {len(only8)}개")
    print(f"  9회만: {len(only9)}개")

    if only8:
        print(f"\n  8회만 있는 동 ({len(only8)}개):")
        for k in sorted(only8)[:20]:
            print(f"    {k}")
    if only9:
        print(f"\n  9회만 있는 동 ({len(only9)}개):")
        for k in sorted(only9)[:20]:
            print(f"    {k}")

    # 비교 데이터 생성 (매칭된 동만)
    records = []
    for (gu, dong_key) in sorted(matched):
        r8 = dong8[(gu, dong_key)]
        r9 = dong9[(gu, dong_key)]

        # 8회: '국민의힘 오세훈' 컬럼
        oh8_col = next((c for c in r8 if "오세훈" in c), None)
        # 9회: '국민의힘오세훈' 컬럼
        oh9_col = next((c for c in r9 if "오세훈" in c), None)

        if not oh8_col or not oh9_col:
            continue

        votes8  = to_int(r8["투표수"])
        oh8     = to_int(r8[oh8_col])
        votes9  = to_int(r9["투표수"])
        oh9     = to_int(r9[oh9_col])
        rate8   = vote_rate(oh8, votes8)
        rate9   = vote_rate(oh9, votes9)

        records.append({
            "구명":       gu,
            "읍면동명":   r8["읍면동명"],
            "투표수_8회": votes8,
            "오세훈_8회": oh8,
            "오세훈율_8회": rate8,
            "투표수_9회": votes9,
            "오세훈_9회": oh9,
            "오세훈율_9회": rate9,
            "득표수증감": oh9 - oh8,
            "득표율증감": round(rate9 - rate8, 2),
        })

    OUT.parent.mkdir(exist_ok=True)
    fieldnames = ["구명","읍면동명","투표수_8회","오세훈_8회","오세훈율_8회",
                  "투표수_9회","오세훈_9회","오세훈율_9회","득표수증감","득표율증감"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    print(f"\n✓ 저장: {OUT} ({len(records)}개 동)")

    # 요약 통계
    print("\n[요약]")
    gains = sorted(records, key=lambda r: r["득표율증감"], reverse=True)
    print("득표율 상승 TOP5:")
    for r in gains[:5]:
        print(f"  {r['구명']} {r['읍면동명']}: {r['오세훈율_8회']}% → {r['오세훈율_9회']}% ({r['득표율증감']:+.2f}%p)")
    print("득표율 하락 TOP5:")
    for r in gains[-5:]:
        print(f"  {r['구명']} {r['읍면동명']}: {r['오세훈율_8회']}% → {r['오세훈율_9회']}% ({r['득표율증감']:+.2f}%p)")


if __name__ == "__main__":
    main()
