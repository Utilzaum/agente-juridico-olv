"""
indexar_dicionario.py
Lê o ativo definitivo (dicionario_base.json) e popula a coleção 'dicionario_juridico' no ChromaDB.
"""
import os
import json
import chromadb
from chromadb.utils import embedding_functions

# Configurações
JSON_PATH = "dicionario/dicionario_base.json"
DB_PATH = "db_vetorial"
COLECAO_DICIONARIO = "dicionario_juridico"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

def indexar_dicionario():
    if not os.path.exists(JSON_PATH):
        print(f"❌ Ativo não encontrado: {JSON_PATH}")
        print("   Execute 'criar_dicionario_base.py' primeiro.")
        return
    
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        verbetes = json.load(f)
    
    print(f"📖 Lendo ativo: {len(verbetes)} verbetes carregados.")
    
    # Configura ChromaDB
    modelo_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    cliente_db = chromadb.PersistentClient(path=DB_PATH)
    
    # Remove coleção existente
    try:
        cliente_db.delete_collection(COLECAO_DICIONARIO)
    except Exception:
        pass
    
    colecao = cliente_db.get_or_create_collection(
        name=COLECAO_DICIONARIO,
        embedding_function=modelo_embedding,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Prepara dados
    ids = []
    documents = []
    metadatas = []
    
    for v in verbetes:
        # ID limpo
        id_limpo = v["titulo"].lower()
        id_limpo = id_limpo.replace("ª", "a").replace("º", "o")
        id_limpo = "".join(c if c.isalnum() or c == "_" else "_" for c in id_limpo)
        id_limpo = id_limpo.strip('_')
        
        # Garante unicidade
        if id_limpo in ids:
            id_limpo = f"{id_limpo}_{ids.count(id_limpo)}"
        
        ids.append(id_limpo)
        documents.append(f"{v['titulo']}: {v['texto']}")
        metadatas.append({
            "titulo": v["titulo"],
            "categoria": "conceito",
            "fonte": "dicionario_juridico"
        })
    
    # Indexa em lotes
    for i in range(0, len(ids), 100):
        colecao.add(
            ids=ids[i:i+100],
            documents=documents[i:i+100],
            metadatas=metadatas[i:i+100]
        )
    
    print(f"🧠 Coleção '{COLECAO_DICIONARIO}' criada com sucesso no ChromaDB.")
    print(f"   📁 Banco: {DB_PATH}")

if __name__ == "__main__":
    indexar_dicionario()
