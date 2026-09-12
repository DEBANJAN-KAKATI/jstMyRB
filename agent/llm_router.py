import os
import json
import hashlib
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple
from agent.db import db
from path_utils import get_base_dir, get_writable_dir

SETTINGS_PATH = os.path.join(get_writable_dir("data"), "settings.json")

def load_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings: Dict[str, Any]):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Notice: could not save settings to {SETTINGS_PATH}: {e}")

def clean_json_str(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

# Estimated costs per 1K tokens (USD)
MODEL_PRICING = {
    "gemini-2.0-flash": (0.0001, 0.0004),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "ollama": (0.0, 0.0)
}

class LLMRouter:
    def __init__(self):
        self.settings = load_settings()

    def get_api_key(self, provider: str = "gemini") -> Optional[str]:
        self.settings = load_settings()
        if provider == "gemini":
            return (
                self.settings.get("gemini_api_key")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
        elif provider == "openai":
            return (
                self.settings.get("openai_api_key")
                or os.environ.get("OPENAI_API_KEY")
            )
        elif provider == "anthropic":
            return (
                self.settings.get("anthropic_api_key")
                or os.environ.get("ANTHROPIC_API_KEY")
            )
        return None

    def get_preferred_provider(self) -> str:
        self.settings = load_settings()
        return self.settings.get("llm_provider", "auto")

    def _make_cache_key(self, provider: str, model: str, prompt: str, system_prompt: str) -> str:
        payload = f"{provider}:{model}:{system_prompt}:{prompt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        provider: str = "auto",
        model: Optional[str] = None,
        temperature: float = 0.2,
        purpose: str = "general"
    ) -> Optional[Dict[str, Any]]:
        """
        Executes LLM call expecting a structured JSON response.
        Checks cache first, then attempts provider with auto-fallback.
        """
        raw = self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt + "\nReturn pure JSON only. Do not wrap in conversational markdown.",
            provider=provider,
            model=model,
            temperature=temperature,
            purpose=purpose,
            require_json=True
        )
        if not raw:
            return None
        try:
            cleaned = clean_json_str(raw)
            return json.loads(cleaned)
        except Exception as e:
            print(f"LLMRouter: JSON decode error: {e}. Raw response was:\n{raw[:300]}")
            return None

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        provider: str = "auto",
        model: Optional[str] = None,
        temperature: float = 0.2,
        purpose: str = "general",
        require_json: bool = False
    ) -> Optional[str]:
        """
        Routes text generation with caching, cost tracking, and multi-provider fallback.
        """
        if provider == "auto":
            pref = self.get_preferred_provider()
            if pref != "auto":
                provider = pref
            else:
                # Default order: gemini -> openai -> anthropic -> ollama
                if self.get_api_key("gemini"):
                    provider = "gemini"
                elif self.get_api_key("openai"):
                    provider = "openai"
                elif self.get_api_key("anthropic"):
                    provider = "anthropic"
                else:
                    provider = "ollama"

        # Check cache
        cache_key = self._make_cache_key(provider, model or "default", prompt, system_prompt)
        cached = db.get_cache(cache_key)
        if cached and "text" in cached:
            return cached["text"]

        res = None
        used_model = model or "default"
        tokens_in = max(1, len(prompt.split()) * 4 // 3)
        tokens_out = 0

        # Try designated provider
        if provider == "gemini":
            res, used_model, tokens_out = self._call_gemini(prompt, system_prompt, model, temperature, require_json)
        elif provider == "openai":
            res, used_model, tokens_out = self._call_openai(prompt, system_prompt, model, temperature, require_json)
        elif provider == "anthropic":
            res, used_model, tokens_out = self._call_anthropic(prompt, system_prompt, model, temperature)
        elif provider == "ollama":
            res, used_model, tokens_out = self._call_ollama(prompt, system_prompt, model, temperature)

        # Fallback to Gemini if other failed
        if not res and provider != "gemini" and self.get_api_key("gemini"):
            print(f"LLMRouter: Falling back from {provider} to Gemini...")
            res, used_model, tokens_out = self._call_gemini(prompt, system_prompt, None, temperature, require_json)
            provider = "gemini"

        if res:
            # Calculate estimated cost
            rates = MODEL_PRICING.get(used_model, (0.0001, 0.0004))
            cost = (tokens_in / 1000.0 * rates[0]) + (tokens_out / 1000.0 * rates[1])
            db.log_api_usage(provider, used_model, tokens_in, tokens_out, cost, purpose)
            db.set_cache(cache_key, {"text": res, "provider": provider, "model": used_model})
            return res

        return None

    def _call_gemini(
        self, prompt: str, system_prompt: str, model_name: Optional[str], temp: float, json_mode: bool
    ) -> Tuple[Optional[str], str, int]:
        api_key = self.get_api_key("gemini")
        if not api_key:
            return None, "", 0

        models_to_try = [model_name] if model_name else [
            "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"
        ]

        # 1. google.genai
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            for m in models_to_try:
                try:
                    cfg_kwargs = {"temperature": temp}
                    if system_prompt:
                        cfg_kwargs["system_instruction"] = system_prompt
                    if json_mode:
                        cfg_kwargs["response_mime_type"] = "application/json"
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(**cfg_kwargs)
                    )
                    if resp and resp.text:
                        tokens_out = max(1, len(resp.text.split()) * 4 // 3)
                        return resp.text, m, tokens_out
                except Exception as e:
                    print(f"google.genai {m} attempt failed: {e}")
                    continue
        except Exception:
            pass

        # 2. google.generativeai fallback
        try:
            import google.generativeai as gai
            gai.configure(api_key=api_key)
            for m in models_to_try:
                try:
                    gen_cfg = {"temperature": temp}
                    if json_mode:
                        gen_cfg["response_mime_type"] = "application/json"
                    model_obj = gai.GenerativeModel(
                        model_name=m,
                        system_instruction=system_prompt if system_prompt else None,
                        generation_config=gen_cfg
                    )
                    resp = model_obj.generate_content(prompt)
                    if resp and resp.text:
                        tokens_out = max(1, len(resp.text.split()) * 4 // 3)
                        return resp.text, m, tokens_out
                except Exception as e:
                    print(f"google.generativeai {m} attempt failed: {e}")
                    continue
        except Exception:
            pass

        return None, "", 0

    def _call_openai(
        self, prompt: str, system_prompt: str, model_name: Optional[str], temp: float, json_mode: bool
    ) -> Tuple[Optional[str], str, int]:
        api_key = self.get_api_key("openai")
        if not api_key:
            return None, "", 0

        target_model = model_name or "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temp
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                out_tokens = data.get("usage", {}).get("completion_tokens", len(text.split()))
                return text, target_model, out_tokens
        except Exception as e:
            print(f"LLMRouter: OpenAI call failed: {e}")
            return None, target_model, 0

    def _call_anthropic(
        self, prompt: str, system_prompt: str, model_name: Optional[str], temp: float
    ) -> Tuple[Optional[str], str, int]:
        api_key = self.get_api_key("anthropic")
        if not api_key:
            return None, "", 0

        target_model = model_name or "claude-3-5-sonnet-20241022"
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": target_model,
            "max_tokens": 4096,
            "temperature": temp,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["content"][0]["text"]
                out_tokens = data.get("usage", {}).get("output_tokens", len(text.split()))
                return text, target_model, out_tokens
        except Exception as e:
            print(f"LLMRouter: Anthropic call failed: {e}")
            return None, target_model, 0

    def _call_ollama(
        self, prompt: str, system_prompt: str, model_name: Optional[str], temp: float
    ) -> Tuple[Optional[str], str, int]:
        target_model = model_name or "llama3.2"
        endpoint = self.settings.get("ollama_endpoint", "http://localhost:11434/api/generate")
        payload = {
            "model": target_model,
            "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
            "stream": False,
            "options": {"temperature": temp}
        }
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "")
                return text, target_model, len(text.split())
        except Exception as e:
            # Ollama might not be running locally
            print(f"LLMRouter: Local Ollama unavailable: {e}")
            return None, target_model, 0

router = LLMRouter()
