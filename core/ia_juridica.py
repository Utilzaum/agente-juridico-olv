import json
import ollama

def analisar_publicacao(texto: str) -> dict:
    prompt = f"""
    Analise a publicação jurídica abaixo e retorne JSON válido com:

    - tipo_evento (INTIMACAO, SENTENCA, DESPACHO, OUTRO)
    - prazo_dias (numero inteiro ou null)
    - tipo_prazo ("corrido" ou "util")
    - resumo (1 frase objetiva)

    Regras:
    - Se não houver prazo, prazo_dias = null
    - Se mencionar "dias úteis", tipo_prazo = util
    - Caso contrário, tipo_prazo = corrido

    Texto:
    {texto}
    """

    response = ollama.generate(
        model="qwen2.5:7b-instruct-q4_K_M",
        prompt=prompt
    )

    try:
        return json.loads(response["response"])
    except:
        return {
            "tipo_evento": "OUTRO",
            "prazo_dias": None,
            "tipo_prazo": "corrido",
            "resumo": ""
        }
