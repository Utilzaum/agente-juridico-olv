import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from infra.db import conectar  # ✅ Mantém seu padrão de conexão

# =========================
# ⚙️ CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(page_title="⚖️ Controladoria Jurídica", layout="wide")

# =========================
# 🔐 AUTENTICAÇÃO
# =========================
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

# =========================
# 🗄️ CARREGAR DADOS
# =========================
@st.cache_data(ttl=60)
def carregar_eventos():
    try:
        with conectar() as conn:
            return pd.read_sql_query("SELECT * FROM eventos", conn)
    except Exception as e:
        st.error(f"❌ Erro ao carregar eventos: {e}")
        return pd.DataFrame()

# 🎯 PASSO 2 — FAZER O DASHBOARD LER PROCESSOS
@st.cache_data(ttl=60)
def carregar_processos():
    try:
        with conectar() as conn:
            return pd.read_sql_query("SELECT * FROM processos", conn)
    except:
        return pd.DataFrame()

def concluir_evento(id_evento: int) -> bool:
    try:
        with conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE eventos SET concluido = 1 WHERE id = ?", (id_evento,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        st.error(f"❌ Erro ao concluir: {e}")
        return False

# Carregamento inicial
eventos = carregar_eventos()
processos = carregar_processos()  # ✅ Executado no topo

# =========================
# 📊 HEADER
# =========================
st.title("⚖️ Controladoria Jurídica")
col1, col2, col3 = st.columns(3)
total = len(eventos)
pendentes = eventos[eventos["concluido"] == 0] if not eventos.empty else pd.DataFrame()
concluidos = eventos[eventos["concluido"] == 1] if not eventos.empty else pd.DataFrame()
col1.metric("📊 Total de Prazos", total)
col2.metric("🟢 Pendentes", len(pendentes))
col3.metric("✅ Concluídos", len(concluidos))

st.divider()

# =========================
# 🎯 PASSO 3 — MOSTRAR PROCESSOS NO DASHBOARD
# =========================
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
        processos["data_ultima_movimentacao"] = pd.to_datetime(processos["data_ultima_movimentacao"], errors="coerce")
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

# =========================
# 📅 LISTA DE PRAZOS
# =========================
st.subheader("📅 Prazos")
if not eventos.empty:
    eventos["prazo_final"] = pd.to_datetime(eventos["prazo_final"], errors="coerce")
    hoje = pd.Timestamp.today()
    pendentes = eventos[
        (eventos["concluido"] == 0) & (eventos["prazo_final"].notna())
    ].sort_values("prazo_final")
    
    urgentes = pendentes[pendentes["prazo_final"] <= hoje + pd.Timedelta(days=3)]
    st.metric("⚠️ Urgentes (≤3 dias)", len(urgentes))

    st.divider()

    for _, row in pendentes.iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.write(f"📌 {row['processo']}")
            st.caption(row.get("descricao", "Sem descrição"))
        with col2:
            st.write(row.get("tipo_evento", "N/D"))
        with col3:
            st.write(f"📅 {str(row['prazo_final']).split(' ')[0]}")
        with col4:
            if st.button("✔️ Concluir", key=f"btn_{row['id']}"):
                if concluir_evento(int(row["id"])):
                    st.toast("✅ Prazo concluído!", icon="🎉")
                    st.rerun()
                else:
                    st.toast("❌ Falha ao concluir", icon="⚠️")
else:
    st.info("📭 Nenhum prazo cadastrado ainda.")

# =========================
# 📊 GRÁFICO
# =========================
if not eventos.empty and "tipo_evento" in eventos.columns:
    st.divider()
    st.subheader("📊 Eventos por Tipo")
    st.bar_chart(eventos["tipo_evento"].value_counts())
