#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de refatoração do sistema RAG do Agente Jurídico OLV
Objetivo: Integrar o BM25 melhorado (com enriquecimento de metadados) no bot ativo
"""
import re
from pathlib import Path
import shutil

# Configurações
BASE_DIR = Path(__file__).parent
BOT_FILE = BASE_DIR / "bot_ocr_conversacional.py"

def backup_arquivo(arquivo: Path):
    """Cria backup do arquivo original"""
    backup = arquivo.with_suffix(arquivo.suffix + '.backup')
    if arquivo.exists() and not backup.exists():
        shutil.copy2(arquivo, backup)
        print(f"✅ Backup criado: {backup.name}")

def refatorar_bot():
    """Atualiza os imports e parâmetros no bot_ocr_conversacional.py"""
    print(f"\n📝 Refatorando {BOT_FILE.name}...")
    if not BOT_FILE.exists():
        print(f"❌ Arquivo não encontrado: {BOT_FILE}")
        return False

    with open(BOT_FILE, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    # Backup antes de modificar
    backup_arquivo(BOT_FILE)
    mudancas = 0

    # 1. Atualizar o import do BM25
    if 'from bm25_index import' in conteudo:
        conteudo = re.sub(
            r'from\s+bm25_index\s+import\s+buscar_bm25_puro',
            'from infra.rag.bm25_reranker import buscar_bm25_puro',
            conteudo
        )
        print(f"  ✅ Import atualizado para infra.rag.bm25_reranker")
        mudancas += 1
    else:
        print(f"  ⚠️  Import do BM25 não encontrado no formato esperado")

    # 2. Ajustar BM25_TOP_K para 15 (para melhor RRF)
    if 'BM25_TOP_K = 5' in conteudo:
        conteudo = conteudo.replace('BM25_TOP_K = 5', 'BM25_TOP_K = 15')
        print(f"  ✅ BM25_TOP_K ajustado: 5 → 15")
        mudancas += 1
    elif 'BM25_TOP_K = 15' in conteudo:
        print(f"  ✅ BM25_TOP_K já está 15")

    # 3. Ajustar RRF_TOP_K para 8
    if 'RRF_TOP_K = 5' in conteudo:
        conteudo = conteudo.replace('RRF_TOP_K = 5', 'RRF_TOP_K = 8')
        print(f"  ✅ RRF_TOP_K ajustado: 5 → 8")
        mudancas += 1
    elif 'RRF_TOP_K = 8' in conteudo:
        print(f"  ✅ RRF_TOP_K já está 8")

    # 4. Adicionar comentário de melhoria após os imports
    melhoria_comment = """
# 🔄 REFATORAÇÃO RAG v2 - Integração BM25 melhorado
# - BM25 com enriquecimento de metadados (artigo, fonte, tipo)
# - METADATA_BOOST=50 para artigos citados na query
# - Texto enriquecido: tipo + fonte + artigo + lei + corpo
# - top_k=20 no rerank BM25, top_k=8 no RRF final
"""
    if '🔄 REFATORAÇÃO RAG v2' not in conteudo:
        linhas = conteudo.split('\n')
        for i, linha in enumerate(linhas):
            if 'import logging' in linha or 'from datetime' in linha:
                linhas.insert(i + 1, melhoria_comment)
                break
        conteudo = '\n'.join(linhas)
        print(f"  ✅ Comentário de refatoração adicionado")
        mudancas += 1

    if mudancas > 0:
        # Salvar arquivo modificado
        with open(BOT_FILE, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        print(f"  ✅ {mudancas} mudança(s) aplicada(s) com sucesso")
        return True
    else:
        print(f"  ⚠️  Nenhuma mudança necessária")
        return False

def verificar_bm25_reranker():
    """Verifica se o arquivo infra/rag/bm25_reranker.py tem as melhorias"""
    bm25_file = BASE_DIR / "infra" / "rag" / "bm25_reranker.py"
    if not bm25_file.exists():
        print(f"❌ Arquivo não encontrado: {bm25_file}")
        return False

    with open(bm25_file, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    checks = [
        ('METADATA_BOOST', 'Boost para artigos citados'),
        ('_texto_enriquecido', 'Função de enriquecimento'),
        ('DEFAULT_TOP_K = 20', 'top_k do rerank'),
        ('RRF_DEFAULT_TOP_K = 8', 'top_k do RRF'),
    ]
    print(f"\n🔍 Verificando {bm25_file.name}...")
    all_ok = True
    for termo, descricao in checks:
        if termo in conteudo:
            print(f"  ✅ {descricao}: presente")
        else:
            print(f"  ❌ {descricao}: AUSENTE")
            all_ok = False
    return all_ok

def criar_resumo_mudancas():
    """Cria arquivo de resumo das mudanças"""
    resumo = """# 🔄 Resumo da Refatoração RAG v2

## Problema Identificado
O bot RAG estava usando o `bm25_index.py` da raiz (versão genérica),
que não aplicava:
- Enriquecimento de metadados no texto
- Boost para artigos citados na query
- top_k adequado para fusão híbrida

## Mudanças Aplicadas
### 1. Import Atualizado
**Antes:**
```python
from bm25_index import buscar_bm25_puro
