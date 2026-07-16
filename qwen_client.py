# qwen_client.py
"""
Cliente para extração jurídica com Qwen via Ollama local.
✅ Timeout configurável + Validação de resposta + Cache
✅ Conformidade LGPD: processamento 100% offline
"""
import requests
import json
import logging
import hashlib
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Configurações
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "hf.co/LiquidAI/LFM2.5-1.2B-Thinking-GGUF:Q4_K_M"
TIMEOUT = 15  # ⚠️ Timeout crítico para evitar travamento
MAX_TOKENS = 256

# Cache simples para evitar reprocessamento
_CACHE: Dict[str, Dict] = {}

def _limpar_cache(max_size: int = 100):
    """Mantém o cache limitado para evitar vazamento de memória."""
    if len(_CACHE) > max_size:
        chaves = list(_CACHE.keys())[:len(_CACHE)//4]
        for k in chaves:
            del _CACHE[k]

def _validar_resposta_llm(resultado: Dict) -> Dict:
    """
    Validação de qualidade da resposta do LLM.
    ✅ Correção crítica: rejeita valores fora de faixa segura.
    """
    # Validação de prazo_dias (1 a 100 dias)
    prazo = resultado.get("prazo_dias")
    if prazo is not None:
        if not isinstance(prazo, int) or prazo < 1 or prazo > 100:
            logger.warning(f"⚠️ prazo_dias inválido ({prazo}), nullificado.")
            resultado["prazo_dias"] = None
    
    # Validação de unidade
    unidade = resultado.get("unidade")
    if unidade and unidade not in ("UTEIS", "CORRIDOS"):
        logger.warning(f"⚠️ unidade inválida ('{unidade}'), nullificada.")
        resultado["unidade"] = None
    
    # Validação de ramo (fallback para CPC)
    ramo = resultado.get("ramo")
    if ramo not in ("CPC", "CPP", "CLT"):
        logger.debug(f"🔒 ramo não reconhecido ('{ramo}'), assumindo CPC.")
        resultado["ramo"] = "CPC"
    
    # Validação de audiencia_data (formato ISO)
    aud = resultado.get("audiencia_data")
    if aud and isinstance(aud, str) and len(aud) == 10:
        # Verifica se parece ser YYYY-MM-DD
        if aud[4] != "-" or aud[7] != "-":
            logger.warning(f"⚠️ audiencia_data em formato inválido: '{aud}'")
            resultado["audiencia_data"] = None
    
    return resultado

def extrair_prazo_com_llm(texto: str, timeout: int = TIMEOUT) -> Dict:
    """
    Extrai informações de prazo processual usando Qwen local.
    
    Retorna estrutura padronizada e VALIDADA:
    {
        "prazo_dias": int|null (1-100),
        "unidade": "UTEIS"|"CORRIDOS"|null,
        "ramo": "CPC"|"CPP"|"CLT" (default: CPC),
        "menciona_prazo": bool,
        "audiencia_data": "YYYY-MM-DD"|null
    }
    """
    # Hash para cache
    hash_texto = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    if hash_texto in _CACHE:
        logger.debug("♻️ Cache hit para extração de prazo")
        return _CACHE[hash_texto].copy()

    # Trunca texto para evitar overflow
    texto_limpo = texto[:2500] if len(texto) > 2500 else texto

    prompt = f"""Você é um assistente jurídico especializado em prazos processuais brasileiros.

Extraia APENAS os campos abaixo em JSON válido, sem markdown, sem explicações:
{{
  "prazo_dias": número inteiro ou null,
  "unidade": "UTEIS" | "CORRIDOS" | null,
  "ramo": "CPC" | "CPP" | "CLT" | null,
  "menciona_prazo": true | false,
  "audiencia_data": "YYYY-MM-DD" | null
}}

Regras:
1. Se não houver prazo explícito, retorne null em prazo_dias
2. Para audiências, priorize audiencia_data no formato YYYY-MM-DD
3. Unidade padrão para CPC é "UTEIS", para CPP é "CORRIDOS"
4. Responda APENAS com JSON puro

Texto jurídico:
\"\"\"{texto_limpo}\"\"\"
"""

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": MAX_TOKENS}},
            headers={"Content-Type": "application/json"},
            timeout=timeout  # ✅ Timeout crítico aplicado
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}").strip()

        # Remove blocos markdown
        if raw.startswith("```"):
            raw = raw.split("```json")[-1].split("```")[0].strip()
        elif raw.startswith("```json"):
            raw = raw[7:].split("```")[0].strip()

        resultado = json.loads(raw)
        
        if not isinstance(resultado, dict):
            raise ValueError("Resposta não é um dicionário")
        
        # ✅ Validação de qualidade aplicada
        resultado_validado = _validar_resposta_llm(resultado)
        
        _CACHE[hash_texto] = resultado_validado
        _limpar_cache()
        return resultado_validado.copy()

    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama indisponível em http://localhost:11434")
        return _fallback_seguro()
    except requests.exceptions.Timeout:
        logger.warning(f"⚠️ Timeout na inferência ({timeout}s). Usando fallback.")
        return _fallback_seguro()
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ JSON inválido do LLM: {e}")
        return _fallback_seguro()
    except Exception as e:
        logger.warning(f"⚠️ Erro inesperado no LLM: {e}")
        return _fallback_seguro()

def _fallback_seguro() -> Dict:
    """Retorna estrutura segura quando o LLM falha."""
    return {
        "prazo_dias": None,
        "unidade": None,
        "ramo": "CPC",  # ✅ Default seguro explícito
        "menciona_prazo": False,
        "audiencia_data": None
    }

def health_check() -> bool:
    """Verifica se o Ollama está respondendo."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        return resp.status_code == 200
    except:
        return False
