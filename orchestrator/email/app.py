from fastapi import FastAPI

app = FastAPI()

@app.post("/send")
def send(payload: dict):
    data = payload.get("data")

    # Simulação de envio (por enquanto)
    print(f"[EMAIL] Enviando: {data}")

    return {
        "resultado": f"Email enviado com conteúdo: {data}"
    }
