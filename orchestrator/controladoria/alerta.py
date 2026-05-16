#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alerta de Prazos - Verificação Automatizada (Async)
Integra com controladoria/service.py e envia notificações via Telegram
"""
import asyncio
from telegram import Bot
from orchestrator.controladoria.service import listar_eventos
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ⚠️ Configure suas credenciais aqui

async def enviar_mensagem(texto: str):
    """Envia mensagem assíncrona para o Telegram."""
    try:
        bot = Bot(token=TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=texto)
    except Exception as e:
        print(f"❌ Falha ao enviar mensagem: {e}")

async def verificar_prazos():
    """Busca prazos pendentes e alerta se houver urgência/vencimento."""
    eventos = listar_eventos()
    print("📦 RETORNO DO SERVICE:", eventos)

    if not eventos:
        print("📭 Nenhum prazo pendente encontrado.")
        return

    for e in eventos:
        # 🔒 Unpacking exato para 6 elementos (id, processo, descricao, prazo, tipo, status)
        id_ev, processo, descricao, prazo, tipo, status = e
        print(f"🔎 ITEM: id={id_ev} | proc={processo} | prazo={prazo} | status={status}")

        # 🚨 Gatilho de alerta baseado nos emojis retornados por calcular_status()
        if "🔴" in status or "🟠" in status or "🟡" in status:
            await enviar_mensagem(
                f"🚨 ALERTA DE PRAZO\n\n"
                f"Processo: {processo}\n"
                f"Descrição: {descricao}\n"
                f"Tipo: {tipo}\n"
                f"Prazo: {prazo}\n"
                f"Status: {status}"
            )

if __name__ == "__main__":
    asyncio.run(verificar_prazos())
