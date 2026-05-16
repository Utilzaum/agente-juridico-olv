from fastapi import FastAPI
import asyncio

# IMPORTANTE: importar do seu bot
from bot import gerar_kit_inicial, get_user_data

app = FastAPI()

@app.post("/run")
async def run(payload: dict):
    comando = payload.get("data")

    if "kit" in comando:
        chat_id = 999  # pode ser fixo por enquanto

        # simula dados (depois virão do Telegram)
        user_data = get_user_data(chat_id)
        user_data["nome"] = "Cliente Teste"
        user_data["cpf"] = "12345678901"
        user_data["endereco"] = "Rua Teste"
        user_data["email"] = "teste@email.com"

        arquivos = await gerar_kit_inicial(chat_id)

        return {
            "resultado": f"{len(arquivos)} documentos gerados"
        }

    return {"resultado": "Comando não reconhecido"}
