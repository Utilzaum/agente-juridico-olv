"""
gerar_dicionario_limpo.py
Parser inteligente que lida com verbetes na mesma linha ou em linhas separadas.
"""
import json
import re

def parse_dicionario(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    lines = text.split('\n')
    verbetes = []
    current_title = None
    current_def = []
    
    # Regex para capturar verbetes na mesma linha (ex: "Absolvição Reconhecimento da...")
    same_line_regex = re.compile(r'^([A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç0-9\s\-]{1,40}?)\s{2,}([A-ZÁÉÍÓÚÂÊÔÃÕÇ].+)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Pula cabeçalhos/rodapés
        if line in ["Dicionário Jurídico", "VERBETE DEFINIÇÃO ÍCONE", "Dê sua opinião sobre o Dicionário Jurídico"]:
            continue
        if line.startswith("Todos A B C"):
            continue
        if line.startswith("Referência Bibliográfica"):
            break
            
        # 1. Verifica se é verbete de linha única
        match = same_line_regex.match(line)
        if match:
            if current_title and current_def:
                verbetes.append({"titulo": current_title, "texto": " ".join(current_def).strip()})
            current_title = match.group(1).strip()
            current_def = [match.group(2).strip()]
            continue
            
        # 2. Verifica se é um novo título (curto, sem ponto final, começa com maiúscula/número)
        if len(line) < 50 and not line.endswith('.') and not line.endswith(','):
            if current_title and current_def:
                verbetes.append({"titulo": current_title, "texto": " ".join(current_def).strip()})
            current_title = line
            current_def = []
        else:
            # 3. É continuação da definição
            if current_title:
                current_def.append(line)
                
    # Salva o último
    if current_title and current_def:
        verbetes.append({"titulo": current_title, "texto": " ".join(current_def).strip()})
        
    # Limpeza final (remove duplicatas e lixo)
    clean_verbetes = []
    seen_titles = set()
    for v in verbetes:
        t = v['titulo'].strip()
        txt = v['texto'].strip()
        if t in seen_titles or len(t) < 2 or len(txt) < 10:
            continue
        seen_titles.add(t)
        clean_verbetes.append({"titulo": t, "texto": txt})
        
    return clean_verbetes

if __name__ == "__main__":
    print("🔄 Processando dicionario_texto.txt...")
    verbetes = parse_dicionario("dicionario/dicionario_texto.txt")
    
    with open("dicionario/dicionario_base.json", "w", encoding="utf-8") as f:
        json.dump(verbetes, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Sucesso! {len(verbetes)} verbetes limpos gerados.")
    print("🔍 Exemplo:", verbetes[0])
