from pathlib import Path
from datetime import datetime
from docxtpl import DocxTemplate
from services.parser_dados import extrair_dados

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "modelo_hipossuficiencia.docx"
OUTPUT_DIR = BASE_DIR.parent / "temp"
OUTPUT_DIR.mkdir(exist_ok=True)


def gerar_hipossuficiencia(dados: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template não encontrado: {TEMPLATE_PATH}")

    dados_extraidos = extrair_dados(dados.get("texto", "")) if "texto" in dados else dados

    doc = DocxTemplate(str(TEMPLATE_PATH))

    contexto = {
        "nome": dados_extraidos.get("nome", ""),
        "nacionalidade": dados_extraidos.get("nacionalidade", ""),
        "estado_civil": dados_extraidos.get("estado_civil", ""),
        "profissao": dados_extraidos.get("profissao", ""),
        "rg": dados_extraidos.get("rg", ""),
        "cpf": dados_extraidos.get("cpf", ""),
        "endereco": dados_extraidos.get("endereco", ""),
        "email": dados_extraidos.get("email", ""),
        "data": dados_extraidos.get("data", datetime.now().strftime("%d/%m/%Y")),
    }

    print("📌 HIPOSSUFICIÊNCIA:", contexto)

    doc.render(contexto)

    caminho_saida = OUTPUT_DIR / f"hipossuficiencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))

    return str(caminho_saida)
