#!/usr/bin/env python3
"""
Bot de Petições Jurídicas - Telegram
Arquitetura: OCR Local + LLM (Qwen) + Regex Fallback
Execução: python -m core.bot_peticoes (a partir da raiz do projeto)
"""

import os
import sys
import re
import json
import time
import requests
from datetime import datetime
from docx import Document
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# 🔥 IMPORTS CORRIGIDOS
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.bot_ocr import extrair_texto_do_arquivo
    from core.parser_juridico import extrair_dados
else:
    from .bot_ocr import extrair_texto_do_arquivo
    from .parser_juridico import extrair_dados

# ==============================
# CONFIG
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_PETICOES")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_OCR = "qwen2.5:7b-instruct-q4_K_M"

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN_PETICOES não definido!")

# ==============================
# ESTADO SIMPLES
# ==============================
user_state = {}

# ==============================
# CLASSIFICAÇÃO JURÍDICA
# ==============================

TIPOS_ACAO = {
    "manifestacao": {
        "descricao": "Manifestação",
        "verbo": "apresentar manifestação",
        "acao": "apresenta sua manifestação"
    },
    "juntada": {
        "descricao": "Juntada de Documentos",
        "verbo": "proceder à juntada de documentos",
        "acao": "procede à juntada do(s) documento(s)"
    },
    "emenda": {
        "descricao": "Emenda à Inicial",
        "verbo": "emendar a petição inicial",
        "acao": "apresenta a competente emenda à inicial"
    },
    "impugnacao": {
        "descricao": "Impugnação",
        "verbo": "apresentar impugnação",
        "acao": "oferece sua impugnação"
    },
    "replica": {
        "descricao": "Réplica",
        "verbo": "apresentar réplica",
        "acao": "oferece sua réplica à contestação"
    },
    "cumprimento": {
        "descricao": "Cumprimento de Determinação",
        "verbo": "cumprir determinação judicial",
        "acao": "vem cumprir a determinação judicial"
    }
}


# ==============================
# UTILITÁRIOS
# ==============================

def chamar_ollama(payload, tentativas=3, delay=2):
    """Chama API Ollama com retry automático"""
    for tentativa in range(tentativas):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                if "response" not in data:
                    raise Exception(f"Ollama retornou resposta sem 'response': {data}")
                return data
            else:
                print(f"⚠️ Tentativa {tentativa+1}: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout na tentativa {tentativa+1}")
        except requests.exceptions.ConnectionError:
            print(f"🔌 Erro de conexão na tentativa {tentativa+1}")
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa+1}: {e}")
        
        if tentativa < tentativas - 1:
            time.sleep(delay * (tentativa + 1))
    
    raise Exception(f"Falha ao comunicar com Ollama após {tentativas} tentativas")


def extrair_json_seguro(texto):
    """Extrai JSON de resposta LLM com múltiplas estratégias"""
    # Estratégia 1: Regex para bloco JSON
    match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    
    # Estratégia 2: Busca por chaves específicas
    dados = {}
    campos = {
        'numero_processo': [r'"numero_processo"\s*:\s*"([^"]*)"'],
        'autor': [r'"autor"\s*:\s*"([^"]*)"'],
        'reu': [r'"reu"\s*:\s*"([^"]*)"'],
        'tipo_acao': [r'"tipo_acao"\s*:\s*"([^"]*)"'],
        'contexto': [r'"contexto"\s*:\s*"([^"]*)"'],
        'prazo': [r'"prazo"\s*:\s*"([^"]*)"']
    }
    
    for campo, padroes in campos.items():
        for padrao in padroes:
            match = re.search(padrao, texto)
            if match:
                dados[campo] = match.group(1)
                break
    
    return dados if dados else {}


# ==============================
# ANÁLISE JURÍDICA (NOVA!)
# ==============================

def classificar_despacho(texto_ocr):
    """
    CLASSIFICA o despacho em vez de apenas extrair dados
    Retorna: tipo_acao, contexto, prazo
    """
    prompt_classificacao = f"""
Você é um advogado especializado em direito processual civil.

Analise o despacho judicial abaixo e CLASSIFIQUE a natureza da determinação:

TEXTO DO DESPACHO:
{texto_ocr[:3000]}

CLASSIFICAÇÕES POSSÍVEIS:
- manifestacao: juiz pede para a parte se manifestar sobre algo
- juntada: juiz determina juntada de documentos
- emenda: juiz determina emenda à inicial
- impugnacao: juiz abre prazo para impugnação
- replica: juiz abre prazo para réplica
- cumprimento: determinação genérica para cumprir algo

EXTRAIA:
1. numero_processo: número CNJ completo
2. autor: nome da parte autora
3. reu: nome da parte ré
4. tipo_acao: classificação da determinação (use APENAS as opções acima)
5. contexto: resumo OBJETIVO do que o juiz determinou (NÃO transcreva o despacho)
6. prazo: prazo processual mencionado (se houver)

Responda APENAS com JSON válido, sem markdown.

Formato:
{{"numero_processo": "...", "autor": "...", "reu": "...", "tipo_acao": "juntada", "contexto": "O juiz determinou a juntada de documentos comprobatórios", "prazo": "15 dias"}}
"""
    
    try:
        data = chamar_ollama({
            "model": MODEL_OCR,
            "prompt": prompt_classificacao,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500,
                "top_p": 0.9
            }
        })
        
        resposta_llm = data["response"]
        print(f"🤖 Classificação LLM: {resposta_llm[:200]}...")
        
        dados_llm = extrair_json_seguro(resposta_llm)
        return dados_llm
        
    except Exception as e:
        print(f"⚠️ LLM falhou na classificação: {e}")
        return {}


def analisar_documento(caminho_arquivo):
    """
    Pipeline jurídico completo
    """
    print(f"📄 Analisando: {caminho_arquivo}")
    
    # 1. OCR LOCAL
    try:
        texto_ocr = extrair_texto_do_arquivo(caminho_arquivo)
    except Exception as e:
        raise Exception(f"Falha no OCR: {str(e)}")
    
    if not texto_ocr or len(texto_ocr.strip()) < 10:
        raise Exception("OCR não retornou texto suficiente")
    
    print(f"📝 Texto OCR: {len(texto_ocr)} caracteres")
    
    # 2. CLASSIFICAÇÃO JURÍDICA (LLM)
    dados_llm = classificar_despacho(texto_ocr)
    
    # 3. FALLBACK REGEX (SEMPRE)
    try:
        dados_regex = extrair_dados(texto_ocr)
        print(f"📊 Dados regex: {dados_regex}")
    except Exception as e:
        print(f"⚠️ Erro no regex fallback: {e}")
        dados_regex = {}
    
    # 4. FUSÃO INTELIGENTE (LLM tem prioridade)
    dados_finais = {
        "numero_processo": dados_llm.get("numero_processo") or dados_regex.get("numero_processo", ""),
        "autor": dados_llm.get("autor") or dados_regex.get("autor", ""),
        "reu": dados_llm.get("reu") or dados_regex.get("reu", ""),
        "tipo_acao": dados_llm.get("tipo_acao", "cumprimento"),
        "contexto": dados_llm.get("contexto", "cumprimento de determinação judicial"),
        "prazo": dados_llm.get("prazo", "")
    }
    
    # Validação do tipo_acao
    if dados_finais["tipo_acao"] not in TIPOS_ACAO:
        dados_finais["tipo_acao"] = "cumprimento"
    
    # Limpeza
    for k in dados_finais:
        if isinstance(dados_finais[k], str):
            dados_finais[k] = dados_finais[k].strip()
    
    print(f"🎯 Dados finais: {dados_finais}")
    return dados_finais


# ==============================
# GERAR PETIÇÃO (JURIDICAMENTE CORRETA)
# ==============================

def gerar_peticao(dados, fundamentacao_extra=""):
    """
    Gera petição CORRETA - NUNCA transcreve o despacho
    """
    meses = {
        'January': 'janeiro', 'February': 'fevereiro', 'March': 'março',
        'April': 'abril', 'May': 'maio', 'June': 'junho',
        'July': 'julho', 'August': 'agosto', 'September': 'setembro',
        'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'
    }
    
    data_formatada = datetime.now().strftime('%d de %B de %Y')
    for en, pt in meses.items():
        data_formatada = data_formatada.replace(en, pt)
    
    # 🔥 DADOS JURÍDICOS CORRETOS
    tipo_acao = dados.get('tipo_acao', 'cumprimento')
    acao_info = TIPOS_ACAO.get(tipo_acao, TIPOS_ACAO['cumprimento'])
    contexto = dados.get('contexto', '')
    prazo = dados.get('prazo', '')
    
    # 🔥 CONSTRUÇÃO DA PETIÇÃO (advogado falando!)
    template = f"""EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO DA VARA CÍVEL DA COMARCA DE NILÓPOLIS/RJ

PROCESSO Nº {dados.get('numero_processo', 'Nº INDISPONÍVEL')}

{dados.get('autor', 'PARTE AUTORA')}, já qualificado(a) nos autos do processo em epígrafe, que move em face de {dados.get('reu', 'PARTE RÉ')}, por intermédio de seu advogado que esta subscreve, vem, respeitosamente, à presença de Vossa Excelência, em atenção ao despacho de fls., apresentar {acao_info['descricao'].upper()}, nos termos que seguem.
"""
    
    # 🔥 CORPO DA PETIÇÃO BASEADO NO TIPO DE AÇÃO
    if tipo_acao == "manifestacao":
        template += f"""
1. DA MANIFESTAÇÃO

Em atenção à determinação deste D. Juízo, o Autor {acao_info['acao']} quanto ao ponto especificado, entendendo pertinente destacar que {contexto}.
"""
    elif tipo_acao == "juntada":
        template += f"""
1. DA JUNTADA DE DOCUMENTOS

Em atenção ao despacho, o Autor {acao_info['acao']} solicitado(s), os quais comprovam o quanto determinado por este Juízo.
"""
    elif tipo_acao == "emenda":
        template += f"""
1. DA EMENDA À INICIAL

Em cumprimento à determinação judicial, o Autor {acao_info['acao']}, promovendo as correções apontadas com o fito de regularizar o processamento do feito.
"""
    elif tipo_acao == "impugnacao":
        template += f"""
1. DA IMPUGNAÇÃO

No prazo concedido, o Autor {acao_info['acao']}, demonstrando as inconsistências apontadas no despacho que determinou a presente manifestação.
"""
    elif tipo_acao == "replica":
        template += f"""
1. DA RÉPLICA

Tempestivamente, o Autor {acao_info['acao']}, rebatendo os argumentos apresentados pela parte contrária.
"""
    else:  # cumprimento genérico
        template += f"""
1. DO CUMPRIMENTO

Em atenção ao despacho, o Autor {acao_info['acao']}, na forma e para os fins determinados.
"""
    
    # 🔥 FUNDAMENTAÇÃO EXTRA (se fornecida pelo usuário)
    if fundamentacao_extra:
        template += f"""
2. DA FUNDAMENTAÇÃO JURÍDICA

Neste sentido, cumpre destacar que {fundamentacao_extra}
"""
        num_pedido = 3
    else:
        num_pedido = 2
    
    # 🔥 FECHAMENTO PADRÃO
    template += f"""
{num_pedido}. DO PEDIDO

Diante do exposto, requer:

a) O recebimento da presente {acao_info['descricao'].lower()}, para que produza seus regulares efeitos legais e processuais;

b) O regular processamento do feito, nos termos da legislação aplicável.

Termos em que,
Pede deferimento.

Nilópolis/RJ, {data_formatada}.

RAPHAEL VITOR ARAGÃO DE OLIVEIRA
OAB/RJ 176.629
"""
    return template


# ==============================
# GERAR DOCX
# ==============================

def gerar_docx(texto, caminho):
    """Gera arquivo DOCX formatado"""
    doc = Document()
    
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = 12
    
    for linha in texto.split("\n"):
        if linha.strip():
            p = doc.add_paragraph(linha.strip())
            if any(palavra in linha.upper() for palavra in ['EXCELENTÍSSIMO', 'PROCESSO Nº']):
                for run in p.runs:
                    run.bold = True
    
    doc.save(caminho)
    print(f"📄 DOCX salvo: {caminho}")


# ==============================
# HANDLERS TELEGRAM
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "📸 **BOT DE PETIÇÕES JURÍDICAS**\n\n"
        "Envie a imagem ou PDF do despacho judicial.\n"
        "O bot irá CLASSIFICAR a determinação e gerar a petição adequada.\n\n"
        "🔹 Formatos aceitos: JPG, PNG, PDF\n"
        "🔹 Processamento: OCR + IA Jurídica\n\n"
        "⚖️ **Tipos de petição geradas:**\n"
        "• Manifestação\n"
        "• Juntada de Documentos\n"
        "• Emenda à Inicial\n"
        "• Impugnação\n"
        "• Réplica\n"
        "• Cumprimento de Determinação\n\n"
        "Desenvolvido por Raphael Vitor - OAB/RJ 176.629",
        parse_mode='Markdown'
    )


async def receber_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe foto ou documento"""
    user_id = update.message.from_user.id
    caminho = None
    
    try:
        # Download do arquivo
        if update.message.photo:
            foto = update.message.photo[-1]
            file = await foto.get_file()
            extensao = '.jpg'
        elif update.message.document:
            doc = update.message.document
            file = await doc.get_file()
            extensao = os.path.splitext(doc.file_name)[1].lower()
            
            if extensao not in ['.jpg', '.jpeg', '.png', '.pdf']:
                await update.message.reply_text("⚠️ Formato não suportado. Envie JPG, PNG ou PDF.")
                return
        else:
            await update.message.reply_text("⚠️ Envie uma imagem ou PDF do despacho.")
            return
        
        caminho = f"/tmp/doc_{user_id}_{int(time.time())}{extensao}"
        await file.download_to_drive(caminho)
        print(f"📥 Arquivo salvo: {caminho}")
        
        await update.message.reply_text(
            "🔍 **Processando documento...**\n"
            "⏳ OCR + Classificação Jurídica em ação...\n"
            "📊 Isso pode levar alguns segundos.",
            parse_mode='Markdown'
        )
        
        # 🔥 Análise completa
        dados = analisar_documento(caminho)
        user_state[user_id] = {"dados": dados}
        
        # Mensagem formatada
        tipo_acao = dados.get('tipo_acao', 'cumprimento')
        acao_info = TIPOS_ACAO.get(tipo_acao, TIPOS_ACAO['cumprimento'])
        
        msg = (
            f"✅ **DESPACHO CLASSIFICADO:**\n\n"
            f"📋 **Processo:** `{dados.get('numero_processo', 'Não encontrado')}`\n"
            f"👤 **Autor:** {dados.get('autor', 'Não encontrado')}\n"
            f"⚖️ **Réu:** {dados.get('reu', 'Não encontrado')}\n\n"
            f"🎯 **Tipo de Ação:** {acao_info['descricao']}\n"
            f"📝 **Contexto:** _{dados.get('contexto', 'Não identificado')}_\n"
            f"{'⏰ **Prazo:** ' + dados.get('prazo', '') if dados.get('prazo') else ''}\n\n"
            f"❓ Deseja adicionar alguma fundamentação extra?\n"
            f"📝 Responda com o texto ou digite **'não'** para gerar a petição padrão"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        erro_msg = str(e)
        print(f"❌ Erro no processamento: {erro_msg}")
        await update.message.reply_text(
            f"❌ **Erro ao processar documento:**\n{erro_msg}\n\n"
            f"Por favor, verifique se o documento está legível e tente novamente.",
            parse_mode='Markdown'
        )
    
    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
            print(f"🗑️ Arquivo temporário removido: {caminho}")


async def receber_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe texto de fundamentação"""
    user_id = update.message.from_user.id
    texto_usuario = update.message.text
    nome_arquivo = None
    
    if user_id not in user_state:
        await update.message.reply_text(
            "⚠️ **Nenhum despacho pendente!**\n"
            "Envie primeiro a imagem do despacho judicial.",
            parse_mode='Markdown'
        )
        return
    
    dados = user_state[user_id]["dados"]
    fundamentacao = "" if texto_usuario.lower() in ["não", "nao", "n", "nop"] else texto_usuario
    
    await update.message.reply_text(
        "⏳ **Gerando petição profissional...**\n"
        "📄 Formatando documento DOCX...",
        parse_mode='Markdown'
    )
    
    try:
        texto_peticao = gerar_peticao(dados, fundamentacao)
        
        num_proc = dados.get('numero_processo', 'sem_numero')
        num_proc_limpo = re.sub(r'[^\w\-]', '_', num_proc)
        nome_arquivo = f"/tmp/peticao_{num_proc_limpo}_{user_id}.docx"
        
        gerar_docx(texto_peticao, nome_arquivo)
        
        with open(nome_arquivo, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=f"📄 **Petição gerada com sucesso!**\n"
                       f"📋 Processo: {num_proc}\n"
                       f"⚖️ Tipo: {TIPOS_ACAO.get(dados.get('tipo_acao', 'cumprimento'))['descricao']}\n"
                       f"📅 Data: {datetime.now().strftime('%d/%m/%Y')}\n\n"
                       f"Desenvolvido por Raphael Vitor - OAB/RJ 176.629",
                filename=f"Peticao_{num_proc_limpo}.docx"
            )
        
        user_state.pop(user_id, None)
        print(f"✅ Petição enviada para user {user_id}")
        
    except Exception as e:
        erro_msg = str(e)
        print(f"❌ Erro ao gerar petição: {erro_msg}")
        await update.message.reply_text(
            f"❌ **Erro ao gerar petição:**\n{erro_msg}",
            parse_mode='Markdown'
        )
    
    finally:
        if nome_arquivo and os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)
            print(f"🗑️ DOCX temporário removido: {nome_arquivo}")


# ==============================
# MAIN
# ==============================

def main():
    """Função principal"""
    print("=" * 50)
    print("🤖 Bot de Petições Jurídicas")
    print("⚖️  Versão com Classificação Jurídica")
    print("=" * 50)
    print(f"📡 Ollama: {OLLAMA_URL}")
    print(f"🧠 Modelo LLM: {MODEL_OCR}")
    print(f"🔧 OCR Local: Tesseract")
    
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama conectado! Modelos disponíveis: {len(models)}")
    except:
        print("⚠️ Não foi possível verificar Ollama - verifique se está rodando")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receber_documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_texto))
    
    print("✅ Bot pronto! Aguardando mensagens...")
    print("=" * 50)
    
    app.run_polling()


if __name__ == "__main__":
    main()
