from pathlib import Path
from datetime import datetime
from docxtpl import DocxTemplate
from services.parser_dados import extrair_dados

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "modelo_procuracao.docx"
OUTPUT_DIR = BASE_DIR.parent / "temp"
OUTPUT_DIR.mkdir(exist_ok=True)


def gerar_procuracao(dados: dict) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template não encontrado: {TEMPLATE_PATH}")
    
    # Aceita texto bruto OU dados já extraídos
    if "texto" in dados and dados["texto"].strip():
        dados_extraidos = extrair_dados(dados["texto"])
    else:
        dados_extraidos = dados

    doc = DocxTemplate(str(TEMPLATE_PATH))

    # ✅ CHAVES SEM ESPAÇO (crítico para docxtpl)
    contexto = {
        "nome": dados_extraidos.get("nome", ""),
        "cpf": dados_extraidos.get("cpf", ""),
        "endereco": dados_extraidos.get("endereco", ""),
        "data": dados_extraidos.get("data", datetime.now().strftime("%d/%m/%Y")),
    }

    print("📌 DADOS EXTRAÍDOS (PROCURAÇÃO):")
    for k, v in contexto.items():
        print(f"{k}: {v}")

    doc.render(contexto)

    caminho_saida = OUTPUT_DIR / f"procuracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))

    return str(caminho_saida)
