#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8회 지방선거 XLSX에서 서울시장(시·도지사) 동별 개표결과 추출.
출력: data/서울시장8회_동별개표결과.csv
컬럼: 구명, 읍면동명, 구분, 선거인수, 투표수, [후보자...], 득표계, 무효투표수, 기권수
"""
import sys, csv
from pathlib import Path
import openpyxl

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

XLSX = Path("data/중앙선거관리위원회_제8회 전국동시지방선거 개표결과_20220601.xlsx")
OUT  = Path("data/서울시장8회_동별개표결과.csv")

def clean(v):
    if v is None: return ""
    s = str(v).replace(",", "").replace("\n", " ").strip()
    return s

def main():
    print(f"▶ XLSX 로드: {XLSX}")
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["시·도지사"]

    # 헤더 구조: 행1=컬럼명, 행2=sub헤더(후보1..6), 행3=후보자명, 행4~=데이터
    # 구분: '' = 합계/거소/관외, '소계' = 동별 합계, '관내사전투표'/'선거일투표' = 세부
    candidate_names = []
    records = []
    cur_region = ""  # 병합 셀 처리용

    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        # 행3: 후보자명 추출 (더불어민주당\n송영길 형태)
        if row_idx == 3:
            for i, cell in enumerate(row):
                if cell and i >= 6:
                    name = clean(cell)
                    if name and name not in ("선거인수", ""):
                        candidate_names.append((i, name))
            print(f"  후보자: {[c[1] for c in candidate_names]}")
            continue

        # 행1~3: 헤더 건너뜀
        if row_idx <= 3:
            continue

        # 선거구명 병합 셀 처리
        region = clean(row[0])
        if region:
            cur_region = region
        if cur_region != "서울특별시":
            continue

        gu    = clean(row[1])
        dong  = clean(row[2])
        gubun = clean(row[3])

        if not gu:
            continue

        # 투표수 유효성 체크
        votes_raw = clean(row[5])
        if votes_raw and not votes_raw.replace("-", "").isdigit():
            continue

        record = {
            "구명": gu,
            "읍면동명": dong,
            "구분": gubun,
            "선거인수": clean(row[4]),
            "투표수": votes_raw,
        }
        for col_idx, cname in candidate_names:
            record[cname] = clean(row[col_idx]) if col_idx < len(row) else ""

        # 득표계=인덱스12, 무효투표수=13, 기권수=14 (행1 헤더 기준 고정)
        record["득표계"]    = clean(row[12]) if len(row) > 12 else ""
        record["무효투표수"] = clean(row[13]) if len(row) > 13 else ""
        record["기권수"]     = clean(row[14]) if len(row) > 14 else ""

        records.append(record)

    wb.close()

    # 서울 통계
    seoul_records = records  # 이미 필터링됨
    dong_count = len([r for r in seoul_records if r["구분"] == "소계"])
    print(f"  서울 전체 행: {len(seoul_records)}, 동(계 행): {dong_count}")

    # CSV 저장
    fieldnames = (["구명", "읍면동명", "구분", "선거인수", "투표수"]
                  + [c[1] for c in candidate_names]
                  + ["득표계", "무효투표수", "기권수"])

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(seoul_records)

    print(f"✓ 저장: {OUT}")

    # 샘플 출력
    print("\n샘플 (종로구 동별 계 행):")
    for r in seoul_records:
        if r["구명"] == "종로구" and r["구분"] == "소계":
            print(f"  {r}")
            break

if __name__ == "__main__":
    main()
