"""
web_crawler.py — 채용공고 크롤링 + 회사 리서치
"""
import base64
import io
import os
import re
import time
from urllib.parse import quote, urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from config import SETTINGS

_H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

_IMAGE_HINT_KEYWORDS = (
    "jd",
    "job",
    "recruit",
    "position",
    "desc",
    "detail",
    "content",
    "posting",
    "공고",
    "채용",
    "모집",
)
_IMAGE_EXCLUDE_KEYWORDS = (
    "logo",
    "icon",
    "sprite",
    "avatar",
    "banner",
    "thumb",
    "thumbnail",
    "favicon",
    "profile",
)


class JobPostingCrawler:
    def __init__(self):
        self.s = requests.Session(); self.s.headers.update(_H)
        self.timeout = SETTINGS["request_timeout"]
        self.min_text_chars = int(SETTINGS.get("job_posting_min_text_chars", 800))
        self.max_image_count = int(SETTINGS.get("job_posting_image_max_count", 6))
        self.max_image_bytes = int(SETTINGS.get("job_posting_image_max_bytes", 8_000_000))

    def crawl(self, url):
        site = self._site(url); print(f"  사이트 감지: {site}")
        try:
            base_result = {"wanted": self._wanted, "jobkorea": self._jobkorea,
                           "saramin": self._saramin}.get(site, self._generic)(url)
            return self._apply_image_fallback(url, base_result)
        except Exception as e:
            print(f"  [ERROR] 크롤링 실패: {e}")
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
        except Exception as e: print(f"  [ERROR] HTTP: {str(e)[:80]}"); return None

    def _clean(self, soup):
        for t in soup(["script","style","nav","footer","header","aside","noscript"]): t.decompose()
        return "\n".join(l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip())

    def _apply_image_fallback(self, url, result):
        if not isinstance(result, dict):
            return {"site": self._site(url), "raw_text": "", "parsed": {}}

        raw_text = str(result.get("raw_text") or "").strip()
        parsed = result.get("parsed")
        parsed_dict = parsed if isinstance(parsed, dict) else {}

        if not self._needs_image_fallback(raw_text, parsed_dict):
            return result

        print("  [INFO] 텍스트 추출이 부족하여 이미지 OCR fallback 시도")
        soup = self._soup(url)
        if not soup:
            print("  [WARN] fallback 중 페이지 재요청 실패")
            return result

        image_urls = self._collect_candidate_image_urls(url, soup, limit=self.max_image_count)
        if not image_urls:
            print("  [WARN] OCR 대상 이미지를 찾지 못해 fallback 종료")
            return result

        image_payloads = self._download_image_payloads(image_urls, referer=url)
        if not image_payloads:
            print("  [WARN] OCR 대상 이미지를 다운로드하지 못해 fallback 종료")
            return result

        ocr_text = self._extract_text_from_images(image_payloads)
        if not ocr_text.strip():
            print("  [WARN] 이미지 OCR 결과가 비어 있어 기존 텍스트 사용")
            return result

        merged = f"{raw_text}\n\n[이미지 OCR 보강]\n{ocr_text}".strip() if raw_text else ocr_text
        parsed_dict["image_ocr_used"] = True
        parsed_dict["image_ocr_image_count"] = len(image_payloads)
        parsed_dict["image_ocr_chars"] = len(ocr_text)
        parsed_dict["image_ocr_urls"] = [item.get("url", "") for item in image_payloads]
        result["parsed"] = parsed_dict
        result["raw_text"] = merged
        print(f"  [OK] 이미지 OCR 보강 완료: {len(ocr_text)}자 / {len(image_payloads)}개 이미지")
        return result

    def _needs_image_fallback(self, raw_text, parsed):
        text_len = len((raw_text or "").strip())
        if text_len < self.min_text_chars:
            return True
        title = str(parsed.get("title") or "").strip() if isinstance(parsed, dict) else ""
        sections = parsed.get("sections") if isinstance(parsed, dict) else []
        if not title and not sections:
            return True
        return False

    def _collect_candidate_image_urls(self, page_url, soup, limit=6):
        scored = []

        def add_candidate(src, marker=""):
            normalized = self._normalize_image_url(page_url, src)
            if not normalized:
                return
            score = self._score_image_candidate(normalized, marker)
            if score <= 0:
                return
            scored.append((score, normalized))

        for img in soup.select("img"):
            marker = " ".join(
                filter(
                    None,
                    [
                        img.get("class", "") if isinstance(img.get("class"), str) else " ".join(img.get("class", [])),
                        img.get("id", ""),
                        img.get("alt", ""),
                        img.get("src", ""),
                        img.get("data-src", ""),
                        img.get("data-original", ""),
                        img.get("data-lazy", ""),
                    ],
                )
            )
            add_candidate(img.get("src"), marker=marker)
            add_candidate(img.get("data-src"), marker=marker)
            add_candidate(img.get("data-original"), marker=marker)
            add_candidate(img.get("data-lazy"), marker=marker)

        for source in soup.select("source[srcset]"):
            srcset = source.get("srcset") or ""
            for chunk in srcset.split(","):
                add_candidate(chunk.strip().split(" ")[0], marker=srcset)

        for el in soup.select("[style*='background-image']"):
            style = el.get("style") or ""
            for _, src in re.findall(r"url\((['\"]?)(.*?)\1\)", style):
                add_candidate(src, marker=style)

        seen = set()
        ranked = []
        for score, link in sorted(scored, key=lambda item: item[0], reverse=True):
            if link in seen:
                continue
            seen.add(link)
            ranked.append(link)
            if len(ranked) >= limit:
                break
        return ranked

    def _normalize_image_url(self, page_url, src):
        raw = str(src or "").strip().strip("'\"")
        if not raw or raw.startswith("data:"):
            return ""
        if raw.startswith("//"):
            return "https:" + raw
        return urljoin(page_url, raw)

    def _score_image_candidate(self, image_url, marker=""):
        haystack = f"{image_url} {marker}".lower()
        if any(token in haystack for token in _IMAGE_EXCLUDE_KEYWORDS):
            return -2
        score = 1 if re.search(r"\.(png|jpg|jpeg|webp|bmp|gif)(\?|$)", image_url.lower()) else 0
        if any(token in haystack for token in _IMAGE_HINT_KEYWORDS):
            score += 3
        if "recruit" in haystack or "job" in haystack:
            score += 2
        return score

    def _download_image_payloads(self, image_urls, referer=""):
        payloads = []
        for image_url in image_urls:
            try:
                headers = dict(_H)
                if referer:
                    headers["Referer"] = referer
                response = self.s.get(image_url, timeout=self.timeout, headers=headers)
                if response.status_code != 200:
                    continue
                content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if content_type and not content_type.startswith("image/"):
                    continue
                content = response.content or b""
                if len(content) < 1_024:
                    continue
                if len(content) > self.max_image_bytes:
                    continue
                payloads.append(
                    {
                        "url": image_url,
                        "content_type": content_type or "image/jpeg",
                        "content": content,
                    }
                )
                if len(payloads) >= self.max_image_count:
                    break
            except Exception:
                continue
        return payloads

    def _extract_text_from_images(self, image_payloads):
        text = self._ocr_via_tesseract(image_payloads)
        if text.strip():
            return text
        return self._ocr_via_openai_vision(image_payloads)

    def extract_text_from_images(self, image_payloads):
        """Public wrapper for OCR text extraction from image payload list."""
        return self._extract_text_from_images(image_payloads)

    @staticmethod
    def _normalize_llm_content(content):
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            out = []
            for item in content:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        out.append(text)
            return "\n".join(part.strip() for part in out if part and part.strip()).strip()
        return str(content or "").strip()

    def _ocr_via_tesseract(self, image_payloads):
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ""

        extracted = []
        lang = os.getenv("OCR_LANG", "kor+eng")
        for idx, payload in enumerate(image_payloads, start=1):
            try:
                image = Image.open(io.BytesIO(payload["content"]))
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                text = pytesseract.image_to_string(image, lang=lang).strip()
                if len(text) < 20:
                    text = pytesseract.image_to_string(image, lang="eng").strip()
                if len(text) < 20:
                    continue
                extracted.append(f"[Image {idx}] {text}")
            except Exception:
                continue

        if extracted:
            print(f"  [OCR] tesseract 기반 추출: {len(extracted)}개 이미지")
        return "\n\n".join(extracted)

    def _ocr_via_openai_vision(self, image_payloads):
        if not os.getenv("OPENAI_API_KEY"):
            return ""

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except Exception:
            return ""

        model = os.getenv("BACKEND1_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        llm = ChatOpenAI(model=model, temperature=0)
        extracted = []

        for idx, payload in enumerate(image_payloads[:4], start=1):
            try:
                encoded = base64.b64encode(payload["content"]).decode("ascii")
                data_url = f"data:{payload['content_type']};base64,{encoded}"
                response = llm.invoke(
                    [
                        SystemMessage(
                            content=(
                                "너는 한국 채용공고 OCR 보조기다. "
                                "이미지에 있는 텍스트를 가능한 원문에 가깝게 추출하라. "
                                "설명 없이 추출 텍스트만 출력하라."
                            )
                        ),
                        HumanMessage(
                            content=[
                                {"type": "text", "text": "이미지 내 채용공고 텍스트를 추출해줘."},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ]
                        ),
                    ]
                )
                text = self._normalize_llm_content(getattr(response, "content", ""))
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if len(text) < 20:
                    continue
                extracted.append(f"[Image {idx}] {text}")
            except Exception:
                continue

        if extracted:
            print(f"  [Vision] OpenAI 기반 추출: {len(extracted)}개 이미지")
        return "\n\n".join(extracted)

    def _wanted(self, url):
        print(f"  [INFO] 원티드: {url}")
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
        print(f"  [INFO] 회사: {p['company']}, 포지션: {p['title']}")
        print(f"  [INFO] 텍스트: {len(raw)}자, 섹션: {len(p['sections'])}개")
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
        print(f"  [INFO] 리서치: 스니펫 {len(results['naver_results'])}개")
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
