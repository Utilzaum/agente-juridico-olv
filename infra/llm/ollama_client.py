# infra/llm/ollama_client.py
"""
Cliente Genérico para LLMs via Ollama local.
✅ Conformidade LGPD: processamento 100% offline
✅ Suporte a modelos "Thinking" (remoção robusta de tags <think>)
✅ Cache em memória, validação de resposta e timeout configurável
✅ Suporte a /api/generate (prompt único) e /api/chat (conversacional)
"""
import requests
import json
import logging
import hashlib
import re  # ✅ NOVO: necessário para regex robusto
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURAÇÃO
# =========================================================
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
TIMEOUT = 15
MAX_TOKENS = 256

MODELS = {
    "bibliotecario": "qwen2.5:3b-instruct-q4_K_M",
    "prazo": "qwen2.5:3b-instruct-q4_K_M",
    "default": "qwen2.5:3b-instruct-q4_K_M",
}

DEFAULT_OPTIONS = {
    "temperature": 0.0,
    "top_p": 0.1,
    "repeat_penalty": 1.15,
    "num_ctx": 8192,
    "num_predict": 900
}

_CACHE: Dict[str, Any] = {}


def _limpar_cache(max_size: int = 100):
    if len(_CACHE) > max_size:
        chaves = list(_CACHE.keys())[:len(_CACHE)//4]
        for k in chaves:
            del _CACHE[k]


def _limpar_resposta(raw: str) -> str:
    """
    Remove blocos de raciocínio (<think>) e markdown da resposta bruta.
    ✅ CORREÇÃO CRÍTICA: funciona mesmo quando o modelo NÃO fecha </think>.
    """
    if not raw:
        return ""

    # 🧠 Remove <think>...</think> OU <think>... até o fim da string
    raw = re.sub(
        r"<think>.*?(</think>|$)",
        "",
        raw,
        flags=re.DOTALL
    )

    # 🧹 Segurança extra: remove tags residuais (defesa em profundidade)
    raw = raw.replace("<think>", "").replace("</think>", "")

    # 🧹 Remove blocos de markdown
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif raw.startswith("```"):
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    return raw.strip()


# =========================================================
# API: /api/generate (Prompt único — Agente de Prazos)
# =========================================================
def gerar(prompt: str, model_key: str = "default", timeout: int = TIMEOUT) -> str:
    model = MODELS.get(model_key, MODELS["default"])
    hash_prompt = hashlib.sha256(f"{model}:{prompt}".encode("utf-8")).hexdigest()

    if hash_prompt in _CACHE:
        logger.debug("♻️ Cache hit para geração LLM")
        return _CACHE[hash_prompt]

    try:
        resp = requests.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False, "think": False,
                "options": DEFAULT_OPTIONS
            },
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        limpo = _limpar_resposta(raw)

        _CACHE[hash_prompt] = limpo
        _limpar_cache()
        return limpo

    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama indisponível em http://localhost:11434")
        return ""
    except requests.exceptions.Timeout:
        logger.warning(f"⚠️ Timeout na inferência ({timeout}s).")
        return ""
    except Exception as e:
        logger.warning(f"⚠️ Erro inesperado no LLM (generate): {e}")
        return ""


# =========================================================
# API: /api/chat (Conversacional — Bibliotecário)
# =========================================================
def chat(
    mensagens: List[Dict[str, str]],
    model_key: str = "bibliotecario",
    timeout: int = 120,
    options: Optional[Dict] = None
) -> str:
    model = MODELS.get(model_key, MODELS["default"])
    opts = {**DEFAULT_OPTIONS, **(options or {})}

    try:
        resp = requests.post(
            OLLAMA_CHAT_URL,
            json={
                "model": model,
                "messages": mensagens,
                "stream": False,
                "options": opts
            },
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        resp.raise_for_status()
        raw = resp.json().get("message", {}).get("content", "").strip()
        return _limpar_resposta(raw)

    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama indisponível em http://localhost:11434")
        return ""
    except requests.exceptions.Timeout:
        logger.warning(f"⚠️ Timeout na inferência chat ({timeout}s).")
        return ""
    except Exception as e:
        logger.warning(f"⚠️ Erro inesperado no LLM (chat): {e}")
        return ""


# =========================================================
# PARSER E VALIDAÇÃO JURÍDICA (Agente de Prazos)
# =========================================================
def extrair_json(prompt: str, model_key: str = "default") -> Optional[Dict]:
    raw_text = gerar(prompt, model_key)
    if not raw_text:
        return None

    try:
        resultado = json.loads(raw_text)
        if not isinstance(resultado, dict):
            raise ValueError("Resposta não é um dicionário JSON")
        return _validar_resposta_juridica(resultado)
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ JSON inválido do LLM. Resposta crua: {raw_text[:100]}... | Erro: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erro ao processar resposta do LLM: {e}")
        return None


def _validar_resposta_juridica(resultado: Dict) -> Dict:
    prazo = resultado.get("prazo_dias")
    if prazo is not None:
        if not isinstance(prazo, int) or prazo < 1 or prazo > 100:
            logger.warning(f"⚠️ prazo_dias inválido ({prazo}), nullificado.")
            resultado["prazo_dias"] = None

    unidade = resultado.get("unidade")
    if unidade and unidade not in ("UTEIS", "CORRIDOS"):
        logger.warning(f"⚠️ unidade inválida ('{unidade}'), nullificada.")
        resultado["unidade"] = None

    ramo = resultado.get("ramo")
    if ramo not in ("CPC", "CPP", "CLT"):
        logger.debug(f"🔒 ramo não reconhecido ('{ramo}'), assumindo CPC.")
        resultado["ramo"] = "CPC"

    aud = resultado.get("audiencia_data")
    if aud and isinstance(aud, str) and len(aud) == 10:
        if aud[4] != "-" or aud[7] != "-":
            logger.warning(f"⚠️ audiencia_data em formato inválido: '{aud}'")
            resultado["audiencia_data"] = None

    return resultado


# =========================================================
# WRAPPERS DE NEGÓCIO
# =========================================================
def extrair_prazo_com_llm(texto: str) -> Dict:
    from .prompts import PROMPT_EXTRAIR_PRAZO

    texto_limpo = texto[:2500] if len(texto) > 2500 else texto
    prompt_final = PROMPT_EXTRAIR_PRAZO.format(texto=texto_limpo)

    resultado = extrair_json(prompt_final, model_key="prazo")
    if resultado is None:
        return _fallback_seguro()
    return resultado


def _fallback_seguro() -> Dict:
    return {
        "prazo_dias": None,
        "unidade": None,
        "ramo": "CPC",
        "menciona_prazo": False,
        "audiencia_data": None
    }


def health_check() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False
