"""Bot de Audiências — UI conversacional no Telegram.
Recebe foto/print (OCR) ou texto, extrai audiências, salva,
responde com resumo + .ics e roda o watcher de alertas em 2ª thread.
"""
import os
import time
import logging
import threading

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from audiencias import extractor, ics_builder, notifier, ocr, store, watcher
from audiencias import protocolo

load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("audiencias")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_AUDIENCIA")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN_AUDIENCIA não encontrado no .env")

bot = telebot.TeleBot(TOKEN)

HELP = """⚖️ ASSISTENTE DE AUDIÊNCIAS
📷 Mande o print/foto da pauta, do e-mail ou da decisão: eu faço o OCR, extraio os dados e abro a REVISÃO FINAL.
✍️ Ou cole o texto direto.
⏳ Na revisão, use os botões do card:
✅ Confirmar - entra na agenda e no radar de alertas
✏️ Ajustar - corrige campo por campo
🗑️ Descartar - mata fantasmas/duplicatas
📅 .ics só desta - arquivo com 1 agendamento
/revisar - pendentes aguardando confirmação
/listar - tudo que está salvo
/ics - agenda completa (.ics)
/addemail email [processo] - destinatário do convite
/emails - ver destinatários · /rememail - remover
/ajuda - esta mensagem
🔔 Alertas automáticos: 24h / 1h / 15min antes de cada audiência confirmada."""


def resumo(a):
    l = ["⚖️ " + protocolo.montar_titulo(a)]
    i = a.dt_inicio
    quando = i.strftime("%d/%m/%Y %H:%M") if i else ""
    if a.fim and a.dt_fim:
        quando += " → " + a.dt_fim.strftime("%H:%M")
    campos = [
        ("Processo", a.processo), ("Quando", quando), ("Modo", a.modalidade),
        ("Órgão", a.orgao), ("Sala", a.sala), ("Tipo", a.tipo),
        ("Link", a.link),
        ("ID/Senha", (a.meeting_id + " / " + a.senha) if a.meeting_id else ""),
        ("Situação", a.situacao),
    ]
    for nome, valor in campos:
        if valor:
            l.append("• " + nome + ": " + valor)
    if a.observacoes:
        l.append(a.observacoes)
    return "\n".join(l)


def _audiencias_confirmadas():
    confirmadas = []
    for a in store.listar():
        status = str(getattr(a, "status_revisao", "") or "confirmada").strip()
        if status == "confirmada":
            confirmadas.append(a)
    return confirmadas


def enviar_ics(chat_id):
    out = ics_builder.salvar_agenda(_audiencias_confirmadas())
    with open(str(out), "rb") as f:
        bot.send_document(chat_id, f)


def processar_texto(texto, chat_id, origem):
    auds = extractor.extrair_audiencias(texto, origem=origem)
    if not auds:
        bot.send_message(chat_id, "⚠️ Não encontrei audiência aqui. "
                         "Tente um print mais nítido ou cole o texto.")
        return
    store.upsert_many(auds)
    for a in auds:
        bot.send_message(chat_id, resumo(a))
    _enviar_cards(auds, chat_id)
    bot.send_message(chat_id, "⏳ %d audiência(s) aguardando revisão final. "
                     "Confirme no card para entrar na agenda e nos alertas." % len(auds))


@bot.message_handler(commands=["start", "ajuda", "help"])
def cmd_start(m):
    bot.reply_to(m, HELP)


@bot.message_handler(commands=["listar"])
def cmd_listar(m):
    auds = store.listar()
    if not auds:
        bot.reply_to(m, "📭 Nenhuma audiência agendada.")
        return
    for a in auds:
        bot.reply_to(m, resumo(a))


@bot.message_handler(commands=["ics"])
def cmd_ics(m):
    enviar_ics(m.chat.id)


@bot.message_handler(content_types=["photo"])
def receber_foto(m):
    aviso = bot.reply_to(m, "🔎 OCR em andamento...")
    try:
        file_id = m.photo[-1].file_id
        info = bot.get_file(file_id)
        url = "https://api.telegram.org/file/bot" + TOKEN + "/" + info.file_path
        import requests as _rq
        r = _rq.get(url, timeout=120)
        r.raise_for_status()
        conteudo = r.content
        os.makedirs(os.path.join("audiencias", "data"), exist_ok=True)
        tmp = os.path.join("audiencias", "data",
                           "tmp_%s.png" % m.message_id)
        with open(tmp, "wb") as f:
            f.write(conteudo)
        texto = ocr.ocr_imagem(tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass
        processar_texto(texto, m.chat.id,
                        origem="telegram_foto_%s" % m.message_id)
    except Exception as e:
        logger.error("erro na foto: %s", e)
        bot.send_message(m.chat.id, "❌ Falha no OCR: %s" % e)
    finally:
        try:
            bot.delete_message(m.chat.id, aviso.message_id)
        except Exception:
            pass


@bot.message_handler(func=lambda m: m.text is not None)
def receber_texto(m):
    if m.text.startswith("/"):
        return
    processar_texto(m.text, m.chat.id, origem="telegram_texto")


def _bater_coracao():
    try:
        import json as _json
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audiencias", "data")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "heartbeat.json"), "w") as f:
            _json.dump({"pid": os.getpid(), "ts": time.time()}, f)
    except Exception as e:
        logger.warning("heartbeat falhou: %s", e)

def _loop_watch():
    while True:
        try:
            watcher.verificar()
        except Exception as e:
            logger.error("watcher: %s", e)
        _bater_coracao()
        time.sleep(30)


CAMPOS_AJUSTE = ["quando", "titulo", "orgao", "sala", "tipo", "situacao", "link"]


def _card_revisao(a):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Confirmar", callback_data="rev_ok_" + a.uid),
           InlineKeyboardButton("🗑️ Descartar", callback_data="rev_drop_" + a.uid),
           InlineKeyboardButton("✏️ Ajustar", callback_data="rev_edit_" + a.uid))
    kb.row(InlineKeyboardButton("📅 .ics só desta", callback_data="ics1_" + a.uid))
    return kb


def _enviar_cards(auds, chat_id):
    for a in auds:
        if a.status_revisao == "pendente":
            bot.send_message(chat_id, "⏳ REVISÃO FINAL — confira antes do .ics:\n\n" + resumo(a), reply_markup=_card_revisao(a))


@bot.message_handler(commands=["revisar"])
def cmd_revisar(m):
    pend = [a for a in store.listar() if a.status_revisao == "pendente"]
    if not pend:
        bot.reply_to(m, "✅ Nada pendente de revisão.")
        return
    _enviar_cards(pend, m.chat.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("rev_"))
def cb_revisao(call):
    uid = call.data.split("_")[-1]
    aud = next((x for x in store.listar() if x.uid == uid), None)
    if not aud:
        bot.answer_callback_query(call.id, "Não encontrada")
        return
    if call.data.startswith("rev_ok_"):
        store.marcar_revisao(uid, "confirmada")
        ics_builder.salvar_agenda(_audiencias_confirmadas())
        bot.answer_callback_query(call.id, "Confirmada ✅")
        bot.edit_message_text("✅ Na agenda e no radar de alertas:\n\n" + resumo(aud),
                              call.message.chat.id, call.message.message_id)
    elif call.data.startswith("rev_drop_"):
        store.marcar_revisao(uid, "descartada")
        bot.answer_callback_query(call.id, "Descartada 🗑️")
        bot.edit_message_text("🗑️ Descartada — não entra na agenda.",
                              call.message.chat.id, call.message.message_id)
    elif call.data.startswith("rev_edit_"):
        kb = InlineKeyboardMarkup()
        kb.row(*[InlineKeyboardButton(c.title(), callback_data="aj_" + uid + "_" + c) for c in CAMPOS_AJUSTE[:4]])
        kb.row(*[InlineKeyboardButton(c.title(), callback_data="aj_" + uid + "_" + c) for c in CAMPOS_AJUSTE[4:]])
        bot.edit_message_text("✏️ " + resumo(aud) + "\n\nToque no campo a ajustar:",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("aj_"))
def cb_ajuste(call):
    _, uid, campo = call.data.split("_", 2)
    msg = bot.edit_message_text("✏️ Campo: " + campo + "\nEnvie o novo valor (ou 'cancelar'):",
                                call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, _receber_ajuste, uid, campo)


def _receber_ajuste(m, uid, campo):
    v = (m.text or "").strip()
    if v.lower() in ("cancelar", "cancel"):
        bot.reply_to(m, "❌ Ajuste cancelado.")
        return
    ok = store.ajustar_campo(uid, campo, v)
    bot.reply_to(m, "✅ Campo atualizado. Use /revisar para ver o card." if ok
                 else "❌ Valor não reconhecido. Para 'quando', use dd/mm/aaaa hh:mm.")



if __name__ == "__main__":
    import atexit
    if os.path.exists("/tmp/bot_audiencias.lock"):
        try:
            _old = int(open("/tmp/bot_audiencias.lock").read().strip())
            os.kill(_old, 0)
            logger.warning("⚠️ Outro bot_audiencias ativo (PID %s); saindo.", _old)
            raise SystemExit(1)
        except (ValueError, ProcessLookupError):
            pass
    open("/tmp/bot_audiencias.lock", "w").write(str(os.getpid()))
    atexit.register(lambda: os.path.exists("/tmp/bot_audiencias.lock") and os.remove("/tmp/bot_audiencias.lock"))
    logger.info("🚀 Bot de Audiências no ar + watcher de alertas")
    threading.Thread(target=_loop_watch, daemon=True).start()
    _bater_coracao()
    try:
        notifier.notificar("✅ Bot de Audiências ONLINE — watcher ativo (alertas 24h/1h/15min). Pode mandar print da pauta! 📷")
    except Exception as e:
        logger.warning("aviso de startup falhou: %s", e)
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.warning("queda de conexão: %s", e)
            time.sleep(5)