#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestrador Jurídico v3.3 — UX Mobile-First com Lista Enriquecida
✅ CAMADA ÚNICA: infra.repositorio
✅ LISTA ENRIQUECIDA: cada botão mostra #ID | Cliente | Processo | Tipo | Dias
✅ DRILL-DOWN: tocar no botão abre o detalhe com as ações
✅ MOTIVOS RÁPIDOS: conclusão em 1 clique (sem digitar)
✅ MODO CONVERSACIONAL: digita motivo/data só se quiser
✅ PAGINAÇÃO: técnica limit+1 (detecta "próxima" de verdade)
✅ REINICIAR BASE: zera eventos + avança cursor do DJEN para hoje
✅ LGPD: processo mascarado; parte em spoiler no detalhe   <-- [REMOVIDO]
"""
from __future__ import annotations

import os
import sys
import signal
import subprocess
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
    filters, CallbackQueryHandler,
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
        logging.FileHandler(Path(__file__).parent / "logs" / "orquestrador.log", encoding='utf-8'),
    ],
)
logger = logging.getLogger(__name__)

# =========================================================
# ✅ CAMADA ÚNICA: infra.repositorio
# =========================================================
logger.info("=" * 60)
try:
    from infra.repositorio import (
        buscar_eventos_pendentes,
        buscar_evento_por_id,
        concluir_evento,
        corrigir_prazo,
        reabrir_evento,
        listar_concluidos,
        listar_auditoria,
        obter_cursor,
        atualizar_cursor,
        resetar_base,
    )
    REPOSITORIO_OK = True
    logger.info("✅ REPOSITÓRIO CENTRAL carregado (camada única)")
except Exception as e:
    logger.error(f"❌ Erro ao importar repositorio: {e}")
    REPOSITORIO_OK = False

    def buscar_eventos_pendentes(*a, **k): return []
    def buscar_evento_por_id(*a, **k): return None
    def concluir_evento(*a, **k): return "❌ Sistema indisponível no momento"
    def corrigir_prazo(*a, **k): return "❌ Sistema indisponível no momento"
    def reabrir_evento(*a, **k): return "❌ Sistema indisponível no momento"
    def listar_concluidos(*a, **k): return []
    def listar_auditoria(*a, **k): return []
    def obter_cursor(*a, **k): return None
    def atualizar_cursor(*a, **k): None
    def resetar_base(*a, **k): return "❌ Reinicialização indisponível"
logger.info("=" * 60)

# =========================================================
# ✅ CAMADA DE FORMATAÇÃO (telegram_formatter)
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
    def formatar_auditoria(c): return "📋 Auditoria indisponível"
    def formatar_ajuda(): return "📖 Ajuda indisponível"
    def formatar_briefing(**k): return "📊 Briefing indisponível"

# =========================================================
# 🔐 CONFIG
# =========================================================
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_ORQUESTRADOR")
if not TOKEN:
    raise ValueError("⚠️ TOKEN não encontrado")

ADMIN_ID = 501276610
ADMIN_NOME = "Raphael"
ITENS_POR_PAGINA = 6  # 👈 REDUZIDO de 8 para 6 (botões mais largos agora)

MOTIVOS_RAPIDOS: List[Tuple[str, str]] = [
    ("pet", "Petição protocolada"),
    ("audi", "Audiência realizada"),
    ("cumpr", "Prazo cumprido"),
    ("arq", "Arquivado / sem ação"),
]
AJUSTES_RAPIDOS: List[Tuple[str, str]] = [("7", "+7 dias"), ("15", "+15 dias"), ("30", "+30 dias")]

# =========================================================
# 🔒 LOCK
# =========================================================
LOCK_FILE = Path("/tmp/orquestrador_olv.lock")

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _pid_alive(old_pid):
                logger.warning(f"⚠️ Já rodando (PID {old_pid})")
                sys.exit(1)
        except Exception:
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
            logger.warning(f"️ {nome} não respondeu ao SIGTERM, enviando SIGKILL")
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
            resultados.append(stop_processo(nome, timeout))
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
# 🔒 LGPD / HTML
# =========================================================
def escape_html(texto: str) -> str:
    return html_module.escape(str(texto)) if texto else ""

def mascarar_processo(processo: str) -> str:
    """Mantida para compatibilidade, mas não usada na lista/detalhe."""
    if not processo or processo == "N/D":
        return "N/D"
    limpo = "".join(filter(str.isdigit, str(processo)))
    return limpo if limpo else "N/D"

def truncar(texto: str, max_len: int = 18) -> str:
    """Trunca texto longo mantendo começo + reticências."""
    texto = str(texto or "")
    if len(texto) <= max_len:
        return texto
    return texto[:max_len - 1].rstrip() + "…"

# =========================================================
# 🎨 HELPERS
# =========================================================
def get_saudacao() -> str:
    h = datetime.now().hour
    if h < 12: return "☀️ Bom dia"
    if h < 18: return "🌤️ Boa tarde"
    return "🌙 Boa noite"

def get_dia_semana() -> str:
    return ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"][date.today().weekday()]

def validar_html_telegram(texto: str) -> str:
    if not texto:
        return ""
    if len(texto) > 4000:
        texto = texto[:3900] + "\n<i>... (truncado)</i>"
    return texto.replace("<blockquote expandable>", "<blockquote>")

def _parse_data(texto: str) -> Optional[date]:
    texto = texto.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None

def _parse_prazo(evento: Dict[str, Any]) -> Optional[date]:
    prazo_str = evento.get("prazo_final") or evento.get("prazo")
    if not prazo_str:
        return None
    try:
        return date.fromisoformat(str(prazo_str)[:10])
    except Exception:
        return None

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
                return False, f" Aguardando confirmação ({int(self.timeout_confirmacao - decorrido)}s restantes)"
        self.estado = self.ESTADO_AGUARDANDO
        self.usuario_solicitante = usuario_id
        self.timestamp_solicitacao = datetime.now()
        logger.info(f"🛡️ Shutdown solicitado por {usuario_nome} (ID: {usuario_id})")
        return True, (
            f"🛑 <b>CONFIRMAÇÃO DE SHUTDOWN</b>\n"
            f"👤 Solicitado por: <tg-spoiler>{escape_html(usuario_nome)}</tg-spoiler>\n"
            f" {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"<b>Ações:</b>\n1. 🛑 Encerrar bots\n2.  Liberar lock\n"
            f"3. 💾 Fechar banco\n4. ⏻ Desligar o sistema\n\n"
            f"️ <b>Irreversível.</b>\nDigite <code>CONFIRMAR</code> ou <code>CANCELAR</code>."
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
            import gc; gc.collect()
            linhas.append("💾 Conexões fechadas")
            linhas.append("\n<b>5. Desligando sistema...</b>")
            linhas.append("⏻ Sistema será desligado em 5 segundos...")
        except Exception as e:
            logger.error(f"❌ Erro no shutdown: {e}", exc_info=True)
            linhas.append(f" Erro: {escape_html(str(e))}")
        finally:
            self._agendar_poweroff()
        return "\n".join(linhas)

    def _agendar_poweroff(self, delay: int = 5):
        def _poweroff():
            time.sleep(delay)
            logger.critical(" EXECUTANDO POWEROFF")
            for cmd in [["sudo", "systemctl", "poweroff"],
                        ["sudo", "shutdown", "-h", "now"],
                        ["sudo", "poweroff"]]:
                try:
                    subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                    logger.info("✅ Poweroff executado")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ {cmd} falhou: {e}")
            logger.critical("❌ Todos os métodos de shutdown falharam")
        threading.Thread(target=_poweroff, daemon=True).start()

    def cancelar(self) -> str:
        if self.estado == self.ESTADO_AGUARDANDO:
            self.estado = self.ESTADO_IDLE
            self.usuario_solicitante = None
            self.timestamp_solicitacao = None
            logger.info("Shutdown cancelado")
            return "✅ Shutdown cancelado com sucesso"
        return "ℹ️ Nenhum shutdown pendente"

shutdown_manager = SafeShutdown()

# =========================================================
# ️ PRAZO SERVICE (UX Mobile-First + Lista Enriquecida)
# =========================================================
class PrazoService:

    @staticmethod
    def classificar_urgencia(dias: int) -> Tuple[str, str, int]:
        if dias < 0: return "🔴", "VENCIDO", 0
        if dias == 0: return "🔥", "HOJE", 1
        if dias <= 3: return "", "URGENTE", 2
        if dias <= 7: return "🟡", "ATENÇÃO", 3
        return "🟢", "NORMAL", 4

    @staticmethod
    def _relativo(dias: int) -> str:
        if dias < 0: return f"vencido {abs(dias)}d"
        if dias == 0: return "HOJE"
        return f"{dias}d"

    # ---------- LISTA ENRIQUECIDA (1 botão por prazo, com cliente + processo) ----------
    @staticmethod
    def gerar_lista(pagina: int = 1) -> Tuple[str, InlineKeyboardMarkup]:
        if not REPOSITORIO_OK:
            return "⚠️ <i>Sistema em manutenção. Tente novamente em instantes.</i>", InlineKeyboardMarkup([])
        try:
            hoje = date.today()
            offset = (pagina - 1) * ITENS_POR_PAGINA
            rows = buscar_eventos_pendentes(limit=ITENS_POR_PAGINA + 1, offset=offset)
            has_next = len(rows) > ITENS_POR_PAGINA
            rows = rows[:ITENS_POR_PAGINA]
            has_prev = pagina > 1

            if not rows:
                msg = ("📭 <b>Nenhum prazo pendente.</b>\n"
                       "<i>Ótimo trabalho! Aproveite pra descansar um pouco. ☕</i>")
                kb = [[InlineKeyboardButton("🔄 Atualizar", callback_data="atualizar_prazos"),
                       InlineKeyboardButton(" Menu", callback_data="menu_principal")]]
                return msg, InlineKeyboardMarkup(kb)

            linhas = [f"📋 <b>PRAZOS PENDENTES</b> · pág {pagina}",
                      "<i>Toque em um prazo para agir 👇</i>\n"]
            keyboard: List[List[InlineKeyboardButton]] = []

            for e in rows:
                try:
                    id_p = e.get("id")
                    prazo = _parse_prazo(e)
                    if not prazo:
                        continue
                    dias = (prazo - hoje).days
                    emoji, _label, _prio = PrazoService.classificar_urgencia(dias)
                    
                    tipo = escape_html((e.get("descricao") or e.get("tipo_evento") or "Evento")[:20])
                    autor = e.get("autor") or "N/D"
                    # 🔹 REMOVIDO o mascaramento do processo
                    processo = e.get("numero_processo", "N/D")
                    
                    # Linha de texto acima do botão (resumo visual)
                    linhas.append(f"{emoji} <b>#{id_p}</b> · {autor} · {tipo} · <b>{PrazoService._relativo(dias)}</b>")
                    
                    # Botão enriquecido (1 linha, com cliente + processo)
                    btn_text = f"{emoji} #{id_p} | {autor} | Proc: {processo} | {tipo} | {PrazoService._relativo(dias)}"
                    keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ver_{id_p}")])
                except Exception as ex:
                    logger.warning(f"⚠️ Erro ao montar item: {ex}")
                    continue

            nav = []
            if has_prev:
                nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"prazos_page_{pagina-1}"))
            if has_next:
                nav.append(InlineKeyboardButton("Próxima ➡️", callback_data=f"prazos_page_{pagina+1}"))
            if nav:
                keyboard.append(nav)
            keyboard.append([
                InlineKeyboardButton(" Atualizar", callback_data="atualizar_prazos"),
                InlineKeyboardButton("📊 Resumo", callback_data="menu_dashboard"),
                InlineKeyboardButton("🏠 Menu", callback_data="menu_principal"),
            ])
            return validar_html_telegram("\n".join(linhas)), InlineKeyboardMarkup(keyboard)
        except Exception as e:
            logger.error(f"Erro ao gerar lista: {e}", exc_info=True)
            return f"❌ Erro ao carregar prazos: {escape_html(str(e))}", InlineKeyboardMarkup([])

    # ---------- DETALHE (drill-down) ----------
    @staticmethod
    def detalhe(evento_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        if not REPOSITORIO_OK:
            return "⚠️ <i>Sistema em manutenção.</i>", InlineKeyboardMarkup([])
        e = buscar_evento_por_id(evento_id)
        if not e:
            return (f"⚠️ Prazo <b>#{evento_id}</b> não encontrado (pode ter sido concluído).",
                    InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_prazos")]]))
        hoje = date.today()
        prazo = _parse_prazo(e) or hoje
        dias = (prazo - hoje).days
        emoji, label, _prio = PrazoService.classificar_urgencia(dias)
        tipo = escape_html(e.get("tipo_evento") or "Evento")
        desc = escape_html(e.get("descricao") or "")
        # 🔹 REMOVIDO o mascaramento do processo e o spoiler do autor
        processo = e.get("numero_processo", "N/D")
        autor = e.get("autor") or ""
        autor_html = escape_html(autor) if autor and autor != "N/D" else "—"
        data_pub = escape_html(str(e.get("data_publicacao") or "—")[:10])

        texto = (
            f"📌 <b>Prazo #{evento_id}</b>  {emoji} <b>{label}</b>\n\n"
            f"📎 <b>{tipo}</b>\n"
            f"🔢 Processo: <code>{processo}</code>\n"
            f"👤 Parte: {autor_html}\n"
        )
        if desc:
            texto += f"📝 {desc}\n"
        texto += (
            f"\n📅 Publicação: {data_pub}\n"
            f"⏳ Prazo final: <b>{prazo.strftime('%d/%m/%Y')}</b> ({PrazoService._relativo(dias)})\n\n"
            f"<i>Escolha uma ação 👇</i>"
        )
        kb = [
            [InlineKeyboardButton("✅ Concluir", callback_data=f"concluir_{evento_id}"),
             InlineKeyboardButton("✏️ Ajustar prazo", callback_data=f"corrigir_{evento_id}")],
            [InlineKeyboardButton("↩️ Reabrir", callback_data=f"reabrir_{evento_id}"),
             InlineKeyboardButton("📋 Histórico", callback_data=f"aud_{evento_id}")],
            [InlineKeyboardButton("⬅️ Voltar à lista", callback_data="menu_prazos")],
        ]
        return validar_html_telegram(texto), InlineKeyboardMarkup(kb)

    # ---------- MENU DE MOTIVOS RÁPIDOS ----------
    @staticmethod
    def menu_concluir(evento_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        texto = (f"✅ <b>Concluir #{evento_id}</b>\n"
                 f"<i>Toque no motivo (conclui na hora, sem digitar):</i>")
        kb = []
        for cod, desc in MOTIVOS_RAPIDOS:
            kb.append([InlineKeyboardButton(f"✔️ {desc}", callback_data=f"concluir_rapido_{evento_id}_{cod}")])
        kb.append([InlineKeyboardButton("📝 Digitar motivo…", callback_data=f"concluir_digitar_{evento_id}")])
        kb.append([InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_{evento_id}")])
        return texto, InlineKeyboardMarkup(kb)

    # ---------- MENU DE AJUSTE RÁPIDO DE PRAZO ----------
    @staticmethod
    def menu_corrigir(evento_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        e = buscar_evento_por_id(evento_id)
        prazo = _parse_prazo(e) if e else None
        atual = prazo.strftime('%d/%m/%Y') if prazo else "—"
        texto = (
            f"✏️ <b>Ajustar prazo #{evento_id}</b>\n"
            f"Prazo atual: <b>{atual}</b>\n"
            f"<i>Toque para somar dias, ou digite uma data:</i>"
        )
        kb = []
        for d, txt in AJUSTES_RAPIDOS:
            kb.append([InlineKeyboardButton(txt, callback_data=f"corrigir_dias_{evento_id}_{d}")])
        kb.append([InlineKeyboardButton("📅 Digitar data…", callback_data=f"corrigir_digitar_{evento_id}")])
        kb.append([InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_{evento_id}")])
        return texto, InlineKeyboardMarkup(kb)

    # ---------- BRIEFING / STATUS / AUDITORIA ----------
    @staticmethod
    def briefing() -> str:
        if not REPOSITORIO_OK:
            return f"<b>{get_saudacao()}, {ADMIN_NOME}</b>.\n️ <i>Sistema em manutenção.</i>"
        try:
            eventos = buscar_eventos_pendentes(limit=500)
            hoje = date.today()
            stats = {'pendentes': 0, 'vencidos': 0, 'hoje': 0, 'futuros': 0}
            urgentes = []
            for e in eventos:
                prazo = _parse_prazo(e)
                if not prazo:
                    continue
                dias = (prazo - hoje).days
                stats['pendentes'] += 1
                if dias < 0:
                    stats['vencidos'] += 1
                    urgentes.append((dias, e.get("autor", ""), e.get("descricao") or e.get("tipo_evento", ""), prazo))
                elif dias == 0:
                    stats['hoje'] += 1
                    urgentes.append((dias, e.get("autor", ""), e.get("descricao") or e.get("tipo_evento", ""), prazo))
                else:
                    stats['futuros'] += 1
                    if dias <= 3:
                        urgentes.append((dias, e.get("autor", ""), e.get("descricao") or e.get("tipo_evento", ""), prazo))
            briefing = formatar_briefing(admin_nome=ADMIN_NOME, saudacao=get_saudacao(),
                                         dia_semana=get_dia_semana(), stats=stats, urgentes=urgentes)
            return validar_html_telegram(briefing)
        except Exception as e:
            logger.error(f"Erro briefing: {e}", exc_info=True)
            return f"<b>{get_saudacao()}, {ADMIN_NOME}</b>.\n❌ Erro: {escape_html(str(e)[:100])}"

    @staticmethod
    def auditoria(evento_id: Optional[int] = None) -> str:
        if not REPOSITORIO_OK:
            return "⚠️ <i>Sistema em manutenção.</i>"
        try:
            registros = listar_auditoria(evento_id=evento_id, limite=20)
            if not registros:
                return " <b>Nenhuma ação registrada ainda.</b>"
            try:
                return validar_html_telegram(formatar_auditoria(registros))
            except Exception:
                icones = {"CONCLUIDO": "✔️", "CORRIGIDO": "️", "REABERTO": "🔄", "ARQUIVADO": "🗄️"}
                linhas = ["<b>📋 HISTÓRICO</b>\n"]
                for r in registros:
                    acao = r.get('acao', 'N/D')
                    linhas.append(f"{icones.get(acao, '📌')} <b>{acao}</b> · #{r.get('evento_id')} · {mascarar_processo(r.get('numero_processo','N/D'))}")
                    linhas.append(f"   {escape_html(r.get('motivo',''))} · <i>{r.get('data_hora','')[:16]}</i>\n")
                return validar_html_telegram("\n".join(linhas))
        except Exception as e:
            logger.error(f"Erro auditoria: {e}", exc_info=True)
            return f"❌ Erro: {escape_html(str(e))}"

    @staticmethod
    def status_cursor() -> str:
        if not REPOSITORIO_OK:
            return "️ <i>Sistema em manutenção.</i>"
        try:
            ult = obter_cursor('ultima_djen')
            return (
                "<b> CURSOR DJEN</b>\n\n"
                f"🕐 Última execução: <b>{ult.strftime('%d/%m/%Y') if ult else 'Nunca'}</b>\n"
                f"📅 Hoje: <b>{date.today().strftime('%d/%m/%Y')}</b>\n\n"
                "<i>O DJEN busca do cursor−3 dias até hoje.\n"
                "Se estiver trazendo prazos velhos, use ⚙️ → 🧹 Reiniciar base.</i>"
            )
        except Exception as e:
            return f"❌ Erro: {escape_html(str(e))}"

    @staticmethod
    def status_bots() -> str:
        try:
            sf = {}
            for nome, info in obter_status_global().items():
                sf[nome] = f"🟢 rodando • PID {info['pid']}" if info["estado"] == "rodando" else "🔴 parado"
            return validar_html_telegram(formatar_status(sf))
        except Exception:
            return "❌ Erro ao carregar status."

# =========================================================
# 🎨 TECLADOS
# =========================================================
def kb_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Prazos", callback_data="menu_prazos"),
         InlineKeyboardButton("📊 Resumo", callback_data="menu_dashboard")],
        [InlineKeyboardButton("🤖 Bots", callback_data="menu_bots"),
         InlineKeyboardButton("⚙️ Sistema", callback_data="menu_sistema")],
    ])

def kb_bots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ DJEN", callback_data="start_djen"),
         InlineKeyboardButton("⏹️ DJEN", callback_data="stop_djen")],
        [InlineKeyboardButton("▶️ Executor", callback_data="start_executor"),
         InlineKeyboardButton("⏹️ Executor", callback_data="stop_executor")],
        [InlineKeyboardButton("▶️ IA", callback_data="start_ia"),
         InlineKeyboardButton("️ IA", callback_data="stop_ia")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="menu_principal")],
    ])

def kb_sistema() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Status Bots", callback_data="status_geral"),
         InlineKeyboardButton("📍 Cursor DJEN", callback_data="status_cursor")],
        [InlineKeyboardButton("📋 Auditoria Geral", callback_data="auditoria_geral")],
        [InlineKeyboardButton("🛑 Parar Tudo", callback_data="stop_all"),
         InlineKeyboardButton("🧹 Reiniciar base", callback_data="reset_base")],
        [InlineKeyboardButton("⏻ Desligar", callback_data="safe_shutdown"),
         InlineKeyboardButton("❓ Ajuda", callback_data="ajuda_sistema")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="menu_principal")],
    ])

def kb_voltar_lista() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar à lista", callback_data="menu_prazos")]])

# =========================================================
# 🧭 ESTADO CONVERSACIONAL
# =========================================================
def set_aguardando(context, tipo: str, evento_id: int) -> None:
    context.user_data['aguardando'] = {'tipo': tipo, 'id': evento_id}

def get_aguardando(context) -> Optional[Dict[str, Any]]:
    return context.user_data.get('aguardando')

def limpar_aguardando(context) -> None:
    context.user_data.pop('aguardando', None)

# =========================================================
# 📝 HANDLERS DE COMANDO
# =========================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    limpar_aguardando(context)
    await update.message.reply_text(
        f"🤖 <b>Orquestrador Jurídico v3.3</b>\n"
        f"{get_saudacao()}, <b>{ADMIN_NOME}</b>! 👋\n"
        f"<i>Toque nos botões para navegar.</i>",
        parse_mode="HTML", reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text("<b>O que deseja fazer?</b>", parse_mode="HTML", reply_markup=kb_principal())

async def cmd_prazos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    limpar_aguardando(context)
    context.user_data['prazos_pagina'] = 1
    texto, markup = PrazoService.gerar_lista(pagina=1)
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=markup)

async def cmd_cursor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(PrazoService.status_cursor(), parse_mode="HTML")

async def cmd_concluir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text(
            "💡 <b>Dica:</b> o jeito mais rápido é tocar em 📋 Prazos → tocar no prazo → ✅ Concluir.\n\n"
            "Pelo teclado: <code>/concluir &lt;ID&gt; [motivo]</code>",
            parse_mode="HTML")
        return
    try:
        eid = int(context.args[0])
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Concluído via comando"
        await update.message.reply_text(f"✅ {concluir_evento(eid, motivo, ADMIN_NOME)}")
    except ValueError:
        await update.message.reply_text("❌ ID deve ser número inteiro.")

async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id
    nome = update.effective_user.first_name or "Usuário"
    if uid != ADMIN_ID:
        await update.message.reply_text("❌ Acesso negado.")
        return
    _ok, msg = shutdown_manager.solicitar(uid, nome)
    await update.message.reply_text(msg, parse_mode="HTML")

# =========================================================
# 🎯 CALLBACK HANDLER
# =========================================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data
    logger.info(f" Callback: {data}")

    async def edit(text, markup=None, html=True):
        await query.edit_message_text(text, parse_mode="HTML" if html else None, reply_markup=markup)

    if data == "safe_shutdown":
        uid = update.effective_user.id
        nome = update.effective_user.first_name or "Usuário"
        if uid != ADMIN_ID:
            return await edit("❌ Acesso negado.")
        _ok, msg = shutdown_manager.solicitar(uid, nome)
        return await edit(msg)

    if data == "menu_principal":
        limpar_aguardando(context)
        return await edit("<b>O que deseja fazer?</b>", kb_principal())
    if data == "menu_prazos":
        limpar_aguardando(context)
        context.user_data['prazos_pagina'] = 1
        t, m = PrazoService.gerar_lista(1)
        return await edit(t, m)
    if data == "menu_dashboard":
        return await edit(f"<b>📊 RESUMO</b>\n{PrazoService.briefing()}", kb_principal())
    if data == "menu_bots":
        return await edit("<b>🤖 Controle de Bots</b>", kb_bots())
    if data == "menu_sistema":
        return await edit("<b>⚙️ Sistema</b>", kb_sistema())
    if data == "status_geral":
        return await edit(PrazoService.status_bots(), kb_sistema())
    if data == "status_cursor":
        return await edit(PrazoService.status_cursor(), kb_sistema())
    if data == "auditoria_geral":
        return await edit(PrazoService.auditoria(), kb_sistema())
    if data == "ajuda_sistema":
        return await edit(formatar_ajuda(), kb_sistema())

    if data == "atualizar_prazos" or data.startswith("prazos_page_"):
        if data.startswith("prazos_page_"):
            p = int(data.replace("prazos_page_", ""))
            context.user_data['prazos_pagina'] = p
        else:
            p = context.user_data.get('prazos_pagina', 1)
        t, m = PrazoService.gerar_lista(p)
        return await edit(t, m)

    if data.startswith("ver_"):
        limpar_aguardando(context)
        t, m = PrazoService.detalhe(int(data[4:]))
        return await edit(t, m)

    # CONCLUIR (específicos ANTES do genérico)
    if data.startswith("concluir_rapido_"):
        partes = data.split("_")
        eid = int(partes[2]); cod = partes[3]
        motivo = next((d for c, d in MOTIVOS_RAPIDOS if c == cod), "Concluído via botão")
        resultado = concluir_evento(eid, motivo, ADMIN_NOME)
        return await edit(
            f"✅ <b>#{eid} concluído</b>\n<i>{escape_html(motivo)}</i>\n\n{escape_html(resultado)}",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Ver lista atualizada", callback_data="menu_prazos")],
                [InlineKeyboardButton("️ Voltar ao prazo", callback_data=f"ver_{eid}")],
            ]))
    if data.startswith("concluir_digitar_"):
        eid = int(data.replace("concluir_digitar_", ""))
        set_aguardando(context, "motivo", eid)
        return await edit(
            f"✍️ <b>Concluir #{eid}</b>\n\nDigite o motivo e envie.\n"
            f"<i>(Ex.: Petição protocolada em 26/07)</i>",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data=f"ver_{eid}")]]))
    if data.startswith("concluir_"):
        eid = int(data.replace("concluir_", ""))
        t, m = PrazoService.menu_concluir(eid)
        return await edit(t, m)

    # CORRIGIR (específicos ANTES do genérico)
    if data.startswith("corrigir_dias_"):
        partes = data.split("_")
        eid = int(partes[2]); n = int(partes[3])
        e = buscar_evento_por_id(eid)
        prazo = _parse_prazo(e) if e else None
        if not prazo:
            return await edit(f"⚠️ Prazo #{eid} sem data válida.", kb_voltar_lista())
        nova = prazo + timedelta(days=n)
        resultado = corrigir_prazo(eid, nova, f"Ajuste +{n} dias via botão", ADMIN_NOME)
        return await edit(
            f"✏️ <b>#{eid} ajustado</b> → <b>{nova.strftime('%d/%m/%Y')}</b>\n{escape_html(resultado)}",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Ver lista atualizada", callback_data="menu_prazos")],
                [InlineKeyboardButton("⬅️ Voltar ao prazo", callback_data=f"ver_{eid}")],
            ]))
    if data.startswith("corrigir_digitar_"):
        eid = int(data.replace("corrigir_digitar_", ""))
        set_aguardando(context, "data", eid)
        return await edit(
            f"📅 <b>Ajustar prazo #{eid}</b>\n\nDigite a nova data e envie.\n"
            f"<i>Aceita: 2026-08-10, 10/08/2026 ou 10-08-2026</i>",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data=f"ver_{eid}")]]))
    if data.startswith("corrigir_"):
        eid = int(data.replace("corrigir_", ""))
        t, m = PrazoService.menu_corrigir(eid)
        return await edit(t, m)

    if data.startswith("reabrir_"):
        eid = int(data.replace("reabrir_", ""))
        resultado = reabrir_evento(eid, "Reabertura via botão", ADMIN_NOME)
        return await edit(f"↩️ <b>#{eid}</b>\n{escape_html(resultado)}",
                          InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar ao prazo", callback_data=f"ver_{eid}")]]))

    if data.startswith("aud_"):
        eid = int(data.replace("aud_", ""))
        return await edit(PrazoService.auditoria(evento_id=eid),
                          InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar ao prazo", callback_data=f"ver_{eid}")]]))

    if data == "reset_base":
        return await edit(
            "🧹 <b>REINICIAR BASE</b>\n\n"
            "Isso vai:\n• Apagar <b>todos os prazos</b> e o histórico;\n"
            "• Avançar o cursor do DJEN para <b>hoje</b> (ele para de trazer o passado).\n\n"
            "⚠️ <b>Irreversível.</b> Confirma?",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sim, zerar tudo", callback_data="confirmar_reset")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="menu_sistema")],
            ]))
    if data == "confirmar_reset":
        resultado = resetar_base()
        return await edit(f"🧹 <b>Base reiniciada</b>\n{escape_html(str(resultado))}\n\n"
                          f"<i>Use 🤖 → ▶️ DJEN para buscar só publicações recentes.</i>",
                          kb_sistema())

    if data.startswith("start_"):
        nome = data.replace("start_", "")
        if nome in ["executor", "djen", "ia"]:
            return await edit(start_processo(nome, _get_comando_bot(nome)))
    if data.startswith("stop_"):
        nome = data.replace("stop_", "")
        if nome == "all":
            return await edit(stop_all_processos())
        if nome in ["executor", "djen", "ia"]:
            return await edit(stop_processo(nome))

    await query.answer()

# =========================================================
# 🔄 ROTEADOR DE TEXTO
# =========================================================
async def route_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    low = text.lower()

    ag = get_aguardando(context)
    if ag and not text.startswith("/"):
        eid = ag.get('id')
        if low in ("cancelar", "cancel", "sair"):
            limpar_aguardando(context)
            await update.message.reply_text("❌ Operação cancelada.", reply_markup=kb_voltar_lista())
            return
        if ag['tipo'] == "motivo":
            limpar_aguardando(context)
            resultado = concluir_evento(eid, text, ADMIN_NOME)
            await update.message.reply_text(
                f"✅ <b>#{eid} concluído</b>\n<i>{escape_html(text)}</i>\n\n{escape_html(resultado)}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Ver lista", callback_data="menu_prazos")],
                    [InlineKeyboardButton("⬅️ Voltar ao prazo", callback_data=f"ver_{eid}")],
                ]))
            return
        if ag['tipo'] == "data":
            nova = _parse_data(text)
            if not nova:
                await update.message.reply_text(
                    "⚠️ Data não reconhecida. Use <code>2026-08-10</code>, <code>10/08/2026</code> ou <code>10-08-2026</code>.\n"
                    "Digite novamente ou envie <b>cancelar</b>.", parse_mode="HTML")
                return
            limpar_aguardando(context)
            resultado = corrigir_prazo(eid, nova, f"Correção via texto ({text})", ADMIN_NOME)
            await update.message.reply_text(
                f"✏️ <b>#{eid} ajustado</b> → <b>{nova.strftime('%d/%m/%Y')}</b>\n{escape_html(resultado)}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Ver lista", callback_data="menu_prazos")],
                    [InlineKeyboardButton("⬅️ Voltar ao prazo", callback_data=f"ver_{eid}")],
                ]))
            return

    if low in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "menu", "start", "/start"):
        await cmd_start(update, context)
    elif low in ("prazos", "/prazos"):
        await cmd_prazos(update, context)
    elif low in ("cursor", "/cursor"):
        await cmd_cursor(update, context)
    elif low in ("ajuda", "help", "/ajuda"):
        await update.message.reply_text(formatar_ajuda(), parse_mode="HTML")
    elif low == "status":
        await update.message.reply_text(PrazoService.status_bots(), parse_mode="HTML")
    elif low == "resumo":
        await update.message.reply_text(f"<b> RESUMO</b>\n{PrazoService.briefing()}", parse_mode="HTML")
    elif low == "stop all":
        await update.message.reply_text(stop_all_processos())
    elif low in ("safe shutdown", "desligar"):
        await cmd_shutdown(update, context)
    elif low == "confirmar":
        uid = update.effective_user.id
        ok, msg = shutdown_manager.confirmar(uid)
        await update.message.reply_text(msg, parse_mode="HTML")
        if ok:
            await update.message.reply_text(shutdown_manager.executar(), parse_mode="HTML")
    elif low == "cancelar":
        await update.message.reply_text(shutdown_manager.cancelar())

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"⚠️ Erro: {context.error}", exc_info=True)

# =========================================================
# 🏗️ APP
# =========================================================
async def _ajuda_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(formatar_ajuda(), parse_mode="HTML")

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("prazos", cmd_prazos))
    app.add_handler(CommandHandler("cursor", cmd_cursor))
    app.add_handler(CommandHandler("concluir", cmd_concluir))
    app.add_handler(CommandHandler("shutdown", cmd_shutdown))
    app.add_handler(CommandHandler("ajuda", _ajuda_handler))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_plain_text))
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
        logger.info("🚀 Iniciando Orquestrador Jurídico v3.3 (lista enriquecida)...")
        logger.info(f"📁 Base: {BASE_DIR}")
        logger.info(f" Admin ID: {ADMIN_ID}")
        logger.info(f"🗄️  Repositório: {'OK' if REPOSITORIO_OK else 'FALHOU'}")
        logger.info(f" Formatter: {'OK' if FORMATTER_OK else 'FALLBACK'}")
        logger.info(" UX: lista=botões enriquecidos · concluir/corrigir por toque · modo conversacional")
        app = build_app()
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.critical(f" Erro fatal: {e}", exc_info=True)
    finally:
        release_lock()
        logger.info("👋 Orquestrador encerrado")

if __name__ == "__main__":
    main()
