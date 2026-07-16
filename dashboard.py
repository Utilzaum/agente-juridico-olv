#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Streamlit - Controladoria Jurídica v2.0
✅ CAMADA ÚNICA: infra.repositorio (única fonte de verdade)
✅ BANCO: controladoria.db (eventos.db descontinuado)
✅ SCHEMA: status (não concluido), descricao (não determinacao_judicial)
✅ COMPATÍVEL: Streamlit + pandas DataFrame
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import List, Dict

# =========================================================
# ✅ IMPORT DA CAMADA ÚNICA (infra.repositorio)
# =========================================================
try:
    from infra.repositorio import (
        buscar_eventos_pendentes,
        buscar_evento_por_id,
        concluir_evento,
        listar_concluidos,
        listar_auditoria,
    )
    REPOSITORIO_OK = True
except ImportError as e:
    st.error(f"❌ Erro ao importar repositorio: {e}")
    REPOSITORIO_OK = False

# =========================================================
# ⚙️ CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(page_title="⚖️ Controladoria Jurídica", layout="wide")

# =========================================================
# 🔐 AUTENTICAÇÃO
# =========================================================
SENHA_CORRETA = "backdrifts22"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acesso Restrito")
    senha = st.text_input("Digite a senha", type="password")
    if senha == SENHA_CORRETA:
        st.session_state.auth = True
        st.success("Acesso liberado!")
        st.rerun()
    elif senha != "":
        st.error("Senha incorreta")
    st.stop()

# =========================================================
# 🗄️ CARREGAR DADOS (via repositorio)
# =========================================================
@st.cache_data(ttl=60)
def carregar_todos_eventos() -> pd.DataFrame:
    """
    Carrega TODOS os eventos (pendentes + concluídos) via repositorio.
    Combina buscar_eventos_pendentes() + listar_concluidos()
    """
    if not REPOSITORIO_OK:
        return pd.DataFrame()
    
    try:
        # Busca pendentes
        pendentes = buscar_eventos_pendentes()
        
        # Busca concluídos
        concluidos = listar_concluidos(limite=1000)
        
        # Combina as duas listas
        todos = pendentes + concluidos
        
        if not todos:
            return pd.DataFrame()
        
        # Converte lista de dicts em DataFrame
        df = pd.DataFrame(todos)
        
        # Padroniza colunas para compatibilidade com o dashboard antigo
        if 'prazo_final' in df.columns:
            df['prazo_final'] = pd.to_datetime(df['prazo_final'], errors='coerce')
        
        # Adiciona coluna 'concluido' para compatibilidade (0 ou 1)
        if 'status' in df.columns:
            df['concluido'] = df['status'].apply(lambda x: 1 if x == 'concluido' else 0)
        else:
            df['concluido'] = 0
        
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar eventos: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def carregar_processos() -> pd.DataFrame:
    """
    Carrega processos (se a tabela existir).
    Nota: O repositorio atual não expõe processos diretamente.
    Esta função é um placeholder para futura implementação.
    """
    # TODO: Implementar quando repositorio expuser listar_processos()
    return pd.DataFrame()

def concluir_evento_ui(id_evento: int) -> bool:
    """
    Conclui um evento via repositorio.
    Adapta a interface do Streamlit para o repositorio.
    """
    if not REPOSITORIO_OK:
        st.error("❌ Repositório indisponível")
        return False
    
    try:
        resultado = concluir_evento(id_evento, "Concluído via Dashboard", "Dashboard")
        return "concluído" in resultado.lower() or "sucesso" in resultado.lower()
    except Exception as e:
        st.error(f"❌ Erro ao concluir: {e}")
        return False

# =========================================================
# 📊 HEADER
# =========================================================
st.title("⚖️ Controladoria Jurídica")

# Carregamento inicial
eventos = carregar_todos_eventos()
processos = carregar_processos()

col1, col2, col3 = st.columns(3)

total = len(eventos)
pendentes_df = eventos[eventos["concluido"] == 0] if not eventos.empty else pd.DataFrame()
concluidos_df = eventos[eventos["concluido"] == 1] if not eventos.empty else pd.DataFrame()

col1.metric("📊 Total de Prazos", total)
col2.metric("🟢 Pendentes", len(pendentes_df))
col3.metric("✅ Concluídos", len(concluidos_df))

st.divider()

# =========================================================
# 📁 PROCESSOS
# =========================================================
st.subheader("📁 Processos")

if not processos.empty:
    total_processos = len(processos)
    st.metric("📁 Total de Processos", total_processos)
    
    # Métrica: Ativos
    if "ativo" in processos.columns:
        ativos = processos[processos["ativo"] == 1]
        st.metric("🟢 Ativos", len(ativos))
    
    # Métrica: Parados (+30 dias)
    if "data_ultima_movimentacao" in processos.columns:
        processos["data_ultima_movimentacao"] = pd.to_datetime(
            processos["data_ultima_movimentacao"], errors="coerce"
        )
        hoje = pd.Timestamp.today()
        parados = processos[processos["data_ultima_movimentacao"] < (hoje - pd.Timedelta(days=30))]
        
        st.metric("🧊 Parados +30 dias", len(parados))
        
        if not parados.empty:
            st.warning("⚠️ Processos parados detectados")
            col_id = "numero" if "numero" in parados.columns else parados.columns[0]
            for _, row in parados.iterrows():
                st.write(f"📌 {row[col_id]} — sem movimentação")
    else:
        st.info("ℹ️ Coluna `data_ultima_movimentacao` não encontrada na tabela.")
else:
    st.info("📭 Nenhum processo cadastrado ainda.")

st.divider()

# =========================================================
# 📅 LISTA DE PRAZOS
# =========================================================
st.subheader("📅 Prazos")

if not eventos.empty:
    hoje = pd.Timestamp.today()
    
    # Filtra pendentes com prazo final definido
    pendentes = pendentes_df[pendentes_df["prazo_final"].notna()].sort_values("prazo_final")
    
    # Urgentes (≤3 dias)
    urgentes = pendentes[pendentes["prazo_final"] <= hoje + pd.Timedelta(days=3)]
    st.metric("⚠️ Urgentes (≤3 dias)", len(urgentes))
    
    st.divider()
    
    for _, row in pendentes.iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        
        with col1:
            processo_num = row.get('numero_processo') or row.get('processo') or 'N/D'
            st.write(f"📌 {processo_num}")
            descricao = row.get('descricao') or row.get('tipo_evento') or "Sem descrição"
            st.caption(descricao)
        
        with col2:
            st.write(row.get("tipo_evento", "N/D"))
        
        with col3:
            prazo_str = str(row['prazo_final']).split(' ')[0] if pd.notna(row.get('prazo_final')) else 'N/D'
            st.write(f"📅 {prazo_str}")
        
        with col4:
            if st.button("✔️ Concluir", key=f"btn_{row['id']}"):
                if concluir_evento_ui(int(row["id"])):
                    st.toast("✅ Prazo concluído!", icon="🎉")
                    st.cache_data.clear()  # Limpa cache para atualizar
                    st.rerun()
                else:
                    st.toast("❌ Falha ao concluir", icon="⚠️")
else:
    st.info("📭 Nenhum prazo cadastrado ainda.")

# =========================================================
# 📊 GRÁFICO
# =========================================================
if not eventos.empty and "tipo_evento" in eventos.columns:
    st.divider()
    st.subheader("📊 Eventos por Tipo")
    st.bar_chart(eventos["tipo_evento"].value_counts())

# =========================================================
# 📋 AUDITORIA RECENTE
# =========================================================
st.divider()
st.subheader("📋 Auditoria Recente")

if REPOSITORIO_OK:
    try:
        auditoria = listar_auditoria(limite=10)
        if auditoria:
            for reg in auditoria:
                acao = reg.get('acao', 'N/D')
                motivo = reg.get('motivo', '')
                data_hora = reg.get('data_hora', '')
                processo = reg.get('numero_processo', 'N/D')
                
                icones = {"CONCLUIDO": "✔️", "CORRIGIDO": "✏️", "REABERTO": "🔄", "ARQUIVADO": "📁"}
                icone = icones.get(acao, "📌")
                
                st.write(f"{icone} **{acao}** - Processo {processo}")
                st.caption(f"Motivo: {motivo} | {data_hora}")
        else:
            st.info("ℹ️ Nenhuma ação registrada ainda.")
    except Exception as e:
        st.error(f"❌ Erro ao carregar auditoria: {e}")
else:
    st.warning("⚠️ Repositório indisponível")

# =========================================================
# 📍 STATUS DO CURSOR DJEN
# =========================================================
st.divider()
st.subheader("📍 Status do DJEN")

if REPOSITORIO_OK:
    try:
        from infra.repositorio import obter_cursor
        ultima_djen = obter_cursor('ultima_djen')
        
        col1, col2 = st.columns(2)
        col1.metric("🕐 Última execução DJEN", 
                    ultima_djen.strftime('%d/%m/%Y') if ultima_djen else "Nunca executado")
        col2.metric("📅 Data atual", date.today().strftime('%d/%m/%Y'))
        
        if ultima_djen:
            dias_desde = (date.today() - ultima_djen).days
            if dias_desde > 3:
                st.warning(f"⚠️ DJEN não executa há {dias_desde} dias")
            else:
                st.success("✅ DJEN atualizado")
    except Exception as e:
        st.error(f"❌ Erro ao carregar cursor: {e}")
else:
    st.warning("⚠️ Repositório indisponível")
