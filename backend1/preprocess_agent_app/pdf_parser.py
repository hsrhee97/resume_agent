"""
pdf_parser.py — PDF/TXT 텍스트 추출 + 청킹

⚠️ 한글/워드에서 폰트를 '곡선 변환'하여 PDF 저장 시
   텍스트 레이어가 없어 모든 라이브러리에서 0자.
   → 같은 폴더에 자소서1.txt를 두면 자동으로 그걸 읽음
"""
import os
from config import SETTINGS


def extract_text_from_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"파일 없음: {pdf_path}")

    # .txt면 바로 읽기
    if pdf_path.lower().endswith(".txt"):
        return _read_txt(pdf_path)

    # 같은 이름 .txt 있으면 우선 사용
    txt = os.path.splitext(pdf_path)[0] + ".txt"
    if os.path.exists(txt):
        print(f"  📄 {os.path.basename(txt)} 발견 → 텍스트 파일 사용")
        return _read_txt(txt)

    # PDF 추출 시도 (텍스트 레이어)
    for fn in [_try_pdfplumber, _try_pymupdf, _try_pypdf2]:
        try:
            r = fn(pdf_path)
            if r and r.strip(): return r
        except ImportError: pass
        except Exception as e: print(f"  ⚠️ {fn.__name__}: {str(e)[:50]}")

    # 텍스트 레이어 없음 → OCR 시도
    print("  ⚠️ 텍스트 레이어 없음 → OCR 추출 시도...")
    ocr_text = _try_ocr(pdf_path)
    if ocr_text and ocr_text.strip():
        return ocr_text

    print("  ❌ PDF 텍스트 추출 실패 (0자)")
    print("  ┌──────────────────────────────────────────┐")
    print("  │ OCR도 실패했습니다. 설치 확인:           │")
    print("  │   brew install tesseract poppler         │")
    print("  │   pip install pytesseract pdf2image      │")
    print("  │                                          │")
    print("  │ 또는 PDF → 텍스트 복사 → .txt 저장      │")
    print("  └──────────────────────────────────────────┘")
    return ""


def _read_txt(path: str) -> str:
    for enc in ["utf-8", "cp949", "euc-kr", "utf-16"]:
        try:
            with open(path, encoding=enc) as f: text = f.read()
            if text.strip():
                print(f"  (텍스트) {len(text)}자 ({enc})")
                return text
        except (UnicodeDecodeError, UnicodeError): continue
    return ""


def _try_pdfplumber(path):
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(pdf.pages):
            t = p.extract_text()
            if t and t.strip(): parts.append(f"--- Page {i+1} ---\n{t}"); continue
            w = p.extract_words()
            if w:
                wt = " ".join(x.get("text","") for x in w)
                if wt.strip(): parts.append(f"--- Page {i+1} ---\n{wt}")
    r = "\n\n".join(parts)
    print(f"  (pdfplumber) {len(r)}자, {len(parts)}페이지")
    return r


def _try_pymupdf(path):
    import fitz
    parts = []
    for i, p in enumerate(fitz.open(path)):
        t = p.get_text()
        if t.strip(): parts.append(f"--- Page {i+1} ---\n{t}")
    r = "\n\n".join(parts)
    print(f"  (PyMuPDF) {len(r)}자")
    return r


def _try_pypdf2(path):
    from PyPDF2 import PdfReader
    parts = []
    for i, p in enumerate(PdfReader(path).pages):
        t = p.extract_text()
        if t and t.strip(): parts.append(f"--- Page {i+1} ---\n{t}")
    r = "\n\n".join(parts)
    print(f"  (PyPDF2) {len(r)}자")
    return r


def _try_ocr(pdf_path: str) -> str:
    """OCR로 이미지/벡터 PDF에서 텍스트 추출 (tesseract + poppler 필요)"""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print("  ❌ OCR 패키지 미설치:")
        print("     brew install tesseract poppler")
        print("     pip install pytesseract pdf2image")
        return ""

    try:
        print("  🔄 PDF → 이미지 변환 중...")
        images = convert_from_path(pdf_path, dpi=300)
        print(f"  📸 {len(images)}페이지 변환 완료. OCR 처리 중...")

        text_parts = []
        for i, img in enumerate(images):
            # 한국어+영어 OCR
            text = pytesseract.image_to_string(img, lang="kor+eng")
            if text and text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{text.strip()}")
                print(f"  ✅ Page {i+1}: {len(text.strip())}자")
            else:
                # 영어만으로 재시도
                text = pytesseract.image_to_string(img, lang="eng")
                if text and text.strip():
                    text_parts.append(f"--- Page {i + 1} ---\n{text.strip()}")
                    print(f"  ✅ Page {i+1}: {len(text.strip())}자 (eng)")
                else:
                    print(f"  ⚠️ Page {i+1}: 추출 실패")

        result = "\n\n".join(text_parts)
        if result.strip():
            print(f"  ✅ OCR 완료: 총 {len(result)}자")
        return result

    except Exception as e:
        print(f"  ❌ OCR 실패: {str(e)[:80]}")
        if "tesseract" in str(e).lower():
            print("     → brew install tesseract")
        if "poppler" in str(e).lower() or "pdftoppm" in str(e).lower():
            print("     → brew install poppler")
        return ""


def chunk_text(text: str, max_chars=None, overlap_chars=None) -> list[str]:
    max_chars = max_chars or SETTINGS.get("chunk_max_chars", 3000)
    overlap_chars = overlap_chars or SETTINGS.get("chunk_overlap_chars", 200)
    if len(text) <= max_chars: return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            pb = text.rfind("--- Page", start, end)
            if pb > start + max_chars // 2: end = pb
            elif (pp := text.rfind("\n\n", start + max_chars // 2, end)) > 0: end = pp
            elif (sp := text.rfind(". ", start + max_chars // 2, end)) > 0: end = sp + 1
        c = text[start:end].strip()
        if c: chunks.append(c)
        start = end - overlap_chars
        if start >= len(text): break
    return chunks
    