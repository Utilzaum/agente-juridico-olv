"""CLI do Assistente de Audiências."""
import argparse
import sys

from . import extractor, ics_builder, notifier, ocr, store, watcher

TEXTO_DEMO = """
ACIJ - ALEXSANDRO BARBOSA MENDES - 0100391-19.2026.5.01.0221 - Reunião
Ter, 04/08/2026 09:10 – 09:40
Audiência Telepresencial: 04/08/2026 09:10 horas
Link da reunião: https://trt1.jus-br.zoom.us/j/9741121755?pwd=CjZMdTJhYXY2UUlxK01pYXBiaWdpdz09
ID da reunião: 974 112 1755
Senha de acesso: 1VTN

10/08/2026 11:00 0809037-52.2024.8.19.0008 1ª Vara Cível da Comarca de Belford Roxo
MARCELA GUIMARAES DOS SANTOS X ÁGUAS DO RIO 4 SPE S.A
PROCEDIMENTO COMUM CÍVEL (7) Conciliação CEJUSC - BELFORD ROXO - SEGUNDA Designada

04/08/2026 15:10 0804733-52.2026.8.19.0036 2º Juizado Especial Cível da Comarca de Nilópolis
BRUNA LARISSA MARTINS DA SILVA X Claro S.A
PROCEDIMENTO DO JUIZADO ESPECIAL CÍVEL (436) Conciliação SALA A Cancelada
"""


def resumo(a):
    l = ["⚖️  " + (a.titulo or "(sem título)")]
    i = a.dt_inicio
    quando = i.strftime("%d/%m/%Y %H:%M") if i else ""
    if a.fim and a.dt_fim:
        quando += " → " + a.dt_fim.strftime("%H:%M")
    campos = [
        ("Processo", a.processo),
        ("Quando", quando),
        ("Modo", a.modalidade),
        ("Órgão", a.orgao),
        ("Sala", a.sala),
        ("Tipo", a.tipo),
        ("Link", a.link),
        ("ID/Senha", (a.meeting_id + " / " + a.senha) if a.meeting_id else ""),
        ("Situação", a.situacao),
    ]
    for nome, valor in campos:
        if valor:
            l.append("    " + nome.ljust(9) + ": " + valor)
    if a.observacoes:
        l.append("    " + a.observacoes)
    return "\n".join(l)


def processar_texto(texto, origem):
    auds = extractor.extrair_audiencias(texto, origem=origem)
    if not auds:
        print("⚠️ Nenhuma audiência identificada no texto/imagem.")
        return
    n_new, n_upd = store.upsert_many(auds)
    for a in auds:
        print(resumo(a), "\n")
    print("💾 %d nova(s), %d atualizada(s)." % (n_new, n_upd))
    out = ics_builder.salvar_agenda(store.listar())
    print("📅 Agenda .ics atualizada: " + str(out))
    notifier.notificar("✅ %d audiência(s) nova(s) capturada(s)." % n_new)


def main():
    p = argparse.ArgumentParser(prog="audiencias")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("img")
    s.add_argument("caminhos", nargs="+")
    s = sub.add_parser("txt")
    s.add_argument("--texto", default="")
    sub.add_parser("listar")
    s = sub.add_parser("ics")
    s.add_argument("--out", default="")
    sub.add_parser("watch")
    sub.add_parser("demo")
    args = p.parse_args()
    if args.cmd == "img":
        for c in args.caminhos:
            print("🔎 OCR de " + c + " ...")
            processar_texto(ocr.ocr_imagem(c), origem=c)
    elif args.cmd == "txt":
        texto = args.texto or sys.stdin.read()
        processar_texto(texto, origem="texto")
    elif args.cmd == "listar":
        for a in store.listar():
            print(resumo(a), "\n")
    elif args.cmd == "ics":
        out = ics_builder.salvar_agenda(store.listar(), args.out)
        print("📅 Gerado: " + str(out))
    elif args.cmd == "watch":
        watcher.loop()
    elif args.cmd == "demo":
        processar_texto(TEXTO_DEMO, origem="demo")
