"""Configurações do Bot Documentarista de Petições OLV."""
import os
from pathlib import Path

# Carregar .env se existir
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip())

# Token do Telegram (OBRIGATÓRIO via variável de ambiente)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_PETICOES")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "Token não configurado!\n"
        "Exporte a variável TELEGRAM_BOT_TOKEN_PETICOES ou crie um arquivo .env\n"
        "com: TELEGRAM_BOT_TOKEN_PETICOES=seu_token_aqui"
    )

# Usuários autorizados (vazio = aberto a todos)
AUTHORIZED_USERS = [
    int(x) for x in os.getenv("TELEGRAM_USER_IDS", "").split(",") if x.strip()
]

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BIBLIOTECA_DIR = BASE_DIR / "biblioteca_peticoes"
LOGS_DIR = BASE_DIR / "logs" / "bot_peticoes"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Identificação
BOT_NAME = "Documentarista de Petições OLV"
BOT_VERSION = "1.0.0"
