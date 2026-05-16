import subprocess
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def converter_para_pdf(caminho_docx: str) -> str:
    caminho = Path(caminho_docx)

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_docx}")

    output_dir = caminho.parent
    caminho_pdf = caminho.with_suffix(".pdf")

    comandos = ["libreoffice", "soffice"]

    for cmd in comandos:
        try:
            logger.info(f"🚀 Tentando conversão com: {cmd}")

            resultado = subprocess.run(
                [
                    cmd,
                    "--headless",
                    "--invisible",
                    "--norestore",
                    "--nolockcheck",
                    "--nologo",
                    "--nofirststartwizard",
                    "-env:UserInstallation=file:///tmp/libreoffice",
                    "--convert-to", "pdf:writer_pdf_Export",
                    "--outdir", str(output_dir),
                    str(caminho)
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            logger.info(f"📄 [{cmd}] STDOUT:\n{resultado.stdout}")

            if resultado.stderr:
                logger.warning(f"❗ [{cmd}] STDERR:\n{resultado.stderr}")

            # ⏳ Espera inteligente pelo arquivo
            for _ in range(6):
                if caminho_pdf.exists() and caminho_pdf.stat().st_size > 0:
                    logger.info(f"✅ PDF gerado com sucesso: {caminho_pdf}")
                    return str(caminho_pdf)
                time.sleep(0.5)

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ Timeout na conversão com {cmd}")

        except FileNotFoundError:
            logger.warning(f"⚠️ Comando {cmd} não encontrado")

        except Exception as e:
            logger.warning(f"⚠️ Erro inesperado com {cmd}: {e}")

    # ❌ Falha total
    raise RuntimeError(
        f"❌ PDF não foi gerado.\n"
        f"Arquivo: {caminho_docx}\n"
        f"Verifique LibreOffice instalado e funcional."
    )
