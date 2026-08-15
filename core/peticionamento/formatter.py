"""Formatação dos dados da biblioteca para exibição/envio."""


class FormatterPeticoes:
    @staticmethod
    def formatar_requisitos(dados):
        dados = dados or {}
        linhas = ["REQUISITOS — " + dados.get("nome_peca", ""), ""]
        for r in dados.get("requisitos", []):
            obr = r.get("obrigatoriedade", "")
            emoji = "🔴" if obr == "obrigatorio" else ("🟡" if obr == "condicional" else "⚪")
            linhas.append(f"{emoji} {r.get('nome', '?')} [{r.get('codigo', '?')}]")
            linhas.append(f"   tipo: {r.get('tipo_dado', '?')} | {obr}")
            if r.get("descricao"):
                linhas.append(f"   {r.get('descricao')}")
            linhas.append("")
        return "\n".join(linhas)

    @staticmethod
    def formatar_fundamentos(dados):
        dados = dados or {}
        linhas = ["FUNDAMENTOS", ""]
        for f in dados.get("fundamentos", []):
            linhas.append(f"⚖️ {f.get('nome', '?')} [{f.get('codigo', '?')}]")
            if f.get("descricao"):
                linhas.append(f"   {f.get('descricao')}")
            linhas.append("")
        return "\n".join(linhas)

    @staticmethod
    def formatar_checklist(dados):
        dados = dados or {}
        linhas = ["CHECKLIST", ""]
        for item in dados.get("itens", []):
            obrig = item.get("obrigatorio", item.get("obrigatoriedade") == "obrigatorio")
            emoji = "✅" if obrig else "⬜"
            linhas.append(f"{emoji} {item.get('codigo', '?')}")
            desc = item.get("descricao", item.get("nome", ""))
            if desc:
                linhas.append(f"   {desc}")
            linhas.append("")
        return "\n".join(linhas)

    @staticmethod
    def formatar_kit(area, peca, estrutura, requisitos, fundamentos, checklist):
        estrutura = estrutura or {}
        nome = estrutura.get("nome", peca.replace("_", " ").title())
        return "\n".join([
            f"📦 KIT COMPLETO — {nome}",
            "",
            f"• {len(estrutura.get('secoes', []))} seções na estrutura",
            f"• {len((requisitos or {}).get('requisitos', []))} requisitos",
            f"• {len((fundamentos or {}).get('fundamentos', []))} fundamentos",
            f"• {sum(len(etapa.get('itens', [])) for etapa in (checklist or {}).get('etapas', []))} itens de checklist",
            "• instruções para IA (.md)",
            "• esqueleto (.md)",
            "",
            "Arquivos enviados abaixo. ✔",
        ])
