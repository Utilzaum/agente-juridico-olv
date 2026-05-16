import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# 🔧 Configuração para português
CONFIG = r'--oem 3 --psm 6 -l por'

def extrair_texto_imagem(caminho):
    try:
        imagem = Image.open(caminho)
        texto = pytesseract.image_to_string(imagem, config=CONFIG)
        return texto.strip()
    except Exception as e:
        return f"Erro OCR imagem: {str(e)}"


def extrair_texto_pdf(caminho):
    try:
        paginas = convert_from_path(caminho)
        texto_total = ""

        for pagina in paginas:
            texto = pytesseract.image_to_string(pagina, config=CONFIG)
            texto_total += texto + "\n"

        return texto_total.strip()

    except Exception as e:
        return f"Erro OCR PDF: {str(e)}"
