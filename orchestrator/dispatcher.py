import requests
from orchestrator.config import SERVICES

def dispatch(action, payload):
    url = SERVICES.get(action)

    if not url:
        return {"error": f"Serviço '{action}' não encontrado"}

    try:
        response = requests.post(url, json={"data": payload}, timeout=30)
        return response.json()
    except Exception as e:
        return {"resultado": response.text}
