# -*- coding: utf-8 -*-
"""
2025년 귀속 업종코드 검색기 빌드 스크립트.
data/*.csv 두 개를 읽어 index.html(오프라인 단일 파일)을 생성한다.
매년 CSV만 교체하고 재실행하면 됨.
"""
import csv
import json
import datetime
from pathlib import Path

BASE = Path(__file__).parent
MAIN_CSV = BASE / "data" / "2025년 귀속 업종코드.csv"
LINK_CSV = BASE / "data" / "업종코드-표준산업분류 연계표.csv"
OUT_HTML = BASE / "index.html"


def load_main(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    records = []
    for row in data:
        records.append({
            "code": row[1].strip(),
            "upTae": row[2].strip(),
            "jung": row[3].strip(),
            "se": row[4].strip(),
            "sese": row[5].strip(),
            "gijun": row[6],  # 개행 보존, trim 안 함
            "r1": row[7].strip(),
            "r2": row[8].strip(),
            "r3": row[9].strip(),
            "ksic": [],
        })
    return records


def load_link_groups(path):
    """업종코드 -> [{code, name, main, note}] 딕셔너리와
    업종코드 -> {upTae, jung, se, sese}(업종코드측 분류명) 딕셔너리를 반환.
    레이아웃(실제 CSV 검증 결과):
      col2  = 2025년 귀속 업종코드
      col4  = 업종코드측 대분류명 / col6 = 중분류명 / col8 = 소분류명 / col11 = 세세분류명
      col13 = 표준산업분류(11차) 코드 (인적용역은 '+' 접미사 가능)
      col22 = 표준산업분류 세세분류명
      col24 = 메인 여부('1'이면 메인)
      col25 = 세부설명
    상단 5행은 제목/머리글이며 일련번호(col1)가 숫자인 행부터 데이터.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    # 상단 5행(제목/설명/빈행/일련번호 라벨/컬럼헤더)은 제외하고,
    # 정규 데이터 행(일련번호 숫자) + 업종코드 미대응 KSIC 단독 행(일련번호 없음, KSIC코드만 존재)만 채택
    candidates = rows[5:]
    data_rows = [
        r for r in candidates
        if len(r) > 24 and (r[1].strip().isdigit() or (not r[1].strip() and r[13].strip()))
    ]

    groups = {}
    meta = {}  # 업종코드 -> 업종코드측 분류명(연계표 전용 코드를 레코드화할 때 사용)
    orphan_link_count = 0  # 연계표에는 있으나 업종코드 칸이 비어있는 행(국세청 업종코드 미대응)
    for row in data_rows:
        code = row[2].strip()
        ksic_code = row[13].strip()
        ksic_name = row[22].strip()
        is_main = row[24].strip() == "1"
        note = row[25].strip() if len(row) > 25 else ""
        if not code:
            orphan_link_count += 1
            continue
        meta.setdefault(code, {
            "upTae": row[4].strip(),
            "jung": row[6].strip(),
            "se": row[8].strip(),
            "sese": row[11].strip(),
        })
        if not ksic_code:
            # 예: 381007 소사장제처럼 '해당사항 없음'으로 명시된 행 -> 연계 없음
            groups.setdefault(code, [])
            continue
        groups.setdefault(code, []).append({
            "code": ksic_code,
            "name": ksic_name,
            "main": is_main,
            "note": note,
        })
    return groups, meta, orphan_link_count


def build():
    records = load_main(MAIN_CSV)
    main_record_count = len(records)
    link_groups, link_meta, orphan_link_count = load_link_groups(LINK_CSV)

    main_codes = {r["code"] for r in records}
    matched = 0
    unmatched = 0
    for r in records:
        ksic_list = link_groups.get(r["code"])
        if ksic_list:
            r["ksic"] = ksic_list
            matched += 1
        else:
            r["ksic"] = []
            unmatched += 1

    link_only_codes = sorted(c for c in link_groups if c not in main_codes)
    for code in link_only_codes:
        m = link_meta[code]
        records.append({
            "code": code,
            "upTae": m["upTae"],
            "jung": m["jung"],
            "se": m["se"],
            "sese": m["sese"],
            "gijun": "",  # 적용기준내용 없음(기준경비율 미고시 코드)
            "r1": "",
            "r2": "",
            "r3": "",
            "ksic": link_groups[code],
        })

    records.sort(key=lambda r: r["code"])

    print(f"[기준 테이블] 레코드 수: {main_record_count}")
    print(f"[연계표] 고유 업종코드 그룹 수: {len(link_groups)} (업종코드 칸 비어있는 행: {orphan_link_count})")
    print(f"[조인] KSIC 연계 있음: {matched} / 연계 없음: {unmatched}")
    print(f"[조인] 연계표에만 있고 기준 테이블에 없는 업종코드 → 경비율 없음 레코드로 포함: {len(link_only_codes)}건")
    if link_only_codes:
        print(f"       예시: {link_only_codes[:10]}")
    print(f"[최종] DATA 레코드 수: {len(records)}")

    data_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</script", "<\\/script")

    today = datetime.date.today().isoformat()
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json).replace("__BUILD_DATE__", today)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"[출력] {OUT_HTML} ({OUT_HTML.stat().st_size:,} bytes)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2025년 귀속 업종코드 검색</title>
<style>
:root{
  --main:#00338D;
  --accent:#C5A44E;
  --accent-bg:#C5A44E33;
  --mark-bg:#C5A44E55;
  --text:#222;
  --sub:#666;
  --border:#e2e2e2;
  --bg:#ffffff;
  --card-bg:#fafbfc;
}
*{box-sizing:border-box;}
body{
  margin:0;
  font-family:"Malgun Gothic","맑은 고딕",-apple-system,"Segoe UI",sans-serif;
  background:var(--bg);
  color:var(--text);
  line-height:1.5;
}
header{
  background:var(--main);
  color:#fff;
  padding:24px 20px 20px;
}
header h1{
  margin:0 0 4px;
  font-size:1.4rem;
  font-weight:700;
}
.brand{
  color:var(--accent);
  font-size:0.85rem;
  margin:0 0 14px;
}
#searchBox{
  width:100%;
  max-width:640px;
  padding:12px 16px;
  font-size:1rem;
  border:none;
  border-radius:6px;
  outline:none;
}
#searchBox:focus{
  box-shadow:0 0 0 3px var(--accent);
}
#meta{
  max-width:960px;
  margin:0 auto;
  padding:14px 20px 0;
  color:var(--sub);
  font-size:0.9rem;
}
main{
  max-width:960px;
  margin:0 auto;
  padding:8px 20px 60px;
}
.card{
  border:1px solid var(--border);
  border-radius:8px;
  background:var(--card-bg);
  padding:16px 18px;
  margin:14px 0;
}
.card-head{
  display:flex;
  flex-wrap:wrap;
  align-items:baseline;
  gap:10px;
  justify-content:space-between;
}
.code-title{
  display:flex;
  align-items:baseline;
  gap:10px;
  flex-wrap:wrap;
}
.code{
  color:var(--main);
  font-weight:700;
  font-size:1.25rem;
}
.sese{
  font-weight:700;
  font-size:1.05rem;
}
.rates{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
}
.rate{
  font-size:0.78rem;
  border-radius:12px;
  padding:3px 9px;
  white-space:nowrap;
  border:1px solid var(--border);
  background:#fff;
  color:var(--sub);
}
.rate b{color:var(--main);}
.path{
  color:var(--sub);
  font-size:0.85rem;
  margin-top:4px;
}
.gijun{
  white-space:pre-line;
  margin-top:10px;
  font-size:0.92rem;
  max-height:9.6em;
  overflow:hidden;
  position:relative;
}
.gijun.expanded{max-height:none;}
.more-toggle{
  display:inline-block;
  margin-top:6px;
  color:var(--main);
  font-size:0.85rem;
  cursor:pointer;
  text-decoration:underline;
}
.ksic-wrap{
  margin-top:12px;
  display:flex;
  flex-wrap:wrap;
  gap:6px;
}
.ksic-label{
  font-size:0.8rem;
  color:var(--sub);
  width:100%;
  margin-bottom:2px;
}
.ksic-chip{
  font-size:0.78rem;
  border-radius:12px;
  padding:3px 10px;
  background:#fff;
  border:1px solid var(--border);
  color:var(--text);
}
.ksic-chip.main{
  background:var(--accent-bg);
  border-color:var(--accent);
  font-weight:700;
}
.ksic-note{
  color:var(--sub);
}
mark{
  background:var(--mark-bg);
  color:inherit;
  border-radius:2px;
}
#result-count{font-weight:600;color:var(--main);}
#empty-hint{color:var(--sub);padding:30px 0;text-align:center;}
footer{
  text-align:center;
  color:var(--sub);
  font-size:0.78rem;
  padding:20px 0 30px;
}
</style>
</head>
<body>
<header>
  <h1>2025년 귀속 업종코드 검색</h1>
  <div class="brand">더나은세무법인 덕수 · 김태현 세무사</div>
  <input id="searchBox" type="text" placeholder="키워드 또는 업종코드 입력 — 예: 임가공, 무상사급, 921505" autocomplete="off">
</header>
<div id="meta"><span id="result-count"></span></div>
<main id="results"></main>
<footer>더나은세무법인 덕수 · 김태현 세무사 · 2025년 귀속 업종코드 · 국세청 기준경비율 자료 기반 · 생성일 __BUILD_DATE__</footer>

<script>
const DATA = __DATA_JSON__;
const MAX_RESULTS = 200;

function esc(s){
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// 이스케이프된 문자열 위에 하이라이트 삽입(태그 안 건드리도록 & < > " 이스케이프 후 처리)
// 단일 패스 정규식 alternation + 엔티티 보호 세그먼트 분리: mark 재진입/엔티티 파손 방지
function highlight(escapedText, keywords){
  const parts = keywords.filter(Boolean)
    .sort((a,b) => b.length - a.length)
    .map(kw => esc(kw).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  if(!parts.length) return escapedText;
  const re = new RegExp(parts.join('|'), 'gi');
  return escapedText.split(/(&[a-z]+;|&#\d+;)/gi).map((seg,i) =>
    i % 2 === 1 ? seg : seg.replace(re, m => '<mark>'+m+'</mark>')
  ).join('');
}

function matchField(field, keyword){
  return field.toLowerCase().includes(keyword);
}

function recordMatches(rec, keywords){
  for(const kw of keywords){
    let hit = matchField(rec.code, kw)
      || matchField(rec.upTae, kw)
      || matchField(rec.jung, kw)
      || matchField(rec.se, kw)
      || matchField(rec.sese, kw)
      || matchField(rec.gijun, kw);
    if(!hit){
      for(const k of rec.ksic){
        if(matchField(k.code, kw) || matchField(k.name, kw) || matchField(k.note, kw)){ hit = true; break; }
      }
    }
    if(!hit) return false;
  }
  return true;
}

function renderKsic(list, keywords){
  if(!list.length) return '';
  const chips = list.map(k => {
    const cls = k.main ? 'ksic-chip main' : 'ksic-chip';
    let text = highlight(esc(k.code), keywords) + ' ' + highlight(esc(k.name), keywords);
    if(k.note){
      text += ' <span class="ksic-note">— ' + highlight(esc(k.note), keywords) + '</span>';
    }
    return `<span class="${cls}">${text}</span>`;
  }).join('');
  return `<div class="ksic-wrap"><span class="ksic-label">연계 표준산업분류(11차)</span>${chips}</div>`;
}

function renderCard(rec, keywords){
  const gijunEsc = highlight(esc(rec.gijun), keywords);
  const lineCount = (rec.gijun.match(/\n/g) || []).length + 1;
  const needsToggle = lineCount > 6 || rec.gijun.length > 260;
  const gijunId = 'g' + rec.code;
  const ratesHtml = rec.r1 ? `
        <span class="rate">단순(일반) <b>${esc(rec.r1)}</b></span>
        <span class="rate">단순(초과) <b>${esc(rec.r2)}</b></span>
        <span class="rate">기준 <b>${esc(rec.r3)}</b></span>` : `
        <span class="rate">기준경비율 미고시</span>`;
  const gijunHtml = rec.gijun ? `
    <div class="gijun" id="${gijunId}">${gijunEsc}</div>
    ${needsToggle ? `<span class="more-toggle" data-target="${gijunId}">더보기</span>` : ''}` : '';
  return `
  <div class="card">
    <div class="card-head">
      <div class="code-title">
        <span class="code">${highlight(esc(rec.code), keywords)}</span>
        <span class="sese">${highlight(esc(rec.sese), keywords)}</span>
      </div>
      <div class="rates">${ratesHtml}
      </div>
    </div>
    <div class="path">${highlight(esc(rec.upTae), keywords)} › ${highlight(esc(rec.jung), keywords)} › ${highlight(esc(rec.se), keywords)}</div>
    ${gijunHtml}
    ${renderKsic(rec.ksic, keywords)}
  </div>`;
}

const searchBox = document.getElementById('searchBox');
const resultsEl = document.getElementById('results');
const countEl = document.getElementById('result-count');
let debounceTimer = null;

function runSearch(){
  const raw = searchBox.value.trim();
  if(!raw){
    resultsEl.innerHTML = '<div id="empty-hint">검색어를 입력하세요.</div>';
    countEl.textContent = '';
    return;
  }
  const keywords = raw.toLowerCase().split(/\s+/).filter(Boolean);
  const all = DATA.filter(rec => recordMatches(rec, keywords));
  const total = all.length;
  const shown = all.slice(0, MAX_RESULTS);
  countEl.textContent = total + '건';
  if(total === 0){
    resultsEl.innerHTML = '<div id="empty-hint">검색 결과가 없습니다.</div>';
    return;
  }
  resultsEl.innerHTML = shown.map(rec => renderCard(rec, keywords)).join('')
    + (total > MAX_RESULTS ? `<div id="empty-hint">${total}건 중 ${MAX_RESULTS}건 표시, 키워드를 더 입력하세요</div>` : '');
}

resultsEl.addEventListener('click', (e) => {
  const t = e.target;
  if(t.classList.contains('more-toggle')){
    const target = document.getElementById(t.dataset.target);
    target.classList.toggle('expanded');
    t.textContent = target.classList.contains('expanded') ? '접기' : '더보기';
  }
});

searchBox.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSearch, 150);
});

runSearch();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
