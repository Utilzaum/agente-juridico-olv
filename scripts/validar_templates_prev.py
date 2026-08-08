#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Passo 0 — valida os 4 DOCX do Previdenciário e (opcionalmente) instala no repositório.
Uso:
  python3 scripts/validar_templates_prev.py                      # só valida
  python3 scripts/validar_templates_prev.py --instalar           # valida + copia para services/templates/previdenciario/
  python3 scripts/validar_templates_prev.py "/caminho/da/pasta"  # pasta alternativa
"""
import sys, shutil, zipfile
from pathlib import Path
from docxtpl import DocxTemplate

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "services" / "templates" / "previdenciario"

TEMPLATES = [
    "procuracao_previdenciaria.docx",
    "declaracao_de_hipossuficiencia.docx",
    "renuncia_teto_juizado.docx",
    "contrato_honorarios_previdenciario.docx",
]
PLACEHOLDERS = ["nome", "nacionalidade", "estado_civil", "profissao",
                "cpf", "data_nascimento", "endereco", "email", "data"]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    instalar = "--instalar" in sys.argv
    pasta = Path(args[0]) if args else Path.home() / "Downloads" / "DOCUMENTOS - RASCUNHOS"
    tudo_ok = True

    for nome in TEMPLATES:
        arq = pasta / nome
        print(f"\n=== {nome} ===")
        if not arq.exists():
            print("  ❌ arquivo não encontrado"); tudo_ok = False; continue

        # Juiz definitivo: o parser do próprio docxtpl
        try:
            doc = DocxTemplate(str(arq))
            encontradas = set(doc.get_undeclared_template_variables())
        except Exception as e:
            print(f"  ❌ docxtpl não conseguiu abrir: {e}"); tudo_ok = False; continue

        faltando = [p for p in PLACEHOLDERS if p not in encontradas]
        extras   = sorted(encontradas - set(PLACEHOLDERS))

        if not faltando and not extras:
            print(f"  ✅ íntegro — {len(PLACEHOLDERS)}/9 placeholders OK")
            if instalar:
                DESTINO.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arq, DESTINO / nome)
                print(f"  📦 instalado em {DESTINO / nome}")
        else:
            tudo_ok = False
            if faltando: print(f"  ❌ faltando: {', '.join(faltando)}")
            if extras:   print(f"  ⚠️ placeholders fora do contrato: {', '.join(extras)}")
            print("  🔧 correção: abra o .odt, apague o placeholder e redigite de uma vez, reexporte .docx")

    print("\n" + ("✅ TUDO PRONTO para o bot." if tudo_ok else "❌ HÁ PROBLEMAS — corrija antes de subir o bot."))
    sys.exit(0 if tudo_ok else 1)

if __name__ == "__main__":
    main()
