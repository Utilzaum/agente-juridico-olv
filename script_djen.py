#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DJEN v17.1 — Agente Jurídico Inteligente (Produção)
✅ ARQUITETURA: infra.repositorio (camada única de acesso ao banco)
✅ BANCO: controladoria.db (schema real alinhado)
✅ CURSOR PERSISTENTE: Busca deslizante (cursor - 3 dias até hoje)
✅ DEDUPLICAÇÃO: Hash SHA256 do item cru da API
✅ SALVAMENTO: Publicação crua em publicacoes_djen ANTES da IA
✅ EVENTOS: Salvos após inferência jurídica
"""
import requests
import json
from datetime import datetime, timedelta, date
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List

# =========================================================
# 🏛️ CAMADA ÚNICA: infra.repositorio
# =========================================================
try:
    from infra.repositorio import (
        salvar_publicacao,
        salvar_evento,
        obter_cursor,
        atualizar_cursor,
        calcular_hash_api,
    )
    REPOSITORIO_OK = True
except ImportError as e:
    print(f"❌ Erro ao importar repositorio: {e}")
    REPOSITORIO_OK = False

# =========================================================
# 🤖 LLM LOCAL (fallback)
# =========================================================
try:
    from qwen_client import extrair_prazo_com_llm, health_check
    LLM_OK = True
except ImportError as e:
    print(f"⚠️ Erro ao importar qwen_client: {e}")
    LLM_OK = False

# =========================================================
# ⚖️ MOTOR DE PRAZOS (opcional)
# =========================================================
try:
    from motor_prazos import calcular_prazo_legal
    MOTOR_OK = True
except ImportError as e:
    print(f"⚠️ Motor de prazos não disponível: {e}")
    MOTOR_OK = False

# =========================================================
# 📋 CONFIGURAÇÃO GLOBAL
# =========================================================
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

# Parâmetros de rede
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0
PAGE_SIZE = 100
LOOKBACK_DAYS = 10
MARGEM_SEGURANCA = 3

# =========================================================
# 🌐 REDE
# =========================================================
def fazer_requisicao(url: str, params: dict) -> Optional[requests.Response]:
    headers = {
        "User-Agent": "Mozilla/5.0 (AgenteJuridico-DJEN/17.1)",
        "Accept": "application/json",
    }
    for tentativa in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
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
            logger.warning(f"⏱️ Timeout (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Erro de conexão (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")
            return None
        if tentativa < MAX_RETRIES - 1:
            wait = RETRY_DELAY * (2 ** tentativa)
            time.sleep(wait)
    return None

# =========================================================
# 🔎 BUSCA NA API PJe
# =========================================================
def buscar_publicacoes() -> List[Dict]:
    cursor_data = obter_cursor('ultima_djen')
    if cursor_data:
        data_inicio = (cursor_data - timedelta(days=MARGEM_SEGURANCA)).strftime("%Y-%m-%d")
        logger.info(f"🧭 Cursor encontrado: {cursor_data.strftime('%d/%m/%Y')} → busca de {data_inicio}")
    else:
        data_inicio = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        logger.info(f"🆕 Primeira execução. Fallback: {LOOKBACK_DAYS} dias")
    
    data_fim = date.today().strftime("%Y-%m-%d")
    logger.info(f" Buscando publicações de {data_inicio} a {data_fim}...")
    
    todas = []
    page = 1
    while True:
        params = {
            "numeroOab": OAB_NUMERO,
            "ufOab": OAB_UF,
            "dataDisponibilizacaoInicio": data_inicio,
            "dataDisponibilizacaoFim": data_fim,
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
        
        items = dados.get("items") or dados.get("content") or dados.get("resultados") or []
        total_count = dados.get("count", 0)
        if not items:
            logger.info(f"📭 Página {page} vazia.")
            break
        
        todas.extend(items)
        logger.info(f"  ✅ Página {page}: {len(items)} itens (total: {len(todas)}/{total_count})")
        
        if total_count > 0 and len(todas) >= total_count:
            break
        if len(items) < PAGE_SIZE:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    
    logger.info(f"📦 Busca concluída: {len(todas)} publicações coletadas.")
    return todas

# =========================================================
# 📊 EXTRAÇÃO ESTRUTURADA
# =========================================================
def extrair_partes_estruturado(item: Dict) -> tuple:
    autor, reu = "", ""
    destinatarios = item.get("destinatarios", [])
    for dest in destinatarios:
        nome = dest.get("nome", "")
        polo = dest.get("polo", "")
        if polo == "A" and not autor:
            autor = nome
        elif polo == "P" and not reu:
            reu = nome
    return autor[:150] if autor else "", reu[:150] if reu else ""

def extrair_tipo_ato_estruturado(item: Dict) -> str:
    tipo_doc = item.get("tipoDocumento", "")
    nome_classe = item.get("nomeClasse", "")
    texto = item.get("texto", "").upper()
    if tipo_doc: return tipo_doc
    if nome_classe: return nome_classe
    if "AUDIÊNCIA" in texto or "AUDIENCIA" in texto:
        if "NÃO" not in texto and "SEM" not in texto and "CANCELADA" not in texto:
            return "AUDIÊNCIA"
    if "SENTENÇA" in texto or "SENTENCA" in texto: return "SENTENÇA"
    if "ACÓRDÃO" in texto or "ACORDAO" in texto: return "ACÓRDÃO"
    if "DESPACHO" in texto: return "DESPACHO"
    if "CITAÇÃO" in texto or "CITACAO" in texto: return "CITAÇÃO"
    if "INTIMAÇÃO" in texto or "INTIMACAO" in texto: return "INTIMAÇÃO"
    if "DECISÃO" in texto or "DECISAO" in texto: return "DECISÃO"
    return "OUTROS"

def extrair_audiencia(texto: str) -> Optional[str]:
    import re
    if "AUDIÊNCIA" not in texto.upper() and "AUDIENCIA" not in texto.upper():
        return None
    m = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else None

# =========================================================
# ⚖️ PROCESSAMENTO JURÍDICO
# =========================================================
def processar_publicacoes(publicacoes: List[Dict]) -> int:
    logger.info("⚙️ Processando com motor jurídico integrado...")
    eventos_criados = 0
    duplicatas = 0
    erros = 0
    
    for idx, item in enumerate(publicacoes):
        try:
            hash_api = calcular_hash_api(item)
            
            sucesso, msg = salvar_publicacao(item)
            if not sucesso and msg == "duplicata":
                duplicatas += 1
                logger.debug(f" Duplicata detectada: {hash_api[:16]}...")
                continue
            elif not sucesso:
                logger.warning(f"⚠️ Erro ao salvar publicação: {msg}")
            
            data_str = item.get("dataDisponibilizacao") or item.get("data_disponibilizacao")
            if not data_str:
                continue
            if isinstance(data_str, (int, float)):
                data_pub = datetime.fromtimestamp(data_str / 1000)
            else:
                try:
                    data_pub = datetime.strptime(str(data_str)[:10], "%Y-%m-%d")
                except:
                    data_pub = datetime.strptime(str(data_str)[:10], "%d/%m/%Y")
            
            processo = (
                item.get("numeroprocessocommascara") or
                item.get("numeroProcesso") or
                item.get("numero_processo") or
                item.get("npu") or "N/D"
            )
            tribunal = item.get("siglaTribunal") or "N/D"
            orgao = item.get("nomeOrgao") or "N/D"
            texto = item.get("texto") or item.get("conteudo") or ""
            tipo = extrair_tipo_ato_estruturado(item)
            audiencia_br = extrair_audiencia(texto)
            autor, reu = extrair_partes_estruturado(item)
            
            if MOTOR_OK:
                resultado_motor = calcular_prazo_legal(data_pub, texto, tipo)
                prazo_dias = resultado_motor["dias"]
                unidade = resultado_motor["tipo_dia"]
                ramo_llm = resultado_motor["ramo"]
                artigo = resultado_motor["artigo"]
                logger.info(f"🤖 Motor: {prazo_dias} dias {unidade} ({artigo})")
            else:
                if LLM_OK and health_check():
                    info_llm = extrair_prazo_com_llm(texto)
                    prazo_dias, unidade = info_llm.get("dias", 15), info_llm.get("tipo", "uteis")
                    ramo_llm = info_llm.get("ramo", "CPC")
                else:
                    prazo_dias, unidade = 15, "uteis"
                    ramo_llm = "CPC"
            
            inicio_prazo = data_pub + timedelta(days=1)
            
            if unidade == "uteis":
                if MOTOR_OK:
                    from motor_prazos import adicionar_dias_uteis
                    prazo_final_dt = adicionar_dias_uteis(inicio_prazo, prazo_dias)
                else:
                    dias_adicionados = 0
                    data_atual = inicio_prazo
                    while dias_adicionados < prazo_dias:
                        data_atual += timedelta(days=1)
                        if data_atual.weekday() < 5:
                            dias_adicionados += 1
                    prazo_final_dt = data_atual
            else:
                prazo_final_dt = inicio_prazo + timedelta(days=prazo_dias)
            
            prazo_final = prazo_final_dt.strftime("%Y-%m-%d")
            tipo_evento = "AUDIÊNCIA" if audiencia_br else tipo
            
            try:
                data_pub_date = data_pub.date() if isinstance(data_pub, datetime) else data_pub
                inicio_prazo_date = inicio_prazo.date() if isinstance(inicio_prazo, datetime) else inicio_prazo
                prazo_final_date = datetime.strptime(prazo_final, "%Y-%m-%d").date()
                if prazo_final_date < inicio_prazo_date:
                    logger.error(f"❌ prazo_final anterior ao inicio_prazo. Processo {processo} descartado.")
                    erros += 1
                    continue
                if inicio_prazo_date < data_pub_date:
                    logger.error(f"❌ inicio_prazo anterior à data_publicacao. Processo {processo} descartado.")
                    erros += 1
                    continue
            except Exception as e:
                logger.error(f"❌ Erro na validação temporal: {e}")
                erros += 1
                continue
            
            registro = {
                "numero_processo": str(processo).strip(),
                "tipo_evento": tipo_evento,
                "data_publicacao": data_pub.strftime("%d/%m/%Y"),
                "inicio_prazo": inicio_prazo.strftime("%d/%m/%Y"),
                "prazo_final": prazo_final,
                "autor": autor,
                "reu": reu,
                "tribunal": tribunal,
                "orgao_julgador": orgao,
                "descricao": f"Publicação DJEN: {tipo_evento}",
                "prazo_dias": prazo_dias,
                "tipo_contagem": unidade,
                "ramo": ramo_llm,
                "urgencia": "alta" if prazo_dias <= 5 else "normal",
                "resumo": str(texto).strip()[:200],
                "audiencia": audiencia_br or "",
                "hash_publicacao": hash_api,
            }
            
            evento_id = salvar_evento(registro)
            if evento_id:
                eventos_criados += 1
                logger.info(f"✅ Evento #{evento_id} criado: {processo} - {tipo_evento} ({prazo_dias} {unidade})")
            else:
                erros += 1
            
            if (idx + 1) % 20 == 0:
                logger.info(f"   Processados {idx + 1}/{len(publicacoes)}...")
        except Exception as e:
            erros += 1
            if erros <= 3:
                logger.warning(f"️ Erro no item {idx}: {e}")
            continue
    
    logger.info(f"✨ Resumo: {eventos_criados} criados, {duplicatas} duplicatas, {erros} erros")
    return eventos_criados

# =========================================================
# 🚀 MAIN
# =========================================================
def main():
    logger.info("🚀 DJEN v17.1 — Agente Jurídico Inteligente (Produção)")
    logger.info(f"📍 OAB: {OAB_NUMERO}/{OAB_UF}")
    logger.info(f"🏛️ Repositório: {'OK' if REPOSITORIO_OK else 'FALHOU'}")
    logger.info(f"🤖 Motor Jurídico: {'OK' if MOTOR_OK else 'FALHOU'}")
    logger.info(f"🧠 LLM Local: {'OK' if LLM_OK else 'FALHOU'}")
    
    if not REPOSITORIO_OK:
        logger.critical("❌ Repositório indisponível. Encerrando.")
        return
    
    try:
        publicacoes = buscar_publicacoes()
        if not publicacoes:
            logger.warning("⚠️ Nenhuma publicação encontrada.")
            atualizar_cursor('ultima_djen', date.today())
            return
        
        eventos_criados = processar_publicacoes(publicacoes)
        
        if eventos_criados > 0 or len(publicacoes) > 0:
            atualizar_cursor('ultima_djen', date.today())
            logger.info("✅ Processo concluído com sucesso!")
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrompido pelo usuário. Cursor NÃO atualizado.")
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}", exc_info=True)
        logger.warning("⚠️ Cursor NÃO atualizado devido ao erro.")
    finally:
        logger.info("🏁 DJEN encerrado.")

if __name__ == "__main__":
    main()
