import requests, json, os, logging, re, asyncio

logger = logging.getLogger(__name__)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = "qwen2.5:3b-instruct-q4_K_M"

async def interpretar_com_llm(texto: str) -> dict:
    prompt = f"""O usuário digitou: '{texto}'.
Extraia estado civil, profissão, nacionalidade.
Retorne APENAS JSON: {{"estado_civil": "...", "profissao": "...", "nacionalidade": "..."}}"""
    
    payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
    
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        content = response.json().get("response", "{}")
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.error(f"Erro Interpreter: {e}")
    
    return {}
