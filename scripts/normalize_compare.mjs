#!/usr/bin/env node
// 8회·9회 서울시장 비교 CSV + seoul-dong GeoJSON → 지도용 JSON
// 출력: public/data/seoul_compare.json
// 사용: node scripts/normalize_compare.mjs

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

const GEO_SRC    = path.join(ROOT, "public/geo/seoul-dong.geojson");
const CSV_SRC    = path.join(ROOT, "data/서울시장_8회9회_동별비교.csv");
const CSV_8_FULL = path.join(ROOT, "data/서울시장8회_동별개표결과.csv");
const OUT_DATA   = path.join(ROOT, "public/data/seoul_compare.json");

// 9회 전체 CSV (거소+관외 포함)
function find9thFullCsv() {
  const dir = path.resolve(ROOT, "../nec_prevote/data");
  const files = fs.readdirSync(dir)
    .filter(f => f.startsWith("서울시장_동별개표결과_전체_") && f.endsWith(".csv"))
    .sort((a, b) => b.localeCompare(a));
  return path.join(dir, files[0]);
}
const CSV_9_FULL = find9thFullCsv();

// ── CSV 파싱 ──────────────────────────────────────────────────────
function parseCsv(fpath) {
  const text = fs.readFileSync(fpath, "utf-8").replace(/^﻿/, "");
  const lines = text.trim().split(/\r?\n/);
  const headers = lines[0].split(",").map(h => h.trim());
  return lines.slice(1).map(ln => {
    const vals = ln.split(",").map(v => v.trim());
    return Object.fromEntries(headers.map((h, i) => [h, vals[i] ?? ""]));
  });
}

function num(v) {
  const n = parseFloat(v?.replace(/,/g, "") ?? "");
  return isNaN(n) ? 0 : n;
}

// ── 동이름 정규화 (CSV 쪽) ─────────────────────────────────────────
// 창신제1동 → 창신1동 (GeoJSON은 제N 없는 형식)
function normDong(nm) {
  return nm.replace(/제(\d)/g, "$1");
}

function geoKey(gu, dong) {
  return `${gu}__${dong}`.replace(/\s/g, "");
}

// ── GeoJSON 인덱싱 ──────────────────────────────────────────────
const geo = JSON.parse(fs.readFileSync(GEO_SRC, "utf-8"));
const geoIndex = new Map();
for (const f of geo.features) {
  const { sggnm, temp } = f.properties;
  const parts = (temp ?? "").split(" ");
  const dongNm = parts[parts.length - 1];
  const key = geoKey(sggnm, dongNm);
  geoIndex.set(key, f);
}
console.log(`GeoJSON 피처: ${geo.features.length}개`);

// ── CSV 로드 & 매칭 ────────────────────────────────────────────
const rows = parseCsv(CSV_SRC);
const matched = [];
const unmatched = [];

for (const row of rows) {
  const gu   = row["구명"];
  const dong = row["읍면동명"];
  if (!gu || !dong) continue;

  const key = geoKey(gu, normDong(dong));
  const feature = geoIndex.get(key);

  if (!feature) {
    unmatched.push(`${gu} ${dong}`);
    continue;
  }

  matched.push({
    adm_cd:      feature.properties.adm_cd,
    gu,
    dong,
    r8:  {
      투표수:  num(row["투표수_8회"]),
      오세훈: num(row["오세훈_8회"]),
      오세훈율: num(row["오세훈율_8회"]),
    },
    r9: {
      투표수:  num(row["투표수_9회"]),
      오세훈: num(row["오세훈_9회"]),
      오세훈율: num(row["오세훈율_9회"]),
    },
    득표수증감: num(row["득표수증감"]),
    득표율증감: num(row["득표율증감"]),
  });
}

console.log(`매칭: ${matched.length}개 / 미매칭: ${unmatched.length}개`);
if (unmatched.length) console.log("미매칭:", unmatched);

// ── 구별 공식 집계 (합계 행 직접 사용 — 거소+관외사전투표 포함) ───────
function loadGuTotals(csvPath, ohCol) {
  const rows = parseCsv(csvPath);
  const result = {};
  for (const row of rows) {
    const gu   = (row["구명"] ?? "").trim();
    const dong = (row["읍면동명"] ?? "").trim();
    if (gu && dong === "합계") {
      const votes = num(row["투표수"]);
      const oh    = num(row[ohCol]);
      const valid = num(row["득표계"]);
      result[gu] = { 투표수: votes, 오세훈: oh, 득표계: valid,
                     오세훈율: valid > 0 ? +(oh / valid * 100).toFixed(2) : 0 };
    }
  }
  return result;
}

const gu8raw = loadGuTotals(CSV_8_FULL, "국민의힘 오세훈");
const gu9raw = loadGuTotals(CSV_9_FULL, "국민의힘오세훈");
console.log(`8회 구별 합계 로드: ${Object.keys(gu8raw).length}개 구`);
console.log(`9회 구별 합계 로드: ${Object.keys(gu9raw).length}개 구`);

// dongCount는 동별 매칭 결과에서 집계
const dongCountMap = {};
for (const m of matched) {
  dongCountMap[m.gu] = (dongCountMap[m.gu] ?? 0) + 1;
}

const guAgg = {};
for (const gu of Object.keys(gu8raw)) {
  const r8 = gu8raw[gu];
  const r9 = gu9raw[gu];
  if (!r9) continue;
  guAgg[gu] = {
    gu,
    r8,
    r9,
    득표율증감: +(r9.오세훈율 - r8.오세훈율).toFixed(2),
    득표수증감: r9.오세훈 - r8.오세훈,
    dongCount:  dongCountMap[gu] ?? 0,
    includesExtra: true,  // 거소+관외사전투표 포함
  };
}
console.log("구별 집계 완료:", Object.keys(guAgg).length, "개 구");

// ── 저장 ──────────────────────────────────────────────────────────
const dataIndex = Object.fromEntries(matched.map(m => [m.adm_cd, m]));
const out = {
  meta: {
    races: ["제8회 전국동시지방선거(2022-06-01)", "제9회 전국동시지방선거(2026-06-03)"],
    candidate: "오세훈(국민의힘)",
    matchedCount: matched.length,
  },
  data: dataIndex,
  guData: guAgg,
};

fs.mkdirSync(path.dirname(OUT_DATA), { recursive: true });
fs.writeFileSync(OUT_DATA, JSON.stringify(out));
console.log(`✓ 저장: ${OUT_DATA}`);

// 간단 요약
const rates = matched.map(m => m.득표율증감).sort((a, b) => a - b);
console.log(`\n득표율 증감 범위: ${rates[0]}%p ~ ${rates[rates.length-1]}%p`);
const avg = (rates.reduce((s, v) => s + v, 0) / rates.length).toFixed(2);
console.log(`평균 증감: ${avg}%p`);
