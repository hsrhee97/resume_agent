"""
llm_client.py — OpenAI / HuggingFace Inference Providers / Ollama

⚠️ 2025년 7월부터 HF 무료 API는 text_generation 엔드포인트를 폐지.
   chat_completion만 사용 가능.
   https://huggingface.co/docs/inference-providers/en/tasks/text-generation
"""
import json, os, re, time
from abc import ABC, abstractmethod

try:
    from huggingface_hub import InferenceClient
except ImportError:  # pragma: no cover - optional runtime dependency
    InferenceClient = None


class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 4000) -> str: ...

    def generate_json(self, prompt: str, max_tokens: int = 4000) -> dict | None:
        raw = self.generate(prompt, max_tokens=max_tokens)
        return self._parse_json(raw) if raw else None

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        if not text: return None
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m: text = m.group(1)
        start = next((i for i, c in enumerate(text) if c in "{["), -1)
        if start == -1: return None
        text = text[start:]
        depth, end = 0, len(text)
        for i, c in enumerate(text):
            if c in "{[": depth += 1
            elif c in "}]": depth -= 1
            if depth == 0 and i > 0: end = i + 1; break
        text = text[:end]
        try: return json.loads(text)
        except:
            text = re.sub(r",\s*([}\]])", r"\1", text)
            try: return json.loads(text)
            except: print("  [WARN] JSON 파싱 실패"); return None


def _to_text_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return str(content or "").strip()


class OpenAILLM(BaseLLM):
    """OpenAI ChatCompletion 기반 LLM"""

    def __init__(self, model: str = "gpt-4.1-mini", temperature: float = 0.3):
        self.model = (model or "gpt-4.1-mini").strip()
        self.temperature = float(temperature)
        self.client = None

        if not os.getenv("OPENAI_API_KEY"):
            print("=" * 60)
            print("[WARN] OPENAI_API_KEY 필요")
            print("  .env 또는 환경변수에 OPENAI_API_KEY를 설정하세요.")
            print("=" * 60)
            return

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI

            self._human_cls = HumanMessage
            self._system_cls = SystemMessage
            self.client = ChatOpenAI(model=self.model, temperature=self.temperature)
        except Exception as e:
            print(f"  [ERROR] OpenAI 초기화 실패: {str(e)[:120]}")
            self.client = None

    def generate(self, prompt: str, max_tokens: int = 4000) -> str:
        if not self.client:
            return ""

        try:
            response = self.client.invoke(
                [
                    self._system_cls(
                        content=(
                            "당신은 한국어 데이터 추출 전문가입니다. "
                            "반드시 유효한 JSON만 반환하세요. "
                            "설명, 마크다운, 추가 텍스트 없이 JSON만 출력하세요."
                        )
                    ),
                    self._human_cls(content=prompt),
                ]
            )
            return _to_text_content(getattr(response, "content", ""))
        except Exception as e:
            print(f"  [ERROR] OpenAI 호출 실패: {str(e)[:120]}")
            return ""


class HuggingFaceLLM(BaseLLM):
    """
    HuggingFace Inference Providers — chat_completion 전용

    2025.07 이후 text_generation 폐지 → chat_completion만 사용
    """

    DEFAULT_TOKEN = "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"  # 🔑 여기에 토큰 직접 입력 가능

    # chat_completion을 지원하는 모델 목록
    # https://huggingface.co/docs/inference-providers/en/tasks/text-generation
    CANDIDATE_MODELS = [
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "Qwen/Qwen2.5-7B-Instruct",
        "microsoft/Phi-3-mini-4k-instruct",
        "HuggingFaceH4/zephyr-7b-beta",
        "google/gemma-2-2b-it",
        "tiiuae/falcon-7b-instruct",
    ]

    def __init__(self, api_token: str = None, model_id: str = None):
        self.api_token = api_token or os.getenv("HF_TOKEN", "") or self._load_token()
        self.model_id = model_id
        self.client = None

        if InferenceClient is None:
            print("  [ERROR] huggingface_hub 미설치로 HuggingFace 백엔드를 사용할 수 없습니다.")
            return

        if not self.api_token:
            print("=" * 60)
            print("[WARN] HF_TOKEN 필요")
            print("  export HF_TOKEN='hf_...'")
            print("  또는 llm_client.py DEFAULT_TOKEN에 직접 입력")
            print("  토큰: https://huggingface.co/settings/tokens")
            print("=" * 60)
            return

        self.client = InferenceClient(token=self.api_token)
        self._select_model(model_id)

    @classmethod
    def _load_token(cls) -> str:
        if cls.DEFAULT_TOKEN: return cls.DEFAULT_TOKEN
        env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env):
            for line in open(env):
                if line.strip().startswith("HF_TOKEN="):
                    return line.strip().split("=", 1)[1].strip().strip("'\"")
        return ""

    def _select_model(self, preferred: str = None):
        candidates = ([preferred] if preferred else []) + self.CANDIDATE_MODELS
        print("[INFO] 사용 가능한 모델 탐색 중 (chat_completion)...")

        for m in candidates:
            try:
                # ✅ chat_completion으로 테스트 (text_generation은 폐지됨)
                resp = self.client.chat_completion(
                    messages=[{"role": "user", "content": "Hi"}],
                    model=m,
                    max_tokens=5,
                )
                if resp and resp.choices:
                    self.model_id = m
                    print(f"  [OK] {m}")
                    return
            except Exception as e:
                err = str(e)
                if "503" in err:
                    print(f"  [WAIT] {m}: 로딩 중 (20초 대기)...")
                    time.sleep(20)
                    try:
                        resp = self.client.chat_completion(
                            messages=[{"role": "user", "content": "Hi"}],
                            model=m, max_tokens=5,
                        )
                        if resp and resp.choices:
                            self.model_id = m
                            print(f"  [OK] {m} (로딩 후)")
                            return
                    except:
                        pass
                # 에러 분류
                if "not supported" in err.lower():
                    print(f"  [SKIP] {m}: task 미지원")
                elif "410" in err:
                    print(f"  [SKIP] {m}: 폐지(410)")
                elif "401" in err or "403" in err:
                    print(f"  [SKIP] {m}: 인증 오류")
                elif "429" in err:
                    print(f"  [SKIP] {m}: 요청 제한")
                else:
                    print(f"  [SKIP] {m}: {err[:70]}")

        print("  [ERROR] 사용 가능한 모델 없음")
        print()
        print("  [TIP] 해결 방법:")
        print("     1) HF Pro 구독 ($9/월): 더 많은 모델 사용 가능")
        print("     2) Ollama 로컬 모델: --backend ollama")
        print("     3) 토큰 권한 확인: https://huggingface.co/settings/tokens")
        print("        → 'Make calls to Inference Providers' 체크")
        self.client = None

    def generate(self, prompt: str, max_tokens: int = 4000) -> str:
        if not self.client or not self.model_id:
            return ""

        for attempt in range(3):
            try:
                resp = self.client.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "당신은 한국어 데이터 추출 전문가입니다. "
                                "반드시 유효한 JSON만 반환하세요. "
                                "설명, 마크다운, 추가 텍스트 없이 JSON만 출력하세요."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    model=self.model_id,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                content = resp.choices[0].message.content
                return content.strip() if content else ""

            except Exception as e:
                err = str(e)
                if attempt < 2:
                    wait = 3 * (attempt + 1)
                    if "429" in err:
                        wait = 10 * (attempt + 1)
                        print(f"  [WAIT] Rate limit. {wait}초 대기...")
                    elif "503" in err:
                        wait = 15
                        print(f"  [WAIT] 모델 로딩 중. {wait}초 대기...")
                    else:
                        print(f"  [RETRY] {attempt+1}: {err[:60]}")
                    time.sleep(wait)
                else:
                    print(f"  [ERROR] 최종 실패: {err[:100]}")
        return ""


class OllamaLLM(BaseLLM):
    """Ollama 로컬 LLM (ollama serve 필요)"""

    def __init__(self, model="qwen2.5", base_url="http://localhost:11434"):
        import requests; self.req = requests
        self.model = model; self.model_id = model
        self.url = f"{base_url}/api/chat"
        try:
            r = requests.get(f"{base_url}/api/tags", timeout=5)
            ms = [m["name"].split(":")[0] for m in r.json().get("models", [])]
            status = "[OK]" if any(model in m for m in ms) else "[WARN]"
            print(f"  {status} Ollama: {model}")
        except:
            print("  [ERROR] Ollama 미실행 -> ollama serve")

    def generate(self, prompt: str, max_tokens: int = 4000) -> str:
        try:
            r = self.req.post(self.url, json={
                "model": self.model, "stream": False,
                "messages": [
                    {"role": "system", "content": "한국어 JSON 추출 전문가. JSON만 반환."},
                    {"role": "user", "content": prompt}
                ],
                "options": {"num_predict": max_tokens, "temperature": 0.3},
            }, timeout=120)
            return r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            print(f"  [ERROR] Ollama: {str(e)[:60]}"); return ""
