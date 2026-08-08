"""Loop de alertas com antecedência (24h / 1h / 15min), sem repetir aviso."""
from __future__ import annotations
import time
from datetime import datetime
from . import notifier, store

LIMIARES = [(15, "🚨", "EM 15 MINUTOS"), (60, "⏰", "EM 1 HORA"), (1440, "📅", "AMANHÃ (24h)")]

def _msg(a, rotulo: str) -> str:
    i = a.dt_inicio
    linhas = [f"{rotulo} — AUDIÊNCIA {a.tipo or ''} {a.modalidade or ''}".strip(),
              f"⚖️ {a.titulo or a.processo or '(sem título)'}",
              f"📅 {i:%d/%m/%Y %H:%M}" + (f" → {a.dt_fim:%H:%M}" if a.fim else "")]
    if a.orgao:  linhas.append(f"🏛 {a.orgao}")
    if a.sala:   linhas.append(f"📍 {a.sala}")
    if a.link:   linhas.append(f"🔗 {a.link}")
    if a.meeting_id: linhas.append(f"🆔 {a.meeting_id}  🔑 {a.senha}")
    return "\n".join(linhas)

def verificar() -> int:
    agora = datetime.now()
    n = 0
    for a in store.listar():
        if a.situacao.lower().startswith(("cancel", "realiz")):
            continue
        if "Horário não identificado" in (a.observacoes or ""):
            continue
        if a.status_revisao != "confirmada":
            continue
        i = a.dt_inicio
        if not i:
            continue
        delta = (i - agora).total_seconds() / 60
        if delta < -30:
            continue
        escolhido = None
        for lim, emoji, rotulo in LIMIARES:          # crescente → pega o menor aplicável
            if delta <= lim:
                escolhido = (lim, emoji, rotulo)
                break
        if not escolhido:
            continue
        lim, emoji, rotulo = escolhido
        if str(lim) in a.alertas_enviados:
            continue
        notifier.notificar(f"{emoji} {_msg(a, rotulo)}")
        store.marcar_alerta(a.uid, [str(l) for l, _, _ in LIMIARES if l >= lim])
        n += 1
    return n

def loop(intervalo: int = 30):
    print("👂 Watcher de audiências ativo (Ctrl+C para sair)...")
    while True:
        try:
            verificar()
        except Exception as e:
            print(f"[watcher] erro: {e}")
        time.sleep(intervalo)
