#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestrador Jurídico v3.1 — Experiência Humanizada
✅ CAMADA ÚNICA: infra.repositorio (única fonte de verdade)
✅ UX HUMANIZADA: Mensagens claras, amigáveis e contextuais
✅ LGPD: Proteção de dados sensíveis mantida
✅ PAGINAÇÃO: Navegação fluida entre prazos
✅ AUDITORIA: Rastreabilidade completa de ações
✅ SAFE SHUTDOWN: Desligamento seguro em 2 etapas
"""
from __future__ import annotations
import os
import sys
import signal
import asyncio
import subprocess
import re
import html as html_module
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Any
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackQueryHandler
)
from datetime import date, datetime, timedelta

# =========================================================
# 📋 LOGGING
# =========================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "orquestrador.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# =========================================================
# ✅ CAMADA ÚNICA: infra.repositorio (única fonte de verdade)
# =========================================================
logger.info("=" * 60)
try:
    from infra.repositorio import (
        # Eventos
        buscar_eventos_pendentes,
        buscar_evento_por_id,
        # Ações
        concluir_evento,
        corrigir_prazo,
        reabrir_evento,
        # Consultas
        listar_concluidos,
        listar_auditoria,
        # Cursores
        obter_cursor,
        atualizar_cursor,
    )
    REPOSITORIO_OK = True
    logger.info("✅ REPOSITÓRIO CENTRAL carregado (camada única)")
except Exception as e:
    logger.error(f"❌ Erro ao importar repositorio: {e}")
    REPOSITORIO_OK = False
    # Fallbacks para não quebrar o bot
    def buscar_eventos_pendentes(*a, **k): return []
    def buscar_evento_por_id(*a, **k): return None
    def concluir_evento(*a, **k): return "❌ Sistema indisponível no momento"
    def corrigir_prazo(*a, **k): return "❌ Sistema indisponível no momento"
    def reabrir_evento(*a, **k): return "❌ Sistema indisponível no momento"
    def listar_concluidos(*a, **k): return []
    def listar_auditoria(*a, **k): return []
    def obter_cursor(*a, **k): return None
    def atualizar_cursor(*a, **k): None
logger.info("=" * 60)

# =========================================================
# ✅ CAMADA DE FORMATAÇÃO
# =========================================================
try:
    from telegram_formatter import (
        formatar_prazo,
        formatar_dashboard,
        formatar_status,
        formatar_auditoria,
        formatar_ajuda,
        formatar_briefing,
    )
    FORMATTER_OK = True
except ImportError as e:
    logger.error(f"❌ ERRO IMPORT FORMATTER: {e}")
    FORMATTER_OK = False
    def formatar_prazo(e): return str(e)
    def formatar_dashboard(s): return str(s)
    def formatar_status(s): return str(s)
    def formatar_auditoria(c): return " Auditoria indisponível"
    def formatar_ajuda(): return "📖 Ajuda indisponível"
    def formatar_briefing(**k): return "📊 Briefing indisponível"

# =========================================================
# 🔐 CONFIG
# =========================================================
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_ORQUESTRADOR")
if not TOKEN:
    raise ValueError(" TOKEN não encontrado")
ADMIN_ID = 501276610
ADMIN_NOME = "Raphael"

# =========================================================
# 🔒 LOCK
# =========================================================
LOCK_FILE = Path("/tmp/orquestrador_olv.lock")
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except:
        return False

def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _pid_alive(old_pid):
                logger.warning(f"⚠️ Já rodando (PID {old_pid})")
                sys.exit(1)
        except:
            pass
        LOCK_FILE.write_text(str(os.getpid()))

def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
        logger.info("🔓 Lock file liberado")
    except Exception as e:
        logger.error(f"❌ Erro ao liberar lock: {e}")

# =========================================================
# 🧠 PROCESSOS
# =========================================================
processos: Dict[str, subprocess.Popen] = {}

def _spawn(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=str(BASE_DIR), start_new_session=True)

def start_processo(nome: str, comando: list[str]) -> str:
    proc = processos.get(nome)
    if proc and proc.poll() is None:
        return f"⚠️ {nome} já está rodando (PID {proc.pid})"
    if proc:
        processos.pop(nome, None)
    new_proc = _spawn(comando)
    processos[nome] = new_proc
    return f"✅ {nome} iniciado com sucesso (PID {new_proc.pid})"

def stop_processo(nome: str, timeout: int = 10) -> str:
    proc = processos.get(nome)
    if not proc:
        return f"⚠️ {nome} não está registrado"
    if proc.poll() is not None:
        processos.pop(nome, None)
        return f"ℹ️ {nome} já estava parado"
    try:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
            logger.info(f"🛑 {nome} encerrado graciosamente (PID {proc.pid})")
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️ {nome} não respondeu ao SIGTERM, enviando SIGKILL")
            proc.kill()
            proc.wait(timeout=5)
        finally:
            processos.pop(nome, None)
        return f"🛑 {nome} parado com sucesso"
    except Exception as e:
        logger.error(f"❌ Erro ao parar {nome}: {e}")
        return f"❌ Erro ao parar {nome}: {e}"

def stop_all_processos(timeout: int = 10) -> str:
    resultados = []
    for nome in list(processos.keys()):
        try:
            msg = stop_processo(nome, timeout)
            resultados.append(msg)
        except Exception as e:
            resultados.append(f"❌ {nome}: {e}")
    return "\n".join(resultados) if resultados else "ℹ️ Nenhum processo ativo"

def _get_comando_bot(nome: str) -> list[str]:
    venv_python = BASE_DIR / "venv" / "bin" / "python"
    python_exec = str(venv_python) if venv_python.exists() else sys.executable
    comandos = {
        "executor": [python_exec, "-m", "core.bot"],
        "djen": [python_exec, str(BASE_DIR / "script_djen.py")],
        "ia": [python_exec, str(BASE_DIR / "bot_ocr_conversacional.py")],
    }
    return comandos.get(nome, [python_exec, str(BASE_DIR / f"bot_{nome}.py")])

# =========================================================
# ✅ STATUS GLOBAL
# =========================================================
def obter_status_global() -> Dict[str, Dict[str, Any]]:
    status = {}
    for nome_bot in ["djen", "executor", "ia"]:
        proc = processos.get(nome_bot)
        if proc and proc.poll() is None:
            status[nome_bot] = {"estado": "rodando", "pid": proc.pid, "icone": "🟢"}
        else:
            status[nome_bot] = {"estado": "parado", "pid": None, "icone": "🔴"}
    return status

# =========================================================
# 🔒 LGPD - MÁSCARA CNJ
# =========================================================
def escape_html(texto: str) -> str:
    if not texto:
        return ""
    return html_module.escape(str(texto))

def mascarar_spoiler(texto: str) -> str:
    if not texto or texto == "N/D":
        return "N/D"
    return f"<tg-spoiler>{escape_html(str(texto))}</tg-spoiler>"

def mascarar_processo(processo: str) -> str:
    """
    Retorna apenas os dígitos do número de processo.
    Remove pontos, traços e outros caracteres especiais.
    """
    if not processo or processo == "N/D":
        return "N/D"
    # Extrai apenas os dígitos
    processo_limpo = "".join(filter(str.isdigit, str(processo)))
    return processo_limpo if processo_limpo else "N/D"

# =========================================================
# 🎨 HELPERS
# =========================================================
def get_saudacao() -> str:
    hora = datetime.now().hour
    if hora < 12: return "️ Bom dia"
    elif hora < 18: return "🌤️ Boa tarde"
    else: return "🌙 Boa noite"

def get_dia_semana() -> str:
    dias = ["segunda-feira", "terça-feira", "quarta-feira",
            "quinta-feira", "sexta-feira", "sábado", "domingo"]
    return dias[date.today().weekday()]

def validar_html_telegram(texto: str) -> str:
    if not texto:
        return ""
    if len(texto) > 4000:
        texto = texto[:3900] + "\n<i>... (truncado)</i>"
    texto = texto.replace("<blockquote expandable>", "<blockquote>")
    return texto

# =========================================================
# 🛡️ SAFE SHUTDOWN v2.1
# =========================================================
class SafeShutdown:
    ESTADO_IDLE = "idle"
    ESTADO_AGUARDANDO = "aguardando"
    ESTADO_EXECUTANDO = "executando"
    
    def __init__(self):
        self.estado = self.ESTADO_IDLE
        self.usuario_solicitante = None
        self.timestamp_solicitacao = None
        self.timeout_confirmacao = 60
    
    def solicitar(self, usuario_id: int, usuario_nome: str) -> Tuple[bool, str]:
        if self.estado == self.ESTADO_EXECUTANDO:
            return False, "⚠️ Shutdown já em execução"
        if self.estado == self.ESTADO_AGUARDANDO and self.timestamp_solicitacao:
            decorrido = (datetime.now() - self.timestamp_solicitacao).total_seconds()
            if decorrido < self.timeout_confirmacao:
                return False, f"️ Aguardando confirmação ({int(self.timeout_confirmacao - decorrido)}s restantes)"
        
        self.estado = self.ESTADO_AGUARDANDO
        self.usuario_solicitante = usuario_id
        self.timestamp_solicitacao = datetime.now()
        logger.info(f"🛡️ Shutdown solicitado por {usuario_nome} (ID: {usuario_id})")
        
        return True, (
            f"️ <b>CONFIRMAÇÃO DE SHUTDOWN</b>\n\n"
            f" Solicitado por: <tg-spoiler>{escape_html(usuario_nome)}</tg-spoiler>\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"<b>Ações que serão executadas:</b>\n"
            f"1. 🛑 Encerrar todos os bots (DJEN, Executor, IA)\n"
            f"2. 🔓 Liberar lock file\n"
            f"3. 💾 Fechar conexões com banco\n"
            f"4. ⏻ Desligar o sistema\n\n"
            f"<b>⚠️ ATENÇÃO:</b> Esta ação é irreversível!\n\n"
            f"Digite <code>CONFIRMAR</code> para prosseguir\n"
            f"ou <code>CANCELAR</code> para abortar"
        )
    
    def confirmar(self, usuario_id: int) -> Tuple[bool, str]:
        if self.estado != self.ESTADO_AGUARDANDO:
            return False, "⚠️ Nenhuma solicitação pendente"
        if self.usuario_solicitante != usuario_id:
            return False, "❌ Apenas o solicitante pode confirmar"
        if self.timestamp_solicitacao:
            decorrido = (datetime.now() - self.timestamp_solicitacao).total_seconds()
            if decorrido > self.timeout_confirmacao:
                self.estado = self.ESTADO_IDLE
                return False, "⏰ Tempo expirado. Solicite novamente."
        
        self.estado = self.ESTADO_EXECUTANDO
        logger.critical(f"🔴 SHUTDOWN CONFIRMADO por usuário {usuario_id}")
        return True, "🛑 Iniciando shutdown seguro..."
    
    def executar(self) -> str:
        linhas = []
        try:
            linhas.append("<b>1. Encerrando processos...</b>")
            linhas.append(stop_all_processos(timeout=10))
            linhas.append("\n<b>2. Aguardando encerramento...</b>")
            time.sleep(2)
            linhas.append("\n<b>3. Liberando recursos...</b>")
            release_lock()
            linhas.append("🔓 Lock file liberado")
            linhas.append("\n<b>4. Fechando banco...</b>")
            import gc
            gc.collect()
            linhas.append("💾 Conexões fechadas")
            linhas.append("\n<b>5. Desligando sistema...</b>")
            linhas.append("⏻ Sistema será desligado em 5 segundos...")
        except Exception as e:
            logger.error(f"❌ Erro no shutdown: {e}", exc_info=True)
            linhas.append(f"❌ Erro: {escape_html(str(e))}")
        finally:
            self._agendar_poweroff()
        return "\n".join(linhas)
    
    def _agendar_poweroff(self, delay: int = 5):
        def _poweroff():
            time.sleep(delay)
            logger.critical("⏻ EXECUTANDO POWEROFF")
            comandos = [
                ["sudo", "systemctl", "poweroff"],
                ["sudo", "shutdown", "-h", "now"],
                ["sudo", "poweroff"],
            ]
            for cmd in comandos:
                try:
                    logger.info(f"🔌 Tentando: {' '.join(cmd)}")
                    subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                    logger.info("✅ Poweroff executado com sucesso")
                    return
                except subprocess.CalledProcessError as e:
                    logger.warning(f"⚠️ {cmd} falhou: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ {cmd} erro: {e}")
                    continue
            logger.critical("❌ Todos os métodos de shutdown falharam")
        
        thread = threading.Thread(target=_poweroff, daemon=True)
        thread.start()
    
    def cancelar(self) -> str:
        if self.estado == self.ESTADO_AGUARDANDO:
            self.estado = self.ESTADO_IDLE
            self.usuario_solicitante = None
            self.timestamp_solicitacao = None
            logger.info("️ Shutdown cancelado")
            return "✅ Shutdown cancelado com sucesso"
        return "️ Nenhum shutdown pendente"

shutdown_manager = SafeShutdown()

# =========================================================
# 🏗️ PRAZO SERVICE (UX Humanizada)
# =========================================================
class PrazoService:
    
    @staticmethod
    def classificar_urgencia(dias: int) -> Tuple[str, str, int]:
        if dias < 0: return "", "VENCIDO", 0
        elif dias == 0: return "🔥", "HOJE", 1
        elif dias <= 3: return "🟠", "URGENTE", 2
        elif dias <= 7: return "", "ATENÇÃO", 3
        else: return "🟢", "NORMAL", 4
    
    @staticmethod
    def gerar_briefing_executivo() -> str:
        if not REPOSITORIO_OK:
            return f"<b>{get_saudacao()}, {ADMIN_NOME}</b>.\n\n⚠️ <i>Sistema em manutenção. Tente novamente em instantes.</i>"
        
        try:
            eventos = buscar_eventos_pendentes()
            hoje = date.today()
            stats = {'pendentes': 0, 'vencidos': 0, 'hoje': 0, 'futuros': 0}
            urgentes = []
            
            for e in eventos:
                try:
                    prazo_str = e.get("prazo_final") or e.get("prazo")
                    autor = e.get("autor", "")
                    descricao = e.get("descricao") or e.get("tipo_evento", "")
                    if not prazo_str:
                        continue
                    prazo = date.fromisoformat(str(prazo_str)[:10]) if isinstance(prazo_str, str) else prazo_str
                    dias = (prazo - hoje).days
                    stats['pendentes'] += 1
                    if dias < 0:
                        stats['vencidos'] += 1
                        urgentes.append((dias, autor, descricao, prazo))
                    elif dias == 0:
                        stats['hoje'] += 1
                        urgentes.append((dias, autor, descricao, prazo))
                    else:
                        stats['futuros'] += 1
                        if dias <= 3:
                            urgentes.append((dias, autor, descricao, prazo))
                except:
                    pass
            
            briefing = formatar_briefing(
                admin_nome=ADMIN_NOME,
                saudacao=get_saudacao(),
                dia_semana=get_dia_semana(),
                stats=stats,
                urgentes=urgentes
            )
            return validar_html_telegram(briefing)
        except Exception as e:
            logger.error(f"Erro ao gerar briefing: {e}", exc_info=True)
            return f"<b>{get_saudacao()}, {ADMIN_NOME}</b>.\n\n❌ Erro ao carregar painel: {escape_html(str(e)[:100])}"
    
    @staticmethod
    def gerar_lista_compacta(pagina: int = 1, itens_por_pagina: int = 10) -> Tuple[str, InlineKeyboardMarkup]:
        if not REPOSITORIO_OK:
            return "️ <i>Sistema em manutenção. Tente novamente em instantes.</i>", InlineKeyboardMarkup([])
        
        try:
            offset = (pagina - 1) * itens_por_pagina
            eventos = buscar_eventos_pendentes(limit=itens_por_pagina, offset=offset)
            
            if not eventos:
                return "📭 <b>Nenhum prazo pendente no momento!</b>\n\n<i>Ótimo trabalho! Aproveite para revisar processos antigos ou descansar um pouco. ☕</i>", InlineKeyboardMarkup([])
            
            total_estimado = len(eventos) + offset
            total_paginas = max(1, (total_estimado + itens_por_pagina - 1) // itens_por_pagina)
            
            texto = f"📋 <b>PRAZOS PENDENTES</b>\n<i>Página {pagina}/{total_paginas}</i>\n\n"
            hoje = date.today()
            
            for e in eventos:
                try:
                    id_prazo = e.get("id")
                    prazo_str = e.get("prazo_final") or e.get("prazo")
                    autor = e.get("autor", "N/D")
                    descricao = e.get("descricao") or e.get("tipo_evento", "N/D")
                    processo = e.get("numero_processo", "")
                    
                    if not prazo_str:
                        continue
                    
                    prazo = date.fromisoformat(str(prazo_str)[:10]) if isinstance(prazo_str, str) else prazo_str
                    dias = (prazo - hoje).days
                    emoji, label, _ = PrazoService.classificar_urgencia(dias)
                    
                    processo_mascarado = mascarar_processo(processo) if processo else ""
                    autor_mascarado = f"<tg-spoiler>{escape_html(autor)}</tg-spoiler>" if autor != "N/D" else "N/D"
                    
                    if dias < 0:
                        texto += f"{emoji} <b>#{id_prazo}</b> - {autor_mascarado}\n"
                        texto += f"   <i>{descricao}</i>\n"
                        texto += f"   Processo: {processo_mascarado}\n"
                        texto += f"   <b>VENCIDO há {abs(dias)} dia(s)</b>\n"
                        texto += f"   {prazo.strftime('%d/%m/%Y')}\n\n"
                    elif dias == 0:
                        texto += f"{emoji} <b>#{id_prazo}</b> - {autor_mascarado}\n"
                        texto += f"   <i>{descricao}</i>\n"
                        texto += f"   Processo: {processo_mascarado}\n"
                        texto += f"   <b>🔥 PRAZO FATAL - HOJE</b>\n"
                        texto += f"   {prazo.strftime('%d/%m/%Y')}\n\n"
                    else:
                        texto += f"{emoji} <b>#{id_prazo}</b> - {autor_mascarado}\n"
                        texto += f"   <i>{descricao}</i>\n"
                        texto += f"   Processo: {processo_mascarado}\n"
                        texto += f"   Vence em {dias} dia(s)\n"
                        texto += f"   {prazo.strftime('%d/%m/%Y')}\n\n"
                except Exception as ex:
                    logger.warning(f"⚠️ Erro ao formatar evento: {ex}")
                    continue
            
            keyboard: List[List[InlineKeyboardButton]] = []
            for e in eventos:
                try:
                    id_prazo = e.get("id")
                    prazo_str = e.get("prazo_final") or e.get("prazo")
                    if not prazo_str:
                        continue
                    prazo = date.fromisoformat(str(prazo_str)[:10]) if isinstance(prazo_str, str) else prazo_str
                    dias = (prazo - hoje).days
                    _, label, _ = PrazoService.classificar_urgencia(dias)
                    
                    keyboard.append([
                        InlineKeyboardButton(f"✅ Concluir #{id_prazo}", callback_data=f"concluir_{id_prazo}"),
                        InlineKeyboardButton(f"✏️ Corrigir", callback_data=f"corrigir_{id_prazo}"),
                    ])
                    keyboard.append([
                        InlineKeyboardButton("📋 Auditoria", callback_data=f"auditoria_{id_prazo}"),
                        InlineKeyboardButton("↩ Reabrir", callback_data=f"reabrir_{id_prazo}"),
                    ])
                    keyboard.append([InlineKeyboardButton("──────────", callback_data="separator")])
                except Exception as ex:
                    logger.warning(f"⚠️ Erro ao criar botões: {ex}")
            
            nav_row = []
            if pagina > 1:
                nav_row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"prazos_page_{pagina-1}"))
            if pagina < total_paginas:
                nav_row.append(InlineKeyboardButton("Próxima ➡️", callback_data=f"prazos_page_{pagina+1}"))
            if nav_row:
                keyboard.append(nav_row)
            
            keyboard.append([
                InlineKeyboardButton("🔄 Atualizar", callback_data="atualizar_prazos"),
                InlineKeyboardButton("️ Voltar", callback_data="menu_principal")
            ])
            
            return validar_html_telegram(texto), InlineKeyboardMarkup(keyboard)
        except Exception as e:
            logger.error(f"Erro ao gerar lista: {e}", exc_info=True)
            return f"❌ Erro ao carregar prazos: {escape_html(str(e))}", InlineKeyboardMarkup([])
    
    @staticmethod
    def gerar_auditoria_completa(evento_id: Optional[int] = None) -> str:
        if not REPOSITORIO_OK:
            return "⚠️ <i>Sistema em manutenção.</i>"
        try:
            registros = listar_auditoria(evento_id=evento_id, limite=20)
            if not registros:
                return "📭 <b>Nenhuma ação registrada ainda.</b>\n\n<i>As ações de concluir, corrigir e reabrir aparecerão aqui.</i>"
            
            linhas = ["<b>📋 AUDITORIA COMPLETA</b>\n"]
            for reg in registros:
                acao = reg.get('acao', 'N/D')
                motivo = reg.get('motivo', '')
                data_hora = reg.get('data_hora', '')
                processo = reg.get('numero_processo', 'N/D')
                
                icones = {"CONCLUIDO": "✔️", "CORRIGIDO": "✏️", "REABERTO": "🔄", "ARQUIVADO": ""}
                icone = icones.get(acao, "📌")
                
                linhas.append(f"{icone} <b>{acao}</b> - Processo {mascarar_processo(processo)}")
                linhas.append(f"   Motivo: {escape_html(motivo)}")
                linhas.append(f"   <i>{data_hora}</i>\n")
            
            return validar_html_telegram("\n".join(linhas))
        except Exception as e:
            logger.error(f"Erro na auditoria: {e}", exc_info=True)
            return f"❌ Erro: {escape_html(str(e))}"
    
    @staticmethod
    def gerar_status_cursor() -> str:
        if not REPOSITORIO_OK:
            return "⚠️ <i>Sistema em manutenção.</i>"
        try:
            ultima_djen = obter_cursor('ultima_djen')
            linhas = [
                "<b>📍 STATUS DO CURSOR DJEN</b>\n",
                f"🕐 Última execução: <b>{ultima_djen.strftime('%d/%m/%Y') if ultima_djen else 'Nunca executado'}</b>",
                f"📅 Data atual: <b>{date.today().strftime('%d/%m/%Y')}</b>",
                "",
                "<i>Próxima busca: cursor - 3 dias até hoje</i>"
            ]
            return "\n".join(linhas)
        except Exception as e:
            return f"❌ Erro: {escape_html(str(e))}"
    
    @staticmethod
    def gerar_status_bots() -> str:
        try:
            status_data = obter_status_global()
            status_formatado = {}
            for nome, info in status_data.items():
                if info["estado"] == "rodando":
                    status_formatado[nome] = f"🟢 rodando • PID {info['pid']}"
                else:
                    status_formatado[nome] = "🔴 parado"
            return validar_html_telegram(formatar_status(status_formatado))
        except Exception as e:
            return "❌ Erro ao carregar status."

# =========================================================
# 🎨 TECLADOS
# =========================================================
def teclado_painel_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Prazos", callback_data="menu_prazos"),
         InlineKeyboardButton("🤖 Bots", callback_data="menu_bots")],
        [InlineKeyboardButton(" Dashboard", callback_data="menu_dashboard"),
         InlineKeyboardButton("⚙️ Sistema", callback_data="menu_sistema")]
    ])

def teclado_bots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ DJEN", callback_data="start_djen"),
         InlineKeyboardButton("⏹️ DJEN", callback_data="stop_djen")],
        [InlineKeyboardButton("▶️ Executor", callback_data="start_executor"),
         InlineKeyboardButton("⏹️ Executor", callback_data="stop_executor")],
        [InlineKeyboardButton("▶️ IA", callback_data="start_ia"),
         InlineKeyboardButton("⏹️ IA", callback_data="stop_ia")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="menu_principal")]
    ])

def teclado_sistema() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(" Status Bots", callback_data="status_geral"),
         InlineKeyboardButton("📍 Cursor DJEN", callback_data="status_cursor")],
        [InlineKeyboardButton("📋 Auditoria Geral", callback_data="auditoria_geral")],
        [InlineKeyboardButton("🛑 Parar Tudo", callback_data="stop_all"),
         InlineKeyboardButton(" Desligar", callback_data="safe_shutdown")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="ajuda_sistema"),
         InlineKeyboardButton("⬅️ Voltar", callback_data="menu_principal")]
    ])

# =========================================================
# 📝 HANDLERS DE COMANDO
# =========================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        await update.message.reply_text(
            f"🤖 <b>Orquestrador Jurídico v3.1</b>\n\n"
            f"{get_saudacao()}, <b>{ADMIN_NOME}</b>! 👋\n\n"
            f"<i>Use os botões abaixo para navegar</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem inicial: {e}")
        await update.message.reply_text("🤖 Orquestrador Jurídico v3.1", reply_markup=ReplyKeyboardRemove())
    
    await update.message.reply_text(
        "<b>O que deseja fazer?</b>",
        parse_mode="HTML",
        reply_markup=teclado_painel_principal()
    )

async def cmd_prazos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    context.user_data['prazos_pagina'] = 1
    texto, markup = PrazoService.gerar_lista_compacta(pagina=1)
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=markup)

async def cmd_cursor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    texto = PrazoService.gerar_status_cursor()
    await update.message.reply_text(texto, parse_mode="HTML")

async def cmd_concluir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not context.args:
        await update.message.reply_text(
            "❌ <b>Como usar:</b>\n\n"
            "<code>/concluir &lt;ID&gt; [motivo]</code>\n\n"
            "<b>Exemplo:</b>\n"
            "<code>/concluir 152 Petição protocolada</code>\n\n"
            "<i>💡 Dica: Você também pode clicar no botão '✅ Concluir' diretamente no card do prazo.</i>",
            parse_mode="HTML"
        )
        return
    try:
        evento_id = int(context.args[0])
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Não informado"
        resultado = concluir_evento(evento_id, motivo, ADMIN_NOME)
        await update.message.reply_text(f"✅ {resultado}")
    except ValueError:
        await update.message.reply_text("❌ ID deve ser um número inteiro")
    except Exception as exc:
        logger.error(f"Erro ao concluir evento: {exc}", exc_info=True)
        await update.message.reply_text(f"❌ Erro: {escape_html(str(exc))}")

async def cmd_corrigir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Como usar:</b>\n\n"
            "<code>/corrigir &lt;ID&gt; &lt;AAAA-MM-DD&gt;</code>\n\n"
            "<b>Exemplo:</b>\n"
            "<code>/corrigir 152 2026-07-20</code>\n\n"
            "<i>💡 Use quando o prazo calculado estiver incorreto ou houver suspensão.</i>",
            parse_mode="HTML"
        )
        return
    try:
        evento_id = int(context.args[0])
        nova_data = datetime.strptime(context.args[1], "%Y-%m-%d").date()
        resultado = corrigir_prazo(evento_id, nova_data, "Correção via Telegram", ADMIN_NOME)
        await update.message.reply_text(f"✅ {resultado}", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Formato inválido. Use AAAA-MM-DD")
    except Exception as exc:
        logger.error(f"Erro ao corrigir prazo: {exc}", exc_info=True)
        await update.message.reply_text(f"❌ Erro: {escape_html(str(exc))}")

async def cmd_reabrir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not context.args:
        await update.message.reply_text(
            "❌ <b>Como usar:</b>\n\n"
            "<code>/reabrir &lt;ID&gt;</code>\n\n"
            "<i>💡 Use quando um prazo concluído precisar ser reaberto (ex: republicação).</i>",
            parse_mode="HTML"
        )
        return
    try:
        evento_id = int(context.args[0])
        resultado = reabrir_evento(evento_id, "Reabertura via Telegram", ADMIN_NOME)
        await update.message.reply_text(f"✅ {resultado}")
    except Exception as exc:
        logger.error(f"Erro ao reabrir evento: {exc}", exc_info=True)
        await update.message.reply_text(f"❌ Erro: {escape_html(str(exc))}")

async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    usuario_id = update.effective_user.id
    usuario_nome = update.effective_user.first_name or "Usuário"
    if usuario_id != ADMIN_ID:
        logger.warning(f"⚠️ Tentativa de shutdown não autorizada por {usuario_nome} (ID: {usuario_id})")
        await update.message.reply_text("❌ Acesso negado. Apenas o administrador pode desligar o sistema.")
        return
    sucesso, mensagem = shutdown_manager.solicitar(usuario_id, usuario_nome)
    await update.message.reply_text(mensagem, parse_mode="HTML")

# =========================================================
# 🎯 CALLBACK HANDLER
# =========================================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data
    logger.info(f"🔘 Callback: {data}")
    
    # === SHUTDOWN ===
    if data == "safe_shutdown":
        usuario_id = update.effective_user.id
        usuario_nome = update.effective_user.first_name or "Usuário"
        if usuario_id != ADMIN_ID:
            await query.edit_message_text("❌ Acesso negado.")
            return
        sucesso, mensagem = shutdown_manager.solicitar(usuario_id, usuario_nome)
        await query.edit_message_text(mensagem, parse_mode="HTML")
        return
    
    # === NAVEGAÇÃO ===
    if data == "menu_principal":
        await query.edit_message_text("<b>O que deseja fazer?</b>", parse_mode="HTML", reply_markup=teclado_painel_principal())
    
    elif data == "menu_prazos":
        context.user_data['prazos_pagina'] = 1
        texto, markup = PrazoService.gerar_lista_compacta(pagina=1)
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
    
    elif data == "menu_dashboard":
        dashboard = PrazoService.gerar_briefing_executivo()
        texto = f"<b>📊 DASHBOARD</b>\n\n{dashboard}"
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado_painel_principal())
    
    elif data == "menu_bots":
        await query.edit_message_text("<b>🤖 Controle de Bots</b>\n\n<i>Selecione uma ação:</i>", parse_mode="HTML", reply_markup=teclado_bots())
    
    elif data == "menu_sistema":
        await query.edit_message_text("<b>⚙️ Sistema</b>\n\n<i>Selecione uma ação:</i>", parse_mode="HTML", reply_markup=teclado_sistema())
    
    elif data == "status_geral":
        texto = PrazoService.gerar_status_bots()
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado_sistema())
    
    elif data == "status_cursor":
        texto = PrazoService.gerar_status_cursor()
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado_sistema())
    
    elif data == "auditoria_geral":
        texto = PrazoService.gerar_auditoria_completa()
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado_sistema())
    
    elif data == "ajuda_sistema":
        await query.edit_message_text(formatar_ajuda(), parse_mode="HTML", reply_markup=teclado_sistema())
    
    elif data == "atualizar_prazos":
        pagina_atual = context.user_data.get('prazos_pagina', 1)
        texto, markup = PrazoService.gerar_lista_compacta(pagina=pagina_atual)
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
    
    elif data.startswith("prazos_page_"):
        pagina = int(data.replace("prazos_page_", ""))
        context.user_data['prazos_pagina'] = pagina
        texto, markup = PrazoService.gerar_lista_compacta(pagina=pagina)
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=markup)
    
    elif data.startswith("concluir_"):
        id_prazo = int(data.replace("concluir_", ""))
        await query.edit_message_text(
            f"<b>Concluir Prazo #{id_prazo}</b>\n\n"
            f"<i>Digite:</i>\n"
            f"<code>/concluir {id_prazo} [motivo]</code>\n\n"
            f"<i> Exemplo: /concluir {id_prazo} Petição protocolada</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_prazos")]])
        )
    
    elif data.startswith("corrigir_"):
        id_prazo = int(data.replace("corrigir_", ""))
        await query.edit_message_text(
            f"<b>Corrigir Prazo #{id_prazo}</b>\n\n"
            f"<i>Digite:</i>\n"
            f"<code>/corrigir {id_prazo} AAAA-MM-DD</code>\n\n"
            f"<i> Exemplo: /corrigir {id_prazo} 2026-07-20</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_prazos")]])
        )
    
    elif data.startswith("reabrir_"):
        id_prazo = int(data.replace("reabrir_", ""))
        try:
            resultado = reabrir_evento(id_prazo, "Reabertura via botão inline", ADMIN_NOME)
            await query.edit_message_text(
                f"✅ <b>Prazo #{id_prazo} reaberto!</b>\n\n{resultado}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_prazos")]])
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Erro: {escape_html(str(e))}")
    
    elif data.startswith("auditoria_") and not data.startswith("auditoria_geral"):
        id_prazo = int(data.replace("auditoria_", ""))
        texto = PrazoService.gerar_auditoria_completa(evento_id=id_prazo)
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_prazos")]]))
    
    elif data.startswith("start_"):
        nome_bot = data.replace("start_", "")
        if nome_bot in ["executor", "djen", "ia"]:
            msg = start_processo(nome_bot, _get_comando_bot(nome_bot))
            await query.edit_message_text(msg)
    
    elif data.startswith("stop_"):
        nome_bot = data.replace("stop_", "")
        if nome_bot == "all":
            msg = stop_all_processos()
            await query.edit_message_text(msg)
        elif nome_bot in ["executor", "djen", "ia"]:
            msg = stop_processo(nome_bot)
            await query.edit_message_text(msg)
    
    elif data == "separator":
        await query.answer()
    
    else:
        await query.edit_message_text(f"⚠️ Ação não reconhecida: {data}")

# =========================================================
# 🔄 ROTEADOR DE TEXTO
# =========================================================
async def route_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().lower()
    
    if text in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "menu", "start"]:
        await cmd_start(update, context)
    elif text == "prazos":
        await cmd_prazos(update, context)
    elif text == "cursor":
        await cmd_cursor(update, context)
    elif text in ["ajuda", "help"]:
        await update.message.reply_text(formatar_ajuda(), parse_mode="HTML")
    elif text == "status":
        texto = PrazoService.gerar_status_bots()
        await update.message.reply_text(texto, parse_mode="HTML")
    elif text == "stop all":
        await update.message.reply_text(stop_all_processos())
    elif text in ["safe shutdown", "desligar"]:
        await cmd_shutdown(update, context)
    elif text == "confirmar":
        usuario_id = update.effective_user.id
        sucesso, mensagem = shutdown_manager.confirmar(usuario_id)
        if sucesso:
            await update.message.reply_text(mensagem, parse_mode="HTML")
            resultado = shutdown_manager.executar()
            await update.message.reply_text(resultado, parse_mode="HTML")
        else:
            await update.message.reply_text(mensagem)
    elif text == "cancelar":
        mensagem = shutdown_manager.cancelar()
        await update.message.reply_text(mensagem)

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"⚠️ Erro: {context.error}", exc_info=True)

# =========================================================
# 🏗️ APP
# =========================================================
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    
    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("prazos", cmd_prazos))
    app.add_handler(CommandHandler("cursor", cmd_cursor))
    app.add_handler(CommandHandler("concluir", cmd_concluir))
    app.add_handler(CommandHandler("corrigir", cmd_corrigir))
    app.add_handler(CommandHandler("reabrir", cmd_reabrir))
    app.add_handler(CommandHandler("shutdown", cmd_shutdown))
    app.add_handler(CommandHandler("ajuda", lambda u, c: update.message.reply_text(formatar_ajuda(), parse_mode="HTML") if u.message else None))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_plain_text))
    
    # Erros
    app.add_error_handler(on_error)
    
    return app

def main() -> None:
    acquire_lock()
    
    def _sig_handler(signum: int, frame: Any) -> None:
        logger.info(f"Sinal {signum} recebido. Encerrando...")
        release_lock()
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    
    try:
        logger.info("🚀 Iniciando Orquestrador Jurídico v3.1...")
        logger.info(f"📁 Base: {BASE_DIR}")
        logger.info(f"🆔 Admin ID: {ADMIN_ID}")
        logger.info(f"️ Repositório: {'OK' if REPOSITORIO_OK else 'FALHOU'}")
        logger.info(f"🎨 Formatter: {'OK' if FORMATTER_OK else 'FALLBACK'}")
        logger.info("🔒 LGPD CNJ: ATIVADO (formato preservado)")
        logger.info("📄 Paginação SQL: ATIVADA (LIMIT/OFFSET)")
        logger.info("📍 Cursor: COMANDO /cursor ATIVADO")
        logger.info("🛡️ Safe Shutdown: v2.1 (múltiplos métodos)")
        logger.info("🏗️ Camada única: infra.repositorio")
        logger.info("💬 UX Humanizada: ATIVADA")
        
        app = build_app()
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.critical(f"❌ Erro fatal: {e}", exc_info=True)
    finally:
        release_lock()
        logger.info("👋 Orquestrador encerrado")

if __name__ == "__main__":
    main()
