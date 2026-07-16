from pathlib import Path
from datetime import datetime
from docxtpl import DocxTemplate
from services.parser_dados import extrair_dados
import json

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "modelo_honorarios.docx"
OUTPUT_DIR = BASE_DIR.parent / "temp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def limpar(v):
    return str(v).strip() if v else ""


def gerar_contrato(dados: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template não encontrado: {TEMPLATE_PATH}")

    # Blindagem de entrada
    if not isinstance(dados, dict):
        dados = {"texto": str(dados)}

    # Entrada híbrida
    if "texto" in dados:
        dados_extraidos = extrair_dados(dados["texto"])
    else:
        dados_extraidos = dados

    doc = DocxTemplate(str(TEMPLATE_PATH))

    contexto = {
        "nome": limpar(dados_extraidos.get("nome")),
        "nacionalidade": limpar(dados_extraidos.get("nacionalidade", "brasileiro")),
        "estado_civil": limpar(dados_extraidos.get("estado_civil")),
        "profissao": limpar(dados_extraidos.get("profissao")),
        "rg": limpar(dados_extraidos.get("rg")),
        "orgao_rg": limpar(dados_extraidos.get("orgao_rg", "SSP")),
        "cpf": limpar(dados_extraidos.get("cpf")),
        "endereco": limpar(dados_extraidos.get("endereco")),
        "email": limpar(dados_extraidos.get("email")),
        "area_juridica": limpar(dados_extraidos.get("area_juridica", "cível")),
        "data": limpar(dados_extraidos.get("data", datetime.now().strftime("%d/%m/%Y"))),
    }

    print("📌 CONTEXTO FINAL (CONTRATO):")
    print(json.dumps(contexto, indent=2, ensure_ascii=False))

    try:
        doc.render(contexto)
    except Exception as e:
        raise RuntimeError(f"Erro ao renderizar template: {e}")

    caminho_saida = OUTPUT_DIR / f"contrato_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))

    return str(caminho_saida)
