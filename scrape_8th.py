#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울특별시장 읍면동별 개표결과 수집기 — 제8회 전국동시지방선거(2022-06-01)

NEC 선거통계시스템 VCCP08 메뉴에서 구별로 개별 POST 요청.
페이지 네비게이션이 발생하면 재로드 후 재시도.

출력: data/서울시장8회_동별개표결과_YYYYMMDD_HHMM.csv
"""
import csv
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:
    print("playwright가 없습니다. pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ELECTION_ID = "0020220601"
BASE = "https://info.nec.go.kr"
MENU_URL = f"{BASE}/main/showDocument.xhtml?electionId={ELECTION_ID}&topMenuId=VC&secondMenuId=VCCP08"
REPORT_URI = f"/electioninfo/{ELECTION_ID}/vc/vccp08.jsp"
KST = timezone(timedelta(hours=9))

SEOUL_TOWN_CODES = {
    "1101": "종로구", "1102": "중구",     "1103": "용산구",   "1104": "성동구",
    "1105": "광진구", "1106": "동대문구", "1107": "중랑구",   "1108": "성북구",
    "1109": "강북구", "1110": "도봉구",   "1111": "노원구",   "1112": "은평구",
    "1113": "서대문구","1114": "마포구",  "1115": "양천구",   "1116": "강서구",
    "1117": "구로구", "1118": "금천구",   "1119": "영등포구", "1120": "동작구",
    "1121": "관악구", "1122": "서초구",   "1123": "강남구",   "1124": "송파구",
    "1125": "강동구",
}

# 구 1개만 fetch하는 JS — 짧게 실행되므로 컨텍스트 파괴 위험 최소화
FETCH_ONE_JS = r"""
async ([townCode, reportUri, electionId]) => {
  const body = new URLSearchParams({
    electionId,
    requestURI: reportUri,
    topMenuId: 'VC', secondMenuId: 'VCCP08', menuId: 'VCCP08',
    statementId: 'VCCP08_#00',
    electionCode: '3', cityCode: '1100',
    sggCityCode: '-1', townCodeFromSgg: '-1',
    townCode,
    sggTownCode: '-1', checkCityCode: '-1',
    x: '0', y: '0'
  });
  const r = await fetch('/electioninfo/electionInfo_report.xhtml', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body
  });
  const html = await r.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return [...doc.querySelectorAll('table tr')]
    .map(tr => [...tr.querySelectorAll('td,th')]
      .map(c => c.textContent.replace(/\s+/g,' ').trim()));
}
"""


def load_page(page):
    """메뉴 페이지 로드 및 안정화."""
    page.goto(MENU_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(800)


def fetch_one_gu(page, town_code: str, gu_name: str, max_retry: int = 3) -> list:
    """구 1개 데이터 fetch. 네비게이션 오류 시 재로드 후 재시도."""
    for attempt in range(1, max_retry + 1):
        try:
            rows = page.evaluate(FETCH_ONE_JS, [town_code, REPORT_URI, ELECTION_ID])
            return rows
        except PlaywrightError as e:
            if "context was destroyed" in str(e) or "navigation" in str(e).lower():
                print(f"    ⚠ {gu_name} 시도{attempt}: 페이지 재로드 후 재시도")
                load_page(page)
                page.wait_for_timeout(500 * attempt)
            else:
                raise
    print(f"    ✗ {gu_name}: {max_retry}회 재시도 실패", file=sys.stderr)
    return []


def extract_candidate_names(raw_rows: list) -> list:
    """헤더에서 후보자 이름 목록 추출."""
    skip = {"읍면동명", "구분", "선거인수", "투표수", "무효투표수", "기권자수", "계",
            "후보자별 득표수", ""}
    for row in raw_rows[:6]:
        candidates = [c for c in row if c and c not in skip and not c.isdigit()]
        # 이름처럼 생긴 셀 2개 이상 → 후보자 행으로 판단
        if len(candidates) >= 2 and all(len(c) <= 10 for c in candidates):
            return candidates
    return []


def parse_rows(raw_rows: list, gu_name: str, candidate_names: list) -> list:
    """VCCP08 테이블 파싱. 컬럼: 읍면동명|구분|선거인수|투표수|[후보자...]|득표계|무효|기권"""
    n = len(candidate_names)
    skip_dong = set(candidate_names) | {"읍면동명", ""}
    parsed = []

    for row in raw_rows:
        if not row or len(row) < 4 + n + 3:
            continue
        dong = row[0].strip()
        if dong in skip_dong:
            continue

        def clean(v):
            return v.replace(",", "").strip() if v else ""

        votes_raw = clean(row[3])
        if votes_raw and not votes_raw.lstrip("-").isdigit():
            continue  # 숫자가 아니면 헤더 잔재

        record = {
            "구명": gu_name,
            "읍면동명": dong,
            "구분": row[1].strip(),
            "선거인수": clean(row[2]),
            "투표수": votes_raw,
        }
        for i, cname in enumerate(candidate_names):
            record[cname] = clean(row[4 + i])
        record["득표계"]    = clean(row[4 + n])
        record["무효투표수"] = clean(row[4 + n + 1])
        record["기권자수"]   = clean(row[4 + n + 2])
        parsed.append(record)
    return parsed


def collect(out_dir: Path) -> Path:
    print(f"▶ 8회 서울시장 동별 개표결과 수집 (electionId={ELECTION_ID})")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    candidate_names = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        load_page(page)
        print("  페이지 로드 완료")

        for town_code, gu_name in SEOUL_TOWN_CODES.items():
            rows = fetch_one_gu(page, town_code, gu_name)
            if not rows:
                continue

            # 첫 구에서 후보자명 추출
            if not candidate_names:
                candidate_names = extract_candidate_names(rows)
                if candidate_names:
                    print(f"  후보자: {candidate_names}")
                else:
                    print("  ⚠ 후보자 이름 자동 추출 실패 — 헤더 덤프:")
                    for r in rows[:6]:
                        print(f"    {r}")
                    browser.close()
                    sys.exit(1)

            records = parse_rows(rows, gu_name, candidate_names)
            all_records.extend(records)
            dong_count = len([r for r in records if r.get("구분") == "계"])
            print(f"  {gu_name}: {dong_count}개 동")
            time.sleep(0.2)

        browser.close()

    ts = datetime.now(KST).strftime("%Y%m%d_%H%M")
    out_path = out_dir / f"서울시장8회_동별개표결과_{ts}.csv"
    fieldnames = (["구명", "읍면동명", "구분", "선거인수", "투표수"]
                  + candidate_names
                  + ["득표계", "무효투표수", "기권자수"])

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_records)

    dong_total = len([r for r in all_records if r.get("구분") == "계"])
    print(f"\n✓ 저장 완료: {out_path}")
    print(f"  총 {len(all_records)}행 / 동(계 행): {dong_total}개")
    return out_path


if __name__ == "__main__":
    collect(Path("data"))
