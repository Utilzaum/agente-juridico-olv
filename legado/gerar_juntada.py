from pathlib import Path
from datetime import datetime
from docxtpl import DocxTemplate
from services.parser_dados import extrair_dados

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "modelo_juntada.docx"
OUTPUT_DIR = BASE_DIR.parent / "temp"
OUTPUT_DIR.mkdir(exist_ok=True)


def gerar_juntada(dados: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template não encontrado: {TEMPLATE_PATH}")

    dados_extraidos = extrair_dados(dados.get("texto", "")) if "texto" in dados else dados

    doc = DocxTemplate(str(TEMPLATE_PATH))

    contexto = {
        "numero_processo": dados_extraidos.get("processo", ""),
        "vara": dados_extraidos.get("comarca", ""),
        "autor": dados_extraidos.get("nome", ""),
        "reu": dados_extraidos.get("reu", ""),
        "documento_juntado": "documento",
        "finalidade": dados_extraidos.get("finalidade", "instrução processual"),
        "cidade": dados_extraidos.get("comarca", "Nilópolis"),
        "data": dados_extraidos.get("data", datetime.now().strftime("%d/%m/%Y")),
    }

    print("📌 JUNTADA:", contexto)

    doc.render(contexto)

    caminho_saida = OUTPUT_DIR / f"juntada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))

    return str(caminho_saida)
