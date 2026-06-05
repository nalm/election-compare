#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공공데이터포털에서 8회 지방선거 개표결과 XLSX 다운로드"""
import sys, os
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DATA_URL = "https://www.data.go.kr/data/15101509/fileData.do"
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    print(f"페이지 로드: {DATA_URL}")
    page.goto(DATA_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    # 파일 목록 및 다운로드 링크 탐색
    file_info = page.evaluate(r"""() => {
        const links = [...document.querySelectorAll('a, button')]
            .filter(el => /다운|xlsx|xls|csv|download/i.test(el.textContent + (el.href||'') + (el.getAttribute('onclick')||'')))
            .map(el => ({
                tag: el.tagName,
                text: el.textContent.trim().replace(/\s+/g,' ').slice(0,60),
                href: el.href || '',
                onclick: el.getAttribute('onclick') || '',
                dataUrl: el.getAttribute('data-url') || el.getAttribute('data-href') || ''
            }));
        // 파일 목록 테이블
        const rows = [...document.querySelectorAll('table tr')]
            .map(tr => [...tr.querySelectorAll('td,th')]
                .map(c => c.textContent.trim().replace(/\s+/g,' ').slice(0,50)));
        return { links: links.slice(0,20), rows: rows.slice(0,10), title: document.title,
                 text: document.body?.innerText?.slice(0,600) };
    }""")

    print(f"제목: {file_info['title']}")
    print("\n다운로드 링크들:")
    for lnk in file_info['links']:
        print(f"  <{lnk['tag']}> {lnk['text']!r} href={lnk['href']!r} onclick={lnk['onclick'][:80]!r}")
    print("\n테이블 행들:")
    for row in file_info['rows']:
        print(f"  {row}")
    print(f"\n페이지 텍스트:\n{file_info['text'][:400]}")

    # 직접 다운로드 시도
    print("\n직접 다운로드 시도...")
    download_links = page.evaluate(r"""() => {
        // data.go.kr 파일 다운로드 패턴
        const src = document.documentElement.innerHTML;
        // fileSeq, fileId 패턴
        const seqs = (src.match(/fileSeq[=\s'"]+(\d+)/g)||[]).map(m=>m.replace(/fileSeq[=\s'"]+/,''));
        const ids = (src.match(/fileId[=\s'"]+(\w+)/g)||[]).map(m=>m.replace(/fileId[=\s'"]+/,''));
        // 다운로드 함수 호출
        const scripts = [...document.querySelectorAll('script')].map(s=>s.textContent).join('\n');
        const dnFn = scripts.match(/function\s+\w*[Dd]own\w*[\s\S]{0,400}/)?.[0];
        return { seqs, ids, dnFn: dnFn?.slice(0,300) };
    }""")
    print(f"fileSeq: {download_links['seqs']}")
    print(f"fileId: {download_links['ids']}")
    if download_links['dnFn']:
        print(f"다운로드 함수: {download_links['dnFn'][:200]}")

    # 다운로드 이벤트 처리
    print("\n다운로드 버튼 클릭 시도...")
    try:
        with page.expect_download(timeout=20000) as dl_info:
            # 다운로드 버튼 찾아 클릭
            page.evaluate(r"""() => {
                const btns = [...document.querySelectorAll('a, button')]
                    .filter(el => /다운|download/i.test(el.textContent + (el.href||'')));
                if (btns.length > 0) {
                    console.log('클릭:', btns[0].textContent);
                    btns[0].click();
                    return true;
                }
                return false;
            }""")
        download = dl_info.value
        fname = download.suggested_filename or "8th_election.xlsx"
        out_path = OUT_DIR / fname
        download.save_as(str(out_path))
        print(f"✓ 다운로드 완료: {out_path} ({out_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"자동 클릭 실패: {e}")

        # 직접 URL 시도
        direct_urls = [
            "https://www.data.go.kr/cmm/cmm/fms/FileDown.do?atchFileId=FILE_001718076571438_Q2MRQG&fileSn=1",
            "https://www.data.go.kr/cmm/cmm/fms/FileDown.do?atchFileId=FILE_001718076571438_Q2MRQG&fileSn=0",
        ]
        for du in direct_urls:
            try:
                with page.expect_download(timeout=15000) as dl_info2:
                    page.goto(du)
                dl = dl_info2.value
                out_path = OUT_DIR / (dl.suggested_filename or "8th.xlsx")
                dl.save_as(str(out_path))
                print(f"✓ 직접 URL 다운로드: {out_path}")
                break
            except Exception as e2:
                print(f"  직접 URL 실패: {e2}")

    context.close()
    browser.close()
