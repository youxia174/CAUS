import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()


def chat(messages, temperature=0.2, timeout=(5, 20), tools=None, tool_choice=None):
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("LLM_MODEL", "").strip()
    if not (api_key and base_url and model):
        return None
    payload = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
    try:
        r = requests.post(
            base_url + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("choices", [{}])[0].get("message")
    except requests.Timeout:
        print("[LLM] timeout -> fallback")
    except requests.RequestException as e:
        print(f"[LLM] request error: {e}")
    except (KeyError, IndexError, ValueError) as e:
        print(f"[LLM] response error: {e}")
    return None
