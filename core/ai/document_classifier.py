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

async def interpretar_com_llm(texto: str) -> dict:
    prompt = f"""O usuário digitou o seguinte texto livre para atualizar dados: '{texto}'.
Pense dentro de <think> e extraia apenas estado_civil, profissao e nacionalidade.
Retorne APENAS o JSON final (use null se não encontrar):
{{"estado_civil": "...", "profissao": "...", "nacionalidade": "..."}}"""

    payload = {
        "model": MODEL, 
        "prompt": prompt, 
        "stream": False, 
        "options": {"temperature": 0.2, "num_predict": 200}
    }
    
    try:
        response = await asyncio.to_thread(
            requests.post, f"{OLLAMA_URL}/api/generate", json=payload, timeout=30
        )
        response.raise_for_status()
        content = response.json().get("response", "{}")
        return _extrair_json_robusto(content)
    except Exception as e:
        logger.error(f"Erro Interpreter: {e}")
        return {}
