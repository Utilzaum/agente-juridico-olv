"""
Extrai verbetes do Dicionário Jurídico PDF e gera JSON estruturado.
Parser híbrido: lida com títulos na mesma linha ou em linhas separadas.
"""
import os
import re
import json
import PyPDF2

# Configurações
PDF_PATH = "dicionario/dicionario-juridico.pdf"
JSON_OUTPUT = "dicionario/dicionario.json"

def extrair_verbetes_pdf(pdf_path):
    verbetes = []
    
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        texto_completo = ""
        for pagina in pdf_reader.pages:
            texto_completo += pagina.extract_text() + "\n"
    
    # 1. Limpeza de cabeçalhos e rodapés conhecidos
    texto_completo = re.sub(r'Dicionário Jurídico\s+Todos A B C.*?VERBETE\s+DEFINIÇÃO\s+ÍCONE', '', texto_completo, flags=re.DOTALL | re.IGNORECASE)
    texto_completo = re.sub(r'Dê sua opinião sobre o Dicionário Jurídico', '', texto_completo, flags=re.IGNORECASE)
    texto_completo = re.sub(r'Referência Bibliográfica:.*', '', texto_completo, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. Normaliza e filtra linhas vazias
    linhas = [linha.strip() for linha in texto_completo.split('\n') if linha.strip()]
    
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        
        # PADRÃO 1: Título e definição na MESMA linha, separados por 2+ espaços
        # Ex: "Contrafé  Cópia da petição inicial..."
        match_mesma_linha = re.match(r'^([A-ZÁÉÍÓÚÂÊÔÃÕÇ1][A-ZÁÉÍÓÚÂÊÔÃÕÇ1a-záéíóúâêôãõç1ªº\s\-\'\.]{1,45}?)\s{2,}(.+)$', linha)
        
        if match_mesma_linha:
            titulo = match_mesma_linha.group(1).strip()
            definicao = match_mesma_linha.group(2).strip()
            verbetes.append({"titulo": titulo, "texto": definicao})
            i += 1
            continue
            
        # PADRÃO 2: Título em uma linha, definição na(s) próxima(s)
        # Título é curto (< 50 chars), começa com maiúscula/número, não termina com ponto
        if len(linha) < 50 and re.match(r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ1][A-ZÁÉÍÓÚÂÊÔÃÕÇ1a-záéíóúâêôãõç1ªº\s\-\'\.]*$', linha) and not linha.rstrip().endswith('.'):
            titulo = linha
            i += 1
            definicao_partes = []
            
            # Coleta linhas de definição até encontrar um novo título potencial
            while i < len(linhas):
                proxima = linhas[i]
                
                # Se a próxima linha parecer um novo título (curta, maiúscula, sem ponto final), paramos
                if len(proxima) < 50 and re.match(r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ1][A-ZÁÉÍÓÚÂÊÔÃÕÇ1a-záéíóúâêôãõç1ªº\s\-\'\.]*$', proxima) and not proxima.rstrip().endswith('.'):
                    # Exceção: se a definição acumulada for muito curta (< 30 chars), pode ser continuação
                    if len(" ".join(definicao_partes)) < 30:
                        definicao_partes.append(proxima)
                        i += 1
                        continue
                    break # É um novo verbete
                
                definicao_partes.append(proxima)
                i += 1
            
            definicao = " ".join(definicao_partes).strip()
            
            # Filtro de qualidade: ignora títulos sem definição ou definições muito curtas
            if len(definicao) > 15:
                verbetes.append({"titulo": titulo, "texto": definicao})
        else:
            i += 1
            
    return verbetes

def salvar_json(verbetes, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(verbetes, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON salvo: {output_path}")
    print(f"   Total de verbetes: {len(verbetes)}")

def validar_extracao(verbetes):
    print("\n🔍 Exemplos de verbetes extraídos (validação):")
    for i, v in enumerate(verbetes[:6]):
        print(f"\n{i+1}. 📌 {v['titulo']}")
        print(f"   💬 {v['texto'][:80]}...")

def main():
    print("="*60)
    print("📚 EXTRAÇÃO DO DICIONÁRIO JURÍDICO (Parser Híbrido)")
    print("="*60)
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF não encontrado em: {PDF_PATH}")
        return
        
    verbetes = extrair_verbetes_pdf(PDF_PATH)
    
    if not verbetes:
        print("❌ Nenhum verbete extraído. Verifique o formato do PDF.")
        return
    
    validar_extracao(verbetes)
    salvar_json(verbetes, JSON_OUTPUT)
    
    print("\n" + "="*60)
    print("✅ EXTRAÇÃO CONCLUÍDA COM SUCESSO")
    print("="*60)
    print("Próximo passo: Validar o JSON e depois criar o indexar_dicionario.py")

if __name__ == "__main__":
    main()
