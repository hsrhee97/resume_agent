"""
web_crawler.py — 채용공고 크롤링 + 회사 리서치

잡코리아 대응:
  1) Selenium 헤드리스 → 메인 페이지 (요약정보/스킬/우대)
  2) iframe 감지 → GI_Read_Comt_Ifrm 별도 로드 (상세요강 테이블)
  3) raw_text 줄 기반 키-값 파싱
  4) 이미지 OCR (필요 시)
"""
import io
import re
import time
from urllib.parse import urlparse, urljoin, quote

import requests
from bs4 import BeautifulSoup

from config import SETTINGS

_H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ============================================================
# Selenium
# ============================================================
def _get_rendered_html(url, wait_seconds=3):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("  ⚠️ selenium 미설치: pip install selenium")
        return None
    try:
        opts = Options()
        opts.add_argument("--headless"); opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage"); opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument(f"user-agent={_H['User-Agent']}")
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        except ImportError:
            driver = webdriver.Chrome(options=opts)
        print(f"  🌐 Selenium: {url[:70]}...")
        driver.get(url)
        time.sleep(wait_seconds)
        html = driver.page_source
        driver.quit()
        print(f"  ✅ {len(html)}자 HTML")
        return html
    except Exception as e:
        print(f"  ⚠️ Selenium 실패: {str(e)[:80]}")
        try: driver.quit()
        except: pass
        return None


# ============================================================
# 이미지 OCR
# ============================================================
def _ocr_image_from_url(img_url, session=None):
    try:
        from PIL import Image; import pytesseract
    except ImportError: return ""
    try:
        r = (session or requests).get(img_url, timeout=15)
        if r.status_code != 200: return ""
        img = Image.open(io.BytesIO(r.content))
        if img.size[0] < 200 or img.size[1] < 200: return ""
        try: return pytesseract.image_to_string(img, lang="kor+eng").strip()
        except: return pytesseract.image_to_string(img, lang="eng").strip()
    except: return ""


def _ocr_images_in_soup(soup, base_url, session, container_selector=None):
    try: import pytesseract
    except ImportError: return ""
    container = soup
    if container_selector:
        for sel in container_selector.split(","):
            el = soup.select_one(sel.strip())
            if el: container = el; break
    skip = ["logo","icon","btn","button","banner","ad_","sprite","arrow",
            "facebook","twitter","kakao","naver_","google_","1x1","pixel","tracking"]
    texts = []
    for img in container.select("img"):
        src = img.get("src","") or img.get("data-src","")
        if not src: continue
        if src.startswith("//"): src = "https:" + src
        elif src.startswith("/"): src = urljoin(base_url, src)
        elif not src.startswith("http"): src = urljoin(base_url, src)
        if any(k in src.lower() for k in skip): continue
        print(f"  🖼️ OCR: {src[:80]}...")
        t = _ocr_image_from_url(src, session)
        if t and len(t) > 30: texts.append(t); print(f"     ✅ {len(t)}자")
        else: print(f"     ⏭️ {len(t) if t else 0}자")
    return "\n\n".join(texts)


# ============================================================
# 잡코리아 파서
# ============================================================
def _extract_jobkorea_structured(soup, raw_text):
    info = {
        "company": "", "title": "",
        "employment_type": "", "salary": "", "location": "",
        "career": "", "education": "",
        "skills": [], "preferred": [], "sections": [], "company_info": {},
    }

    # 회사명
    for sel in [".coName a", ".coName", "a.name"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            info["company"] = el.get_text(strip=True); break

    # 제목
    for sel in [".sumTit h2", ".artReadTtl", "h3.hd_3"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            info["title"] = el.get_text(strip=True); break
    if not info["title"]:
        t = soup.select_one("title")
        if t:
            tt = t.get_text(strip=True)
            if " - " in tt: info["title"] = tt.split(" - ", 1)[1].split("|")[0].strip()

    # dt/dd 파싱
    for dt in soup.select("dt"):
        key = dt.get_text(strip=True)
        if not key or len(key) > 30: continue
        dd = dt.find_next_sibling("dd")
        if not dd: continue
        val = dd.get_text(" ", strip=True)
        if not val: continue
        field_map = {"고용형태": "employment_type", "급여": "salary",
                     "근무지주소": "location", "근무지": "location",
                     "경력": "career", "학력": "education"}
        if key in field_map:
            info[field_map[key]] = val
        co_map = {"산업": "industry", "산업(업종)": "industry", "사원수": "employees",
                  "설립년도": "founded", "설립": "founded", "기업형태": "company_type",
                  "매출액": "revenue", "홈페이지": "homepage"}
        if key in co_map:
            info["company_info"][co_map[key]] = val

    # raw_text 줄 기반 fallback
    lines = raw_text.split("\n")
    LINE_KEYS = {"고용형태": "employment_type", "급여": "salary",
                 "근무지주소": "location", "경력": "career", "학력": "education"}
    STOP = set(LINE_KEYS) | {"스킬","우대조건","기본우대","인근지하철",
                              "지도보기","지원자격","모집요강","모집분야"}
    for i, line in enumerate(lines):
        s = line.strip()
        if s in LINE_KEYS and not info.get(LINE_KEYS[s]) and i + 1 < len(lines):
            parts = []
            for j in range(i+1, min(i+4, len(lines))):
                nl = lines[j].strip()
                if nl in STOP: break
                if nl and nl not in ("(",")"): parts.append(nl)
            if parts: info[LINE_KEYS[s]] = " ".join(parts)

        if s in ("기본우대","우대조건") and not info["preferred"] and i+1 < len(lines):
            for j in range(i+1, min(i+3, len(lines))):
                nl = lines[j].strip()
                if nl and len(nl) > 10:
                    info["preferred"] = [x.strip() for x in nl.split(",") if x.strip()]
                    break

    # sections 생성
    existing = set()
    for h, v in [("경력", info["career"]), ("학력", info["education"]),
                  ("고용형태", info["employment_type"]), ("급여", info["salary"]),
                  ("근무지", info["location"]),
                  ("스킬", ", ".join(info["skills"]) if info["skills"] else ""),
                  ("우대사항", ", ".join(info["preferred"]) if info["preferred"] else "")]:
        if v and h not in existing:
            info["sections"].append({"header": h, "content": v})
            existing.add(h)
    for k, v in info["company_info"].items():
        if v and k not in existing:
            info["sections"].append({"header": k, "content": v})
            existing.add(k)

    return info


def _parse_iframe_table(soup):
    """iframe 내 상세요강 테이블 파싱 → sections 리스트"""
    sections = []
    for table in soup.select("table"):
        rows = table.select("tr")
        # 헤더 행 확인
        header_cells = []
        for tr in rows:
            ths = tr.select("th")
            if ths:
                header_cells = [th.get_text(strip=True) for th in ths]
                continue
            tds = tr.select("td")
            if not tds: continue
            cell_texts = [td.get_text("\n", strip=True) for td in tds]
            if len(cell_texts) >= 2 and len(cell_texts[0]) > 3:
                sections.append({
                    "header": cell_texts[0][:80],
                    "content": " | ".join(cell_texts[1:])
                })
    return sections


# ============================================================
# 크롤러
# ============================================================
class JobPostingCrawler:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(_H)
        self.timeout = SETTINGS["request_timeout"]

    def crawl(self, url):
        site = self._site(url)
        print(f"  사이트 감지: {site}")
        try:
            return {"wanted": self._wanted, "jobkorea": self._jobkorea,
                    "saramin": self._saramin}.get(site, self._generic)(url)
        except Exception as e:
            print(f"  ❌ 크롤링 실패: {e}"); return {"site": site, "raw_text": "", "parsed": {}}

    @staticmethod
    def _site(url):
        d = urlparse(url).netloc.lower()
        for k in ["wanted", "jobkorea", "saramin"]:
            if k in d: return k
        return "generic"

    def _soup(self, url):
        try:
            r = self.s.get(url, timeout=self.timeout)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"  ❌ HTTP: {str(e)[:80]}"); return None

    def _soup_rendered(self, url, wait=3):
        html = _get_rendered_html(url, wait_seconds=wait)
        if html: return BeautifulSoup(html, "html.parser")
        print("  ↩️ requests fallback...")
        return self._soup(url)

    def _clean(self, soup):
        for t in soup(["script","style","nav","footer","header","aside","noscript"]):
            t.decompose()
        return "\n".join(l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip())

    # ---- 잡코리아 ----
    def _jobkorea(self, url):
        print(f"  🔍 잡코리아: {url}")

        # ① 메인 페이지 (Selenium)
        soup = self._soup_rendered(url, wait=4)
        if not soup:
            return {"site": "jobkorea", "raw_text": "", "parsed": {}}

        # 본문 텍스트
        raw_text = self._clean(soup)

        # ② iframe 감지 → 상세요강 별도 로드
        iframe_sections = []
        iframe_text = ""
        for iframe in soup.select("iframe"):
            src = iframe.get("src", "")
            if "GI_Read_Comt_Ifrm" in src or "Comt_Ifrm" in src:
                iframe_url = src
                if iframe_url.startswith("/"):
                    iframe_url = "https://www.jobkorea.co.kr" + iframe_url
                print(f"  📋 iframe 상세요강 발견: {iframe_url[:80]}")

                iframe_html = _get_rendered_html(iframe_url, wait_seconds=3)
                if iframe_html:
                    iframe_soup = BeautifulSoup(iframe_html, "html.parser")
                    iframe_sections = _parse_iframe_table(iframe_soup)
                    iframe_text = iframe_soup.get_text("\n", strip=True)
                    print(f"  ✅ iframe: {len(iframe_sections)}개 직무, {len(iframe_text)}자")
                break

        # iframe 텍스트를 raw_text에 합침
        if iframe_text:
            raw_text = raw_text + "\n\n=== 상세요강 (모집분야/자격요건) ===\n" + iframe_text

        # 이미지 OCR (필요 시)
        if len(raw_text) < 300:
            ocr = _ocr_images_in_soup(soup, url, self.s,
                                       container_selector=".artReadCont, .viewInfo, #container")
            if ocr: raw_text += "\n\n=== 이미지 OCR ===\n" + ocr

        # 구조화 정보
        structured = _extract_jobkorea_structured(soup, raw_text)

        # iframe에서 가져온 직무별 sections 추가
        if iframe_sections:
            structured["sections"].extend(iframe_sections)

        # 요약정보를 raw_text 앞에
        summary = "\n".join(f"{s['header']}: {s['content'][:200]}" for s in structured["sections"])
        if summary:
            raw_text = "=== 요약정보 ===\n" + summary + "\n\n" + raw_text

        p = {
            "company": structured["company"],
            "title": structured["title"],
            "sections": structured["sections"],
            "company_info": structured["company_info"],
            "skills": structured["skills"],
            "preferred": structured["preferred"],
            "career": structured["career"],
            "education": structured["education"],
            "employment_type": structured["employment_type"],
            "salary": structured["salary"],
            "location": structured["location"],
        }

        print(f"  → 회사: {p['company']}, 포지션: {p['title']}")
        print(f"  → 텍스트: {len(raw_text)}자, 섹션: {len(p['sections'])}개")
        if iframe_sections:
            print(f"  → 직무: {[s['header'][:30] for s in iframe_sections[:3]]}...")
        return {"site": "jobkorea", "raw_text": raw_text, "parsed": p}

    # ---- 원티드 ----
    def _wanted(self, url):
        print(f"  🔍 원티드: {url}")
        soup = self._soup(url)
        if not soup: return {"site": "wanted", "raw_text": "", "parsed": {}}
        p = {"company": "", "title": "", "sections": []}
        for s in ["[class*='CompanyName']", "a[href*='/company/']", "header h6"]:
            el = soup.select_one(s)
            if el: p["company"] = el.get_text(strip=True); break
        for s in ["[class*='JobHeader'] h1", "h1", "[class*='job_title']"]:
            el = soup.select_one(s)
            if el: p["title"] = el.get_text(strip=True); break
        for h in soup.select("h6, h3"):
            ht = h.get_text(strip=True); parts = []; sib = h.find_next_sibling()
            while sib and sib.name not in ("h6","h3","h2"):
                t = sib.get_text("\n", strip=True)
                if t: parts.append(t)
                sib = sib.find_next_sibling()
            if parts: p["sections"].append({"header": ht, "content": "\n".join(parts)})
        main = soup.select_one("[class*='JobContent'], main, article, #__next")
        raw = self._clean(main or soup)
        print(f"  → {p['company']}, {p['title']}, {len(raw)}자")
        return {"site": "wanted", "raw_text": raw, "parsed": p}

    # ---- 사람인 ----
    def _saramin(self, url):
        soup = self._soup(url)
        if not soup: return {"site": "saramin", "raw_text": "", "parsed": {}}
        p = {"company": "", "title": "", "sections": []}
        t = soup.select_one("h1, .job_tit")
        if t: p["title"] = t.get_text(strip=True)
        c = soup.select_one(".company_name a, [class*='company']")
        if c: p["company"] = c.get_text(strip=True)
        raw = self._clean(soup)
        if len(raw) < 200:
            ocr = _ocr_images_in_soup(soup, url, self.s)
            if ocr: raw += "\n\n" + ocr
        return {"site": "saramin", "raw_text": raw, "parsed": p}

    # ---- 범용 ----
    def _generic(self, url):
        soup = self._soup(url)
        if not soup: return {"site": "generic", "raw_text": "", "parsed": {}}
        p = {"company": "", "title": "", "sections": []}
        t = soup.select_one("h1, title")
        if t: p["title"] = t.get_text(strip=True)
        return {"site": "generic", "raw_text": self._clean(soup), "parsed": p}


# ============================================================
# 회사 리서치
# ============================================================
class CompanyResearcher:
    def __init__(self): self.timeout = SETTINGS["request_timeout"]

    def research(self, company_name, position=""):
        results = {"naver_results": [], "company_site": {}}
        for q in [f"{company_name} 기업 소개 비전", f"{company_name} {position} 채용",
                   f"{company_name} 최근 뉴스 2025", f"{company_name} 기업문화"]:
            results["naver_results"].extend(self._google(q) or self._naver(q))
            time.sleep(0.5)
        print(f"  📊 리서치: {len(results['naver_results'])}개")
        return results

    def _google(self, q):
        try:
            r = requests.get(f"https://www.google.com/search?q={quote(q)}&hl=ko",
                             headers=_H, timeout=self.timeout)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser"); out = []
            for d in soup.select("div.BNeawe, div.VwiC3b, span.aCOpRe"):
                t = d.get_text(strip=True)
                if len(t) > 30: out.append({"query": q, "text": t[:500]})
                if len(out) >= 3: break
            return out
        except: return []

    def _naver(self, q):
        try:
            r = requests.get(f"https://search.naver.com/search.naver?query={quote(q)}",
                             headers={**_H, "Referer": "https://www.naver.com/"}, timeout=self.timeout)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser"); out = []
            for sel in [".total_dsc_wrap", ".api_txt_lines", ".dsc_txt"]:
                for el in soup.select(sel)[:3]:
                    t = el.get_text(strip=True)
                    if len(t) > 20: out.append({"query": q, "text": t[:500]})
            return out
        except: return []


def format_research_for_llm(research):
    parts = [f"[{item['query']}] {item['text']}" for item in research.get("naver_results", [])]
    return "\n\n".join(parts) if parts else "검색 결과 없음"