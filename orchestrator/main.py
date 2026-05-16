#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Orquestrador CLI do Agente Jurídico
Gerencia bots (Executor, DJEN, Email) e a Controladoria Jurídica via linha de comando.
"""
import os
import logging

# 📦 Import flexível: funciona rodando como módulo ou script direto
try:
    from .process_manager import start_bot, stop_bot, stop_all, status_bot
    from .controladoria.service import criar_evento, listar_eventos, concluir_evento
except ImportError:
    from process_manager import start_bot, stop_bot, stop_all, status_bot
    from controladoria.service import criar_evento, listar_eventos, concluir_evento

# 📝 Configuração básica de logs (não polui o terminal, salva em arquivo)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/orchestrator.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def process_message(text: str) -> str:
    """Recebe o comando do usuário, identifica a ação e retorna a resposta."""
    raw_text = text.strip()
    # Versão "limpa" apenas para comparação de comandos fixos
    # ⚠️ Mantemos raw_text intacto para não quebrar parsing de datas com '/'
    command = raw_text.lower().replace("/", "")
    logger.info(f"Comando recebido: {command}")

    # =========================
    # 🤖 GERENCIAMENTO DE BOTS
    # =========================
    if command in ["status", "sistema", "health"]:
        return "\n".join([
            "📊 STATUS DO SISTEMA:",
            status_bot("executor"),
            status_bot("email"),
            status_bot("djen")
        ])

    if command in ["kit", "gerar kit", "start executor", "iniciar executor"]:
        return start_bot("executor", "python -m core.bot")

    if command in ["publicacoes", "publicação", "djen", "processar publicação"]:
        return start_bot("djen", "python script_djen.py")

    if command in ["email", "enviar email"]:
        return start_bot("email", "python bot_email.py")

    if command in ["stop executor", "parar executor", "desligar executor"]:
        return stop_bot("executor")

    if command in ["stop all", "parar tudo", "desligar tudo"]:
        return stop_all()

    # =========================
    # ⚖️ CONTROLADORIA JURÍDICA
    # =========================
    if command.startswith("novo prazo"):
        try:
            # Formato: novo prazo <processo> <descricao> <dias> <CPC/CPP/CLT>
            parts = raw_text.split()
            if len(parts) < 6:
                return "❌ Formato inválido.\nUse: `novo prazo <processo> <descricao> <dias> <tipo>`"

            processo = parts[2]
            descricao = parts[3]
            dias = int(parts[4])          # Converte para inteiro
            tipo = parts[5].upper()       # Força maiúsculas

            if tipo not in ("CPC", "CPP", "CLT"):
                return "❌ Tipo inválido. Use CPC, CPP ou CLT."

            return criar_evento(processo, descricao, dias, tipo)
        except ValueError:
            return "❌ O campo de dias deve ser um número inteiro."
        except Exception as e:
            return f"❌ Erro ao criar prazo: {e}"

    if command in ["prazos", "listar prazos", "ver prazos"]:
        try:
            eventos = listar_eventos()
            # Alguns retornos podem ser string se não houver conexão
            if isinstance(eventos, str) or not eventos:
                return "📭 Nenhum prazo pendente."

            resposta = "📅 Prazos Pendentes:\n\n"
            # listar_eventos retorna: (id, processo, descricao, prazo, tipo, status_visual)
            for id_ev, processo, descricao, prazo, tipo, status in eventos:
                resposta += f"[{status}] ID: {id_ev} | {processo}\n"
                resposta += f"      📝 {descricao} | 📅 {prazo} | ⚖️ {tipo}\n\n"
            return resposta.strip()
        except Exception as e:
            return f"❌ Erro ao listar prazos: {e}"

    if command.startswith("concluir"):
        try:
            # Pega o texto depois de "concluir" e remove espaços
            id_str = raw_text.replace("concluir", "").strip()
            if not id_str.isdigit():
                return "❌ Uso correto: `concluir <id>` (ex: concluir 5)"

            evento_id = int(id_str)
            return concluir_evento(evento_id)
        except Exception as e:
            return f"❌ Erro ao concluir prazo: {e}"

    # =========================
    # 🔁 FALLBACK (comando não reconhecido)
    # =========================
    logger.warning(f"Comando não reconhecido: '{command}'")
    return (
        "⚠️ Comando não reconhecido.\n"
        "Comandos disponíveis:\n"
        "• `status`\n"
        "• `start djen` / `start executor` / `start email`\n"
        "• `stop executor` / `stop all`\n"
        "• `novo prazo <proc> <desc> <dias> <tipo>`\n"
        "• `prazos`\n"
        "• `concluir <id>`"
    )


# =========================
# 🚀 CLI INTERATIVO
# =========================
if __name__ == "__main__":
    print("🔧 Orquestrador CLI iniciado. Digite 'sair' para encerrar.")
    while True:
        try:
            msg = input("Comando: ").strip()
            if not msg:
                continue  # Ignora enter vazio
            if msg.lower() in ["sair", "exit", "quit"]:
                print("👋 Encerrando orquestrador...")
                break
            print(process_message(msg))
        except KeyboardInterrupt:
            print("\n⚠️ Interrompido pelo usuário (Ctrl+C).")
            break
        except EOFError:
            break
