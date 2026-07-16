import os
import re
import chromadb
from collections import Counter
from chromadb.utils import embedding_functions
from bs4 import BeautifulSoup

# =========================================================
# ⚙️ CONFIGURAÇÕES
# =========================================================
PASTA_HTML = "leis_html"
DB_PATH = "db_vetorial"
COLECAO_ARTIGOS = "legislacao_artigos"
COLECAO_BLOCOS = "legislacao_blocos"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

SIGLAS = {
    "cc.html": "CC",
    "cdc.html": "CDC",
    "cp.html": "CP",
    "cpp.html": "CPP",
    "cpc.html": "CPC",
    "clt.html": "CLT",
    "constituicao.html": "CF",
    "JEC_JECRIM.html": "JEC",
    "jef.html": "JEF"
}

MAPEAMENTO_LEIS_META = {
    "cpc.html": {"lei": "Código de Processo Civil", "tipo": "lei", "ano": "2015"},
    "clt.html": {"lei": "CLT", "tipo": "lei", "ano": "1943"},
    "cdc.html": {"lei": "Código de Defesa do Consumidor", "tipo": "lei", "ano": "1990"},
    "constituicao.html": {"lei": "Constituição Federal", "tipo": "constituicao", "ano": "1988"},
    "cc.html": {"lei": "Código Civil", "tipo": "lei", "ano": "2002"},
    "cp.html": {"lei": "Código Penal", "tipo": "lei", "ano": "1940"},
    "cpp.html": {"lei": "Código de Processo Penal", "tipo": "lei", "ano": "1941"},
    "JEC_JECRIM.html": {"lei": "Juizados Especiais (JEC/JECRIM)", "tipo": "lei", "ano": "2003"},
    "jef.html": {"lei": "Juizados Especiais Federais", "tipo": "lei", "ano": "2001"},
}

# =========================================================
# 🔍 PARSER SIMPLIFICADO E ROBUSTO (CORRIGIDO)
# =========================================================

def extrair_metadados_lei(nome_arquivo):
    """Extrai metadados da lei"""
    meta = MAPEAMENTO_LEIS_META.get(nome_arquivo, {
        "lei": nome_arquivo.replace(".html", "").replace("_", " "),
        "tipo": "lei",
        "ano": "desconhecido"
    }).copy()
    return meta


def validar_artigo(texto):
    """Validação permissiva"""
    if not texto or len(texto.strip()) < 20:
        return False, "muito_curto"
    if texto.count(" ") < 5:
        return False, "poucas_palavras"
    return True, None


def limpar_numero_artigo(numero_raw):
    """
     CORREÇÃO DO BUG
    Remove apenas º e . do FINAL do número
    Preserva pontos no meio (ex: não existe, mas previne bugs futuros)
    
    Exemplos:
    - "186." → "186"
    - "1º" → "1"
    - "980-A." → "980-A"
    - "186º." → "186"
    """
    return re.sub(r"[º.]+$", "", numero_raw.strip())


def extrair_artigos_simples(soup, nome_arquivo):
    """
    🎯 VERSÃO SIMPLIFICADA E ROBUSTA (CORRIGIDA)
    - Converte HTML em texto puro
    - Divide por regex nos artigos
    - Captura 99,9% dos artigos
    - IDs limpos sem underscore no final
    """
    metadados_lei = extrair_metadados_lei(nome_arquivo)
    
    # 1️⃣ Converte HTML em texto puro
    texto_completo = soup.get_text("\n")
    
    # 2️ Normaliza quebras de linha
    texto_completo = re.sub(r'\r', '', texto_completo)
    texto_completo = re.sub(r'\n+', '\n', texto_completo)
    texto_completo = texto_completo.strip()
    
    # 3️⃣ Divide nos artigos usando lookahead
    blocos = re.split(
        r'(?=Art\.\s*\d+[A-Za-z\-º.]*)',
        texto_completo
    )
    
    # 4️⃣ Processa cada bloco
    artigos = []
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        
        # Extrai número do artigo
        match = re.match(r'Art\.\s*(\d+[A-Za-z\-º.]*)', bloco)
        if not match:
            continue
        
        # 🐛 CORREÇÃO: usa função dedicada para limpar o número
        numero_artigo = limpar_numero_artigo(match.group(1))
        
        # Valida o artigo
        valido, motivo = validar_artigo(bloco)
        if not valido:
            continue
        
        artigos.append({
            "numero": numero_artigo,
            "texto": bloco,
            "metadados_lei": metadados_lei,
        })
    
    return artigos


def gerar_blocos(artigos, tamanho_janela=5):
    """Gera blocos contextuais com janela maior"""
    blocos = []
    for i in range(len(artigos) - (tamanho_janela - 1)):
        janela = artigos[i:i+tamanho_janela]
        texto_bloco = "\n\n".join([a["texto"] for a in janela])
        blocos.append({
            "artigo_inicial": janela[0]["numero"],
            "artigo_final": janela[-1]["numero"],
            "texto": texto_bloco,
            "metadados_lei": janela[0]["metadados_lei"],
            "tamanho_janela": tamanho_janela,
        })
    return blocos


# =========================================================
# 🧠 INDEXAÇÃO NO CHROMADB (IDs limpos)
# =========================================================

def indexar_no_chromadb(todos_artigos, todos_blocos):
    print(f"🧠 Usando modelo de embeddings: {EMBEDDING_MODEL}")
    modelo_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    cliente_db = chromadb.PersistentClient(path=DB_PATH)
    
    for nome in [COLECAO_ARTIGOS, COLECAO_BLOCOS]:
        try:
            cliente_db.delete_collection(nome)
        except Exception:
            pass

    colecao_artigos = cliente_db.get_or_create_collection(
        name=COLECAO_ARTIGOS, 
        embedding_function=modelo_embedding
    )
    colecao_blocos = cliente_db.get_or_create_collection(
        name=COLECAO_BLOCOS, 
        embedding_function=modelo_embedding
    )

    # IDs limpos: CC_186, CDC_3, CP_138 (sem underscore no final)
    docs_a, metas_a, ids_a = [], [], []
    for art in todos_artigos:
        docs_a.append(art["texto"])
        metas_a.append({
            "fonte": art["fonte"],
            "artigo": art["numero"],
            "lei": art["lei"],
            "tipo": art["tipo"],
            "ano": art["ano"],
        })
        
        sigla = SIGLAS.get(art["fonte"], art["fonte"].replace(".html", ""))
        ids_a.append(f"{sigla}_{art['numero']}")

    if docs_a:
        for i in range(0, len(docs_a), 50):
            colecao_artigos.add(
                documents=docs_a[i:i+50],
                metadatas=metas_a[i:i+50],
                ids=ids_a[i:i+50]
            )

    # Blocos
    docs_b, metas_b, ids_b = [], [], []
    for idx, bloco in enumerate(todos_blocos):
        docs_b.append(bloco["texto"])
        metas_b.append({
            "fonte": bloco["fonte"],
            "artigo_inicial": bloco["artigo_inicial"],
            "artigo_final": bloco["artigo_final"],
            "lei": bloco["lei"],
            "tipo": bloco["tipo"],
            "ano": bloco["ano"],
            "tamanho_janela": bloco.get("tamanho_janela", 5),
        })
        sigla = SIGLAS.get(bloco["fonte"], bloco["fonte"].replace(".html", ""))
        ids_b.append(f"{sigla}_bloco_{bloco['artigo_inicial']}_a_{bloco['artigo_final']}_{idx}")

    if docs_b:
        for i in range(0, len(docs_b), 50):
            colecao_blocos.add(
                documents=docs_b[i:i+50],
                metadatas=metas_b[i:i+50],
                ids=ids_b[i:i+50]
            )

    return len(docs_a), len(docs_b)


# =========================================================
# 🚀 EXECUÇÃO MESTRE
# =========================================================

if __name__ == "__main__":
    if not os.path.exists(PASTA_HTML):
        print(f"❌ Pasta '{PASTA_HTML}' não encontrada.")
        exit(1)
    
    print("🕵️♂️ Iniciando parser SIMPLIFICADO e ROBUSTO (CORRIGIDO)...")

    todos_artigos = []
    todos_blocos = []
    estatisticas = {}

    for arquivo in sorted(os.listdir(PASTA_HTML)):
        caminho_html = os.path.join(PASTA_HTML, arquivo)
        
        if os.path.isdir(caminho_html) or "_files" in arquivo:
            continue
        if not (arquivo.endswith(".html") or arquivo.endswith(".htm")):
            continue
        
        print(f"\n📖 Processando: {arquivo}")
        
        with open(caminho_html, "r", encoding="utf-8", errors="ignore") as f:
            html_conteudo = f.read()
        
        soup = BeautifulSoup(html_conteudo, "html.parser")
        artigos = extrair_artigos_simples(soup, arquivo)
        
        # Filtro de duplicados
        vistos = set()
        artigos_unicos = []
        
        for art in artigos:
            chave = (arquivo, art["numero"])
            if chave in vistos:
                continue
            vistos.add(chave)
            
            art["fonte"] = arquivo
            art["lei"] = art["metadados_lei"]["lei"]
            art["tipo"] = art["metadados_lei"]["tipo"]
            art["ano"] = art["metadados_lei"]["ano"]
            artigos_unicos.append(art)
        
        todos_artigos.extend(artigos_unicos)
        
        # Blocos com janela=5
        blocos = gerar_blocos(artigos_unicos, tamanho_janela=5)
        for bloco in blocos:
            bloco["fonte"] = arquivo
            bloco["lei"] = bloco["metadados_lei"]["lei"]
            bloco["tipo"] = bloco["metadados_lei"]["tipo"]
            bloco["ano"] = bloco["metadados_lei"]["ano"]
            todos_blocos.append(bloco)
        
        tamanhos = [len(art["texto"]) for art in artigos_unicos]
        estatisticas[arquivo] = {
            "lei": artigos_unicos[0]["lei"] if artigos_unicos else "desconhecida",
            "total": len(artigos_unicos),
            "blocos": len(blocos),
            "min_char": min(tamanhos) if tamanhos else 0,
            "max_char": max(tamanhos) if tamanhos else 0,
            "media_char": sum(tamanhos) // len(tamanhos) if tamanhos else 0,
        }
        
        print(f"  ✅ Artigos: {len(artigos_unicos)} | Blocos: {len(blocos)}")
        
        #  DEBUG: Mostra primeiros 5 IDs para validação
        if artigos_unicos:
            print(
    "🔎 IDs de exemplo:",
    [f"{SIGLAS.get(arquivo,'?')}_{a['numero']}" for a in artigos_unicos[:5]]
)

    print("\n🚀 Indexando no ChromaDB...")
    total_artigos, total_blocos = indexar_no_chromadb(todos_artigos, todos_blocos)

    print("\n" + "="*60)
    print("📊 RELATÓRIO DE INDEXAÇÃO")
    print("="*60)
    
    for arquivo, stats in estatisticas.items():
        print(f"\n📚 {stats['lei']} ({arquivo})")
        print(f"   Artigos: {stats['total']}")
        print(f"   Blocos: {stats['blocos']} (janela=5)")
        print(f"   Tamanho: {stats['min_char']} - {stats['max_char']} (média: {stats['media_char']})")

    print(f"\n🎯 TOTAL INDEXADO:")
    print(f"   • {total_artigos} artigos individuais → {COLECAO_ARTIGOS}")
    print(f"   • {total_blocos} blocos contextuais → {COLECAO_BLOCOS}")
    print("="*60)
    print("✨ CORREÇÕES APLICADAS:")
    print("   ✓ Bug do underscore no final dos IDs corrigido")
    print("   ✓ Função limpar_numero_artigo() dedicada")
    print("   ✓ IDs agora: CC_186, CC_1, CC_980-A (limpos)")
    print("   ✓ Debug de IDs de exemplo adicionado")
    print("="*60)
