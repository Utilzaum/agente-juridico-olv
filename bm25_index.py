import os
import json
import pickle
from rank_bm25 import BM25Okapi
from bs4 import BeautifulSoup
import re

# =========================================================
# ⚙️ CONFIGURAÇÕES
# =========================================================
PASTA_HTML = "leis_html"
BM25_INDEX_PATH = "bm25_index.pkl"
ARTIGOS_JSON_PATH = "artigos_corpus.json"

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

RE_ARTIGO = re.compile(r"^Art\.\s*(\d+[A-Za-z\-º.]*)")


# =========================================================
# 🔍 PARSER SIMPLIFICADO (mesmo do indexador ChromaDB)
# =========================================================

def extrair_artigos_simples(soup, nome_arquivo):
    """Extrai artigos usando o mesmo parser do ChromaDB"""
    metadados_lei = MAPEAMENTO_LEIS_META.get(nome_arquivo, {
        "lei": nome_arquivo.replace(".html", "").replace("_", " "),
        "tipo": "lei",
        "ano": "desconhecido"
    }).copy()
    
    texto_completo = soup.get_text("\n")
    texto_completo = re.sub(r'\r', '', texto_completo)
    texto_completo = re.sub(r'\n+', '\n', texto_completo)
    texto_completo = texto_completo.strip()
    
    blocos = re.split(r'(?=Art\.\s*\d+[A-Za-z\-º.]*)', texto_completo)
    
    artigos = []
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        
        match = re.match(r'Art\.\s*(\d+[A-Za-z\-º.]*)', bloco)
        if not match:
            continue
        
        numero_artigo = re.sub(r"[º.]+$", "", match.group(1).strip())
        
        if len(bloco.strip()) < 20 or bloco.count(" ") < 5:
            continue
        
        artigos.append({
            "id": f"{SIGLAS.get(nome_arquivo, '??')}_{numero_artigo}",
            "numero": numero_artigo,
            "texto": bloco,
            "fonte": nome_arquivo,
            "lei": metadados_lei["lei"],
            "tipo": metadados_lei["tipo"],
            "ano": metadados_lei["ano"],
        })
    
    return artigos


# =========================================================
# 🏗️ CONSTRUÇÃO DO ÍNDICE BM25
# =========================================================

def construir_indice_bm25():
    """
    Constrói índice BM25 a partir dos HTMLs
    Salva em disco para carregamento rápido
    """
    print("🔨 Construindo índice BM25...")
    
    todos_artigos = []
    
    if not os.path.exists(PASTA_HTML):
        print(f"❌ Pasta '{PASTA_HTML}' não encontrada.")
        return None, None
    
    for arquivo in sorted(os.listdir(PASTA_HTML)):
        caminho_html = os.path.join(PASTA_HTML, arquivo)
        
        if os.path.isdir(caminho_html) or "_files" in arquivo:
            continue
        if not (arquivo.endswith(".html") or arquivo.endswith(".htm")):
            continue
        
        print(f"  📖 Processando: {arquivo}")
        
        with open(caminho_html, "r", encoding="utf-8", errors="ignore") as f:
            html_conteudo = f.read()
        
        soup = BeautifulSoup(html_conteudo, "html.parser")
        artigos = extrair_artigos_simples(soup, arquivo)
        
        # Remove duplicados
        vistos = set()
        for art in artigos:
            if art["id"] not in vistos:
                vistos.add(art["id"])
                todos_artigos.append(art)
        
        print(f"    ✅ {len(artigos)} artigos extraídos")
    
    if not todos_artigos:
        print("❌ Nenhum artigo encontrado.")
        return None, None
    
    # Prepara corpus para BM25 (tokenização simples)
    corpus = [art["texto"].lower().split() for art in todos_artigos]
    
    # Cria índice BM25
    bm25 = BM25Okapi(corpus)
    
    # Salva em disco
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump({
            "bm25": bm25,
            "corpus": corpus,
            "artigos": todos_artigos
        }, f)
    
    # Salva JSON para debug/inspeção
    with open(ARTIGOS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(todos_artigos, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Índice BM25 construído: {len(todos_artigos)} artigos")
    print(f"   📁 Salvo em: {BM25_INDEX_PATH}")
    
    return bm25, todos_artigos


# =========================================================
# 🔎 BUSCA BM25
# =========================================================

class BM25Searcher:
    """Wrapper para busca BM25 com cache"""
    
    def __init__(self, index_path=BM25_INDEX_PATH):
        self.bm25 = None
        self.corpus = None
        self.artigos = None
        
        if os.path.exists(index_path):
            self.carregar_indice(index_path)
        else:
            print("⚠️ Índice BM25 não encontrado. Execute bm25_index.py primeiro.")
    
    def carregar_indice(self, index_path):
        """Carrega índice BM25 do disco"""
        with open(index_path, "rb") as f:
            data = pickle.load(f)
        
        self.bm25 = data["bm25"]
        self.corpus = data["corpus"]
        self.artigos = data["artigos"]
        
        print(f"✅ Índice BM25 carregado: {len(self.artigos)} artigos")
    
    def buscar(self, pergunta, top_k=10, filtro_fonte=None):
        """
        Busca BM25 por pergunta
        Retorna lista de artigos ordenados por score
        """
        if not self.bm25:
            return []
        
        # Tokeniza a pergunta
        query_tokens = pergunta.lower().split()
        
        # Busca BM25
        scores = self.bm25.get_scores(query_tokens)
        
        # Ordena por score (maior primeiro)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
        
        # Filtra e formata resultados
        resultados = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            
            art = self.artigos[idx]
            
            # Aplica filtro de fonte se especificado
            if filtro_fonte and art["fonte"] != filtro_fonte:
                continue
            
            resultados.append({
                "id": art["id"],
                "numero": art["numero"],
                "texto": art["texto"],
                "fonte": art["fonte"],
                "lei": art["lei"],
                "ano": art["ano"],
                "score_bm25": float(scores[idx]),
                "tipo": "bm25"
            })
            
            if len(resultados) >= top_k:
                break
        
        return resultados


# =========================================================
# 🚀 EXECUÇÃO
# =========================================================

if __name__ == "__main__":
    bm25, artigos = construir_indice_bm25()
    
    if bm25:
        # Teste rápido
        searcher = BM25Searcher()
        resultados = searcher.buscar("responsabilidade civil", top_k=5)
        
        print("\n🔍 Teste de busca BM25:")
        for r in resultados[:3]:
            print(f"  {r['id']} (score: {r['score_bm25']:.2f})")
            print(f"  {r['texto'][:100]}...\n")
