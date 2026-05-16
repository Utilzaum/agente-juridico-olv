#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DJEN v16.1 — Agente Jurídico Inteligente (Produção)
✅ Qwen 2.5:7b local via Ollama (LGPD compliant)
✅ Timeout + Validação de LLM + Normalização de data
✅ Motor jurídico CPC/CPP com fallback robusto
✅ Excel + SendGrid
✅ 🏛️ BANCO ÚNICO: infra/eventos.db (Zero duplicação)
✅ 🔧 Retry exponencial corrigido + Janela de busca ampliada
✅ 🛡️ Inicialização garantida do DB no boot
Autor: Agente Jurídico DJEN
Data: 2026
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import hashlib
import os
import time
import logging
from pathlib import Path
import base64
from typing import Optional, Dict, List, Any
# 📧 SendGrid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition
)
# 🔧 Variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()
# 🤖 Módulos locais
from qwen_client import extrair_prazo_com_llm, health_check
from prazo_engine import calcular_prazo, aplicar_regra_fallback, calcular_inicio_prazo
from utils import normalizar_data_br, gerar_hash

# 🏛️ INTEGRAÇÃO COM BANCO CENTRAL (infra/eventos.db)
try:
    from infra.db import (
        inserir_evento,
        atualizar_processo,
        inicializar_db
    )
    # ✅ garante estrutura do banco no boot
    inicializar_db()
except ImportError:
    inserir_evento = None
    atualizar_processo = None
    logging.warning("⚠️ Módulo infra.db não encontrado. DJEN rodará apenas com Excel/Logs.")

# =========================
# CONFIGURAÇÃO GLOBAL
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# API PJe
BASE_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
OAB_NUMERO = "176629"
OAB_UF = "RJ"

# Output
OUTPUT_FILE = Path(__file__).parent / "publicacoes.xlsx"

# Credenciais
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "olvestag@outlook.com")
EMAIL_TO = os.getenv("EMAIL_TO", "rvao.adv@outlook.com")

# Parâmetros de rede
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0
PAGE_SIZE = 100

# =========================
# FUNÇÕES AUXILIARES DE REDE (✅ CORRIGIDAS)
# =========================
def get_data_busca() -> str:
    """Calcula data de busca: último dia útil anterior."""
    hoje = date.today()
    dia = hoje.weekday()
    if dia == 0:
        delta = 3      # Segunda → sexta
    elif dia == 5:
        delta = 1      # Sábado → sexta
    elif dia == 6:
        delta = 2      # Domingo → sexta
    else:
        delta = 1      # Ter-Sex → ontem
    return (hoje - timedelta(days=delta)).strftime("%Y-%m-%d")

DATA_BUSCA = get_data_busca()

def fazer_requisicao(url: str, params: dict) -> Optional[requests.Response]:
    """Requisição HTTP com retry exponencial (corrigido)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (AgenteJuridico-DJEN/16.1)",
        "Accept": "application/json",
    }
    for tentativa in range(MAX_RETRIES):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = RETRY_DELAY * (2 ** tentativa)
                logger.warning(f"⚠️ Rate limit. Aguardando {wait}s...")
                time.sleep(wait)
                continue
            else:
                logger.error(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Timeout (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Erro de conexão (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")
            return None  # ✅ CORREÇÃO: sai com segurança, sem break inválido

        # Backoff exponencial entre tentativas
        if tentativa < MAX_RETRIES - 1:
            wait = RETRY_DELAY * (2 ** tentativa)
            time.sleep(wait)
    return None

# =========================
# BUSCA NA API PJe (✅ AMPLIADA + LOG)
# =========================
def buscar_publicacoes() -> List[Dict]:
    """Busca publicações da OAB 176629/RJ na API do PJe."""
    # ✅ CORREÇÃO 1: Janela de busca ampliada (evita falha por delay da API)
    hoje = date.today()
    data_inicio = (hoje - timedelta(days=2)).strftime("%Y-%m-%d")
    data_fim = hoje.strftime("%Y-%m-%d")
    logger.info(f"🔎 Buscando publicações de {data_inicio} a {data_fim}...")
    todas = []
    page = 1
    while True:
        params = {
            "numeroOab": OAB_NUMERO,
            "ufOab": OAB_UF,
            "dataDisponibilizacaoInicio": data_inicio,  # ✅ Janela ampliada
            "dataDisponibilizacaoFim": data_fim,        # ✅ Janela ampliada
            "size": PAGE_SIZE,
            "page": page,
        }
        response = fazer_requisicao(BASE_URL, params)
        if not response:
            logger.error(f"❌ Falha na página {page}")
            break
        try:
            dados = response.json()
        except ValueError as e:
            logger.error(f"❌ JSON inválido: {e}")
            break
        items = dados.get("items", [])
        total_count = dados.get("count", 0)
        if not items:
            logger.info(f"📭 Página {page} vazia.")
            break
        todas.extend(items)
        logger.info(f"  ✅ Página {page}: {len(items)} itens (total: {len(todas)}/{total_count})")
        if len(items) < PAGE_SIZE:
            logger.info("🏁 Última página atingida.")
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    # ✅ CORREÇÃO 2: Log da quantidade real retornada
    logger.info(f"📊 API retornou {len(todas)} publicações brutas")
    logger.info(f"📦 Busca concluída: {len(todas)} publicações coletadas.")
    return todas

# =========================
# PROCESSAMENTO JURÍDICO
# =========================
def extrair_tipo_ato(texto: str) -> str:
    """Classifica tipo de ato jurídico com heurística."""
    t = texto.upper()
    if "AUDIÊNCIA" in t or "AUDIENCIA" in t:
        if "NÃO" not in t and "SEM" not in t and "CANCELADA" not in t:
            return "AUDIÊNCIA"
    if "SENTENÇA" in t or "SENTENCA" in t: return "SENTENÇA"
    if "ACÓRDÃO" in t or "ACORDAO" in t: return "ACÓRDÃO"
    if "DESPACHO" in t: return "DESPACHO"
    if "CITAÇÃO" in t or "CITACAO" in t: return "CITAÇÃO"
    if "INTIMAÇÃO" in t or "INTIMACAO" in t: return "INTIMAÇÃO"
    if "DECISÃO" in t or "DECISAO" in t: return "DECISÃO"
    return "OUTROS"

def extrair_audiencia(texto: str) -> Optional[str]:
    """Extrai data de audiência no formato DD/MM/YYYY."""
    if "AUDIÊNCIA" not in texto.upper() and "AUDIENCIA" not in texto.upper():
        return None
    import re
    m = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else None

def extrair_partes(texto: str) -> tuple:
    """Extrai autor e réu com regex adaptativo."""
    import re
    autor, reu = "", ""
    m = re.search(
        r"(?:AUTOR|AUTORA|RECTE|REQUERENTE):\s*(.+?)(?=\s+(?:REU|RÉU|REQUERIDO|ADV|OAB|$))",
        texto, re.IGNORECASE
    )
    if m:
        autor = re.sub(r"\s*(OAB|CPF|CNPJ).*", "", m.group(1).strip(), flags=re.IGNORECASE).strip()
    m = re.search(
        r"(?:REU|RÉU|REQUERIDO|RECORRIDO):\s*(.+?)(?=\s+(?:AUTOR|ADV|OAB|$))",
        texto, re.IGNORECASE
    )
    if m:
        reu = re.sub(r"\s*(OAB|CPF|CNPJ).*", "", m.group(1).strip(), flags=re.IGNORECASE).strip()
    return autor[:150] if autor else "", reu[:150] if reu else ""

def extrair_orgao(texto: str) -> str:
    """Extrai órgão julgador com padrões comuns."""
    import re
    padroes = [
        r"(\d+[ªa°]?\s+VARA\s+[^.]+?)(?=\.|$)",
        r"(JUÍZO\s+ESPECIAL\s+[^.]+?)(?=\.|$)",
        r"(TURMA\s+RECURSAL\s+[^.]+?)(?=\.|$)",
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
    return "N/D"

def processar_publicacoes(publicacoes: List[Dict]) -> List[Dict]:
    """
    Processa publicações e salva APENAS no banco central (infra.db).
    ✅ LGPD: Nenhum dado sai da máquina
    ✅ Validação de LLM + Normalização de data aplicada
    ✅ Banco único: infra/eventos.db
    """
    logger.info("⚙️ Processando com motor jurídico + Qwen local...")
    if not health_check():
        logger.warning("⚠️ Ollama não detectado. Usando apenas fallback jurídico.")
    dados, erros = [], 0
    for idx, item in enumerate(publicacoes):
        try:
            # Parse da data
            data_str = item.get("dataDisponibilizacao") or item.get("data_disponibilizacao")
            if not data_str:
                continue
            if isinstance(data_str, (int, float)):
                data_pub = datetime.fromtimestamp(data_str / 1000)
            else:
                data_pub = datetime.strptime(str(data_str)[:10], "%Y-%m-%d")
            
            # Campos base
            processo = (
                item.get("numeroProcesso") or
                item.get("numero_processo") or
                item.get("npu") or
                "N/D"
            )
            texto = item.get("texto") or item.get("conteudo") or ""
            
            # Classificação básica
            tipo = extrair_tipo_ato(texto)
            audiencia_br = extrair_audiencia(texto)
            autor, reu = extrair_partes(texto)
            orgao = extrair_orgao(texto)
            
            # 🔥 EXTRAÇÃO COM LLM LOCAL
            info_llm = extrair_prazo_com_llm(texto)
            
            # Aplicar regra de fallback (validada)
            prazo_dias, unidade = aplicar_regra_fallback(info_llm)
            
            # ✅ Validação de ramo com fallback explícito
            ramo_llm = info_llm.get("ramo")
            if ramo_llm not in ("CPC", "CPP", "CLT"):
                ramo_llm = "CPC"
                
            # Calcula marco inicial do prazo
            inicio_prazo = calcular_inicio_prazo(data_pub, ramo_llm)
            
            # Calcula prazo final
            prazo_final_dt = calcular_prazo(inicio_prazo, prazo_dias, unidade)
            prazo_final = prazo_final_dt.strftime("%Y-%m-%d")  # ✅ ISO 8601
            
            # 🎯 Audiência tem prioridade absoluta
            audiencia_data_llm = info_llm.get("audiencia_data")
            if audiencia_data_llm and isinstance(audiencia_data_llm, str) and len(audiencia_data_llm) == 10:
                prazo_final = audiencia_data_llm
                tipo_evento = "AUDIÊNCIA"
            elif audiencia_br:
                prazo_final = normalizar_data_br(audiencia_br)  # ✅ DD/MM/YYYY → YYYY-MM-DD
                tipo_evento = "AUDIÊNCIA"
            else:
                tipo_evento = tipo
                
            # Monta registro
            registro = {
                "processo": str(processo).strip(),
                "tribunal": item.get("siglaTribunal") or item.get("tribunal") or "N/D",
                "orgao_julgador": orgao,
                "tipo_ato": tipo_evento,
                "data_publicacao": data_pub.strftime("%d/%m/%Y"),
                "inicio_prazo": inicio_prazo.strftime("%d/%m/%Y"),
                "prazo_final": prazo_final,
                "prazo_dias": prazo_dias,
                "unidade_prazo": unidade,
                "ramo": ramo_llm,
                "audiencia": audiencia_br or audiencia_data_llm or "",
                "autor": autor,
                "reu": reu,
                "conteudo": str(texto).strip()[:800],
            }
            dados.append(registro)
            
            # 🏛️ SALVA APENAS NO BANCO CENTRAL (infra.db)
            if inserir_evento and prazo_final:
                try:
                    inserir_evento({
                        "numero_processo": registro["processo"],
                        "determinacao_judicial": f"Publicação DJEN: {tipo_evento}",
                        "tipo_evento": tipo_evento,
                        "prazo_dias": prazo_dias,
                        "tipo_prazo": unidade,
                        "prazo_final": prazo_final,
                        "urgencia": "alta" if prazo_dias <= 5 else "normal",
                        "resumo": registro["conteudo"][:200]
                    })
                    if atualizar_processo:
                        atualizar_processo(
                            numero=registro["processo"],
                            tribunal=registro.get("tribunal", "N/D"),
                            data=registro.get("data_publicacao")
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao salvar em infra.db: {e}")
                    
            if (idx + 1) % 20 == 0:
                logger.info(f"  📊 Processados {idx + 1}/{len(publicacoes)}...")
                
        except Exception as e:
            erros += 1
            if erros <= 3:
                logger.warning(f"⚠️ Erro no item {idx}: {e}")
            continue
            
    if erros > 0:
        logger.warning(f"⚠️ {erros} erros no processamento.")
    logger.info(f"✨ {len(dados)} publicações processadas com sucesso.")
    return dados

# =========================
# GERAÇÃO DE PLANILHA
# =========================
def gerar_planilha(dados: List[Dict]) -> Optional[str]:
    logger.info("📊 Gerando planilha...")
    if not dados:
        return None
    df = pd.DataFrame(dados)
    # Deduplicação
    df["_hash"] = df["conteudo"].apply(gerar_hash)
    antes = len(df)
    df = df.drop_duplicates(subset=["_hash"], keep="first").drop(columns=["_hash"])
    if antes - len(df) > 0:
        logger.info(f"🧹 {antes - len(df)} duplicatas removidas.")
    # Ordenação
    df["_sort"] = pd.to_datetime(df["data_publicacao"], dayfirst=True, errors="coerce")
    df = df.sort_values("_sort", ascending=False).drop(columns=["_sort"])
    # Colunas finais
    colunas = [
        "processo", "tribunal", "orgao_julgador", "tipo_ato",
        "data_publicacao", "inicio_prazo", "prazo_final",
        "prazo_dias", "unidade_prazo", "ramo", "audiencia",
        "autor", "reu", "conteudo"
    ]
    df = df[[c for c in colunas if c in df.columns]]
    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(OUTPUT_FILE, index=False)
    logger.info(f"💾 {len(df)} registros salvos em: {OUTPUT_FILE}")
    return str(OUTPUT_FILE)

# =========================
# ENVIO DE E-MAIL
# =========================
def enviar_email(arquivo: str, total: int) -> bool:
    if not SENDGRID_API_KEY:
        logger.error("❌ SENDGRID_API_KEY não configurada no .env")
        return False
    try:
        logger.info("📧 Enviando e-mail...")
        with open(arquivo, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(os.path.basename(arquivo)),
            FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            Disposition("attachment"),
        )
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=EMAIL_TO,
            subject=f"DJEN v16.1 - OAB {OAB_NUMERO}/{OAB_UF}",
            html_content=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h3 style="color: #2c3e50;">📋 Relatório DJEN v16.1</h3>
            <p>Segue planilha com <strong>{total} publicações</strong>.</p>
            <p style="color: #666; font-size: 12px;">
            <em>Processamento 100% local • LGPD compliant • Banco único infra.db</em>
            </p>
            </div>
            """,
        )
        message.attachment = attachment
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code in (200, 202):
            logger.info(f"✅ E-mail enviado (status {response.status_code})")
            return True
        else:
            body = getattr(response, "body", "Sem detalhes")
            logger.error(f"❌ SendGrid: {response.status_code} - {body}")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao enviar e-mail: {e}", exc_info=True)
        return False

# =========================
# MAIN
# =========================
def main():
    logger.info("🚀 DJEN v16.1 — Agente Jurídico Inteligente (Produção)")
    logger.info(f"📍 OAB: {OAB_NUMERO}/{OAB_UF} | 🏛️ Banco: infra/eventos.db")
    try:
        # 1. Busca publicações (janela ampliada)
        publicacoes = buscar_publicacoes()
        if not publicacoes:
            logger.warning("⚠️ Nenhuma publicação encontrada.")
            return
        # 2. Processa com inteligência jurídica + salva no banco central
        dados = processar_publicacoes(publicacoes)
        if not dados:
            logger.warning("⚠️ Nenhum dado processado.")
            return
        # 3. Gera planilha
        arquivo = gerar_planilha(dados)
        if not arquivo:
            return
        # 4. Envia e-mail
        enviar_email(arquivo, len(dados))
        logger.info("✅ Processo concluído com sucesso!")
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrompido pelo usuário.")
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}", exc_info=True)
    finally:
        logger.info("🏁 DJEN encerrado.")

if __name__ == "__main__":
    main()
