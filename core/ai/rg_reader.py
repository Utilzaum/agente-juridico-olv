import requests, json, os, logging, re, asyncio
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "hf.co/LiquidAI/LFM2.5-1.2B-Thinking-GGUF:Q4_K_M")

def _extrair_json_robusto(texto: str) -> dict:
    if not texto: return {}
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"```[a-z]*\s*|\s*```", "", texto, flags=re.IGNORECASE)
    inicio = texto.find('{')
    fim = texto.rfind('}')
    if inicio != -1 and fim != -1 and fim > inicio:
        try: return json.loads(texto[inicio:fim+1])
        except json.JSONDecodeError: pass
    return {}

async def extrair_rg(texto_ocr: str) -> dict:
    prompt = f"""Você é um especialista em ler RGs brasileiros.
Analise o texto OCR abaixo. Pense dentro de <think> e extraia APENAS os dados do titular.
Retorne APENAS o JSON final (use null se não encontrar):
{{
    "nome": "nome completo",
    "cpf": "apenas 11 números",
    "rg": "número do RG",
    "data_nascimento": "DD/MM/AAAA",
    "orgao_expedidor": "ex: SSP/PR",
    "nacionalidade": "se houver",
    "estado_civil": "se houver",
    "profissao": "se houver"
}}
Texto OCR:
{texto_ocr[:2000]}"""

    payload = {
        "model": MODEL, 
        "prompt": prompt, 
        "stream": False, 
        "options": {"temperature": 0.1, "num_predict": 600}
    }
    
    try:
        response = await asyncio.to_thread(
            requests.post, f"{OLLAMA_URL}/api/generate", json=payload, timeout=45
        )
        response.raise_for_status()
        content = response.json().get("response", "")
        dados = _extrair_json_robusto(content)
        if dados:
            dados["confidence"] = 0.92 # Hardcoded de confiança do especialista
        return dados
    except Exception as e:
        logger.error(f"Erro RG Reader: {e}")
        return {}
