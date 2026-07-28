# diagnostico_indexacao.py
"""
Script de Diagnóstico de Indexação — ChromaDB
✅ Verifica se o artigo 12 do CDC está indexado
✅ Imprime o formato REAL dos metadados (artigo, fonte)
✅ Lista amostras de cada coleção
"""
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import os

load_dotenv()

DB_PATH = "db_vetorial"
COLECAO_ARTIGOS = "legislacao_artigos"
COLECAO_BLOCOS = "legislacao_blocos"
COLECAO_DICIONARIO = "dicionario_juridico"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")


def conectar():
    modelo_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    cliente_db = chromadb.PersistentClient(path=DB_PATH)
    colecao_artigos = cliente_db.get_collection(
        name=COLECAO_ARTIGOS, embedding_function=modelo_embedding
    )
    colecao_blocos = cliente_db.get_collection(
        name=COLECAO_BLOCOS, embedding_function=modelo_embedding
    )
    colecao_dicionario = cliente_db.get_collection(
        name=COLECAO_DICIONARIO, embedding_function=modelo_embedding
    )
    return colecao_artigos, colecao_blocos, colecao_dicionario


def diagnosticar_artigo_12_cdc(colecao_artigos):
    print("\n" + "="*60)
    print("🔍 DIAGNÓSTICO: Artigo 12 do CDC")
    print("="*60)

    # Teste 1: Busca exata por metadado (como o bot faz)
    print("\n[Teste 1] Busca com where={'artigo': '12', 'fonte': 'cdc.html'}")
    try:
        resultado = colecao_artigos.get(
            where={"$and": [{"artigo": "12"}, {"fonte": "cdc.html"}]},
            limit=1
        )
        if resultado and resultado['documents']:
            print("✅ ENCONTRADO!")
            print(f"   Documento: {resultado['documents'][0][:100]}...")
            print(f"   Metadados: {resultado['metadatas'][0]}")
        else:
            print("❌ NÃO ENCONTRADO com esses critérios exatos.")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # Teste 2: Busca sem filtro de fonte
    print("\n[Teste 2] Busca com where={'artigo': '12'} (sem fonte)")
    try:
        resultado = colecao_artigos.get(
            where={"artigo": "12"},
            limit=5
        )
        if resultado and resultado['documents']:
            print(f"✅ Encontrados {len(resultado['documents'])} documentos com artigo='12':")
            for i, meta in enumerate(resultado['metadatas']):
                print(f"   [{i}] fonte={meta.get('fonte')} | artigo={meta.get('artigo')} | lei={meta.get('lei')}")
        else:
            print("❌ Nenhum documento com artigo='12'")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # Teste 3: Busca por fonte CDC (sem artigo)
    print("\n[Teste 3] Busca com where={'fonte': 'cdc.html'} (sem artigo)")
    try:
        resultado = colecao_artigos.get(
            where={"fonte": "cdc.html"},
            limit=5
        )
        if resultado and resultado['documents']:
            print(f"✅ Encontrados {len(resultado['documents'])} documentos com fonte='cdc.html':")
            for i, meta in enumerate(resultado['metadatas']):
                print(f"   [{i}] artigo={meta.get('artigo')} | tipo={meta.get('tipo')}")
        else:
            print("❌ Nenhum documento com fonte='cdc.html'")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # Teste 4: Amostra geral de metadados
    print("\n[Teste 4] Amostra geral (primeiros 10 documentos)")
    try:
        resultado = colecao_artigos.get(limit=10)
        if resultado and resultado['metadatas']:
            for i, meta in enumerate(resultado['metadatas']):
                print(f"   [{i}] artigo={repr(meta.get('artigo'))} | fonte={repr(meta.get('fonte'))} | lei={repr(meta.get('lei'))}")
        else:
            print("❌ Coleção vazia")
    except Exception as e:
        print(f"❌ Erro: {e}")


def diagnosticar_distancias(colecao_artigos):
    print("\n" + "="*60)
    print("📏 DIAGNÓSTICO: Distâncias de Embedding")
    print("="*60)

    consultas = [
        "art. 12 CDC",
        "responsabilidade civil fornecedor",
        "prazo contestação",
        "tutela de urgência"
    ]

    for consulta in consultas:
        print(f"\n[Consulta] '{consulta}'")
        try:
            resultado = colecao_artigos.query(
                query_texts=[consulta],
                n_results=5
            )
            if resultado and resultado['distances'] and resultado['distances'][0]:
                for i, dist in enumerate(resultado['distances'][0]):
                    meta = resultado['metadatas'][0][i]
                    print(f"   [{i}] distância={dist:.4f} | artigo={meta.get('artigo')} | fonte={meta.get('fonte')}")
            else:
                print("   ❌ Sem resultados")
        except Exception as e:
            print(f"   ❌ Erro: {e}")


if __name__ == "__main__":
    print("🚀 Iniciando diagnóstico de indexação...")
    colecao_artigos, colecao_blocos, colecao_dicionario = conectar()

    diagnosticar_artigo_12_cdc(colecao_artigos)
    diagnosticar_distancias(colecao_artigos)

    print("\n" + "="*60)
    print("✅ Diagnóstico concluído.")
    print("="*60)
