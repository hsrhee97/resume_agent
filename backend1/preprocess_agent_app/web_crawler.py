"""
web_crawler.py — 채용공고 크롤링 + 회사 리서치
"""
import time
from urllib.parse import urlparse, quote
import requests
from bs4 import BeautifulSoup
from config import SETTINGS

_H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


class JobPostingCrawler:
    def __init__(self):
        self.s = requests.Session(); self.s.headers.update(_H)
        self.timeout = SETTINGS["request_timeout"]

    def crawl(self, url):
        site = self._site(url); print(f"  사이트 감지: {site}")
        try:
            return {"wanted": self._wanted, "jobkorea": self._jobkorea,
                    "saramin": self._saramin}.get(site, self._generic)(url)
        except Exception as e:
            print(f"  ❌ 크롤링 실패: {e}")
            return {"site": site, "raw_text": "", "parsed": {}}

    @staticmethod
    def _site(url):
        d = urlparse(url).netloc.lower()
        for k in ["wanted","jobkorea","saramin"]:
            if k in d: return k
        return "generic"

    def _soup(self, url):
        try:
            r = self.s.get(url, timeout=self.timeout); r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e: print(f"  ❌ HTTP: {str(e)[:80]}"); return None

    def _clean(self, soup):
        for t in soup(["script","style","nav","footer","header","aside","noscript"]): t.decompose()
        return "\n".join(l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip())

    def _wanted(self, url):
        print(f"  🔍 원티드: {url}")
        soup = self._soup(url)
        if not soup: return {"site":"wanted","raw_text":"","parsed":{}}
        p = {"company":"","title":"","sections":[]}
        for s in ["[class*='CompanyName']","a[href*='/company/']","header h6"]:
            el = soup.select_one(s)
            if el: p["company"] = el.get_text(strip=True); break
        for s in ["[class*='JobHeader'] h1","h1","[class*='job_title']"]:
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
        print(f"  → 회사: {p['company']}, 포지션: {p['title']}")
        print(f"  → 텍스트: {len(raw)}자, 섹션: {len(p['sections'])}개")
        return {"site":"wanted","raw_text":raw,"parsed":p}

    def _jobkorea(self, url):
        soup = self._soup(url)
        if not soup: return {"site":"jobkorea","raw_text":"","parsed":{}}
        p = {"company":"","title":"","sections":[]}
        t = soup.select_one("h1, .title"); 
        if t: p["title"] = t.get_text(strip=True)
        for dt in soup.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd: p["sections"].append({"header":dt.get_text(strip=True),"content":dd.get_text("\n",strip=True)})
        body = soup.select_one(".tbRow, .artReadCont, #container, main")
        return {"site":"jobkorea","raw_text":self._clean(body or soup),"parsed":p}

    def _saramin(self, url):
        soup = self._soup(url)
        if not soup: return {"site":"saramin","raw_text":"","parsed":{}}
        p = {"company":"","title":"","sections":[]}
        t = soup.select_one("h1, .job_tit"); 
        if t: p["title"] = t.get_text(strip=True)
        c = soup.select_one(".company_name a, [class*='company']")
        if c: p["company"] = c.get_text(strip=True)
        return {"site":"saramin","raw_text":self._clean(soup),"parsed":p}

    def _generic(self, url):
        soup = self._soup(url)
        if not soup: return {"site":"generic","raw_text":"","parsed":{}}
        p = {"company":"","title":"","sections":[]}
        t = soup.select_one("h1, title")
        if t: p["title"] = t.get_text(strip=True)
        return {"site":"generic","raw_text":self._clean(soup),"parsed":p}


class CompanyResearcher:
    def __init__(self): self.timeout = SETTINGS["request_timeout"]

    def research(self, company_name, position=""):
        results = {"naver_results": [], "company_site": {}}
        queries = [
            f"{company_name} 기업 소개 비전",
            f"{company_name} {position} 채용",
            f"{company_name} 최근 뉴스 2025",
            f"{company_name} 기업문화 개발자",
        ]
        for q in queries:
            sn = self._google(q) or self._naver(q)
            results["naver_results"].extend(sn)
            time.sleep(0.5)
        print(f"  📊 리서치: 스니펫 {len(results['naver_results'])}개")
        return results

    def _google(self, q):
        try:
            r = requests.get(f"https://www.google.com/search?q={quote(q)}&hl=ko", headers=_H, timeout=self.timeout)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser"); out = []
            for d in soup.select("div.BNeawe, div[data-sncf], div.VwiC3b, span.aCOpRe"):
                t = d.get_text(strip=True)
                if len(t) > 30: out.append({"query":q,"text":t[:500]})
                if len(out) >= 3: break
            return out
        except: return []

    def _naver(self, q):
        try:
            r = requests.get(f"https://search.naver.com/search.naver?query={quote(q)}",
                             headers={**_H, "Referer":"https://www.naver.com/"}, timeout=self.timeout)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser"); out = []
            for sel in [".total_dsc_wrap",".api_txt_lines",".dsc_txt",".news_dsc"]:
                for el in soup.select(sel)[:3]:
                    t = el.get_text(strip=True)
                    if len(t) > 20: out.append({"query":q,"text":t[:500]})
            return out
        except: return []


def format_research_for_llm(research):
    parts = []
    for item in research.get("naver_results", []):
        parts.append(f"[{item['query']}] {item['text']}")
    return "\n\n".join(parts) if parts else "검색 결과 없음"