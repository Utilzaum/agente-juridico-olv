"""Persistência JSON simples com dedup por uid."""
from __future__ import annotations
import json
from pathlib import Path
from typing import List
from .models import Audiencia

DATA_DIR = Path(__file__).resolve().parent / "data"
ARQ = DATA_DIR / "audiencias.json"

def _load() -> List[dict]:
    if not ARQ.exists():
        return []
    return json.loads(ARQ.read_text(encoding="utf-8"))

def _save(regs: List[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(regs, ensure_ascii=False, indent=2), encoding="utf-8")

def listar() -> List[Audiencia]:
    auds = [Audiencia.from_dict(r) for r in _load()]
    return sorted(auds, key=lambda a: a.inicio or "9999")

def upsert_many(novas: List[Audiencia]) -> tuple:
    regs = {r["uid"]: r for r in _load()}
    n_new = n_upd = 0
    for a in novas:
        if a.uid in regs:  # preserva histórico de alertas
            ant = Audiencia.from_dict(regs[a.uid])
            a.alertas_enviados = sorted(set(a.alertas_enviados) | set(ant.alertas_enviados))
            if getattr(ant, "status_revisao", "") == "confirmada":
                a.status_revisao = "confirmada"
            n_upd += 1
        else:
            n_new += 1
        regs[a.uid] = a.to_dict()
        regs[a.uid]["uid"] = a.uid
    _save(list(regs.values()))
    return n_new, n_upd

def marcar_alerta(uid: str, chaves: List[str]):
    regs = _load()
    for r in regs:
        if r.get("uid") == uid:
            r["alertas_enviados"] = sorted(set(r.get("alertas_enviados", [])) | set(chaves))
    _save(regs)


def marcar_revisao(uid, status):
    regs = _load()
    for r in regs:
        if r.get("uid") == uid:
            r["status_revisao"] = status
    _save(regs)


def ajustar_campo(uid, campo, valor):
    from datetime import datetime as _dt
    regs = _load()
    for r in regs:
        if r.get("uid") != uid:
            continue
        if campo == "quando":
            dt = None
            for f in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    dt = _dt.strptime(valor, f)
                    break
                except ValueError:
                    continue
            if not dt:
                return False
            if "%H:%M" not in valor and r.get("inicio"):
                ant = _dt.fromisoformat(r["inicio"])
                dt = dt.replace(hour=ant.hour, minute=ant.minute)
            r["inicio"] = dt.isoformat(timespec="minutes")
        elif campo in r:
            r[campo] = valor
        else:
            return False
        _save(regs)
        return True
    return False
