"""Carregador da Biblioteca de Petições OLV."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class BibliotecaLoader:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._cache = {}

    def listar_areas(self) -> List[str]:
        if not self.base_dir.exists():
            return []
        return sorted(
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    def listar_pecas(self, area: str) -> List[str]:
        area_dir = self.base_dir / area
        if not area_dir.exists():
            return []
        return sorted(
            d.name for d in area_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    def carregar_estrutura(self, area, peca):
        return self._json(area, peca, "estrutura.json")

    def carregar_requisitos(self, area, peca):
        return self._json(area, peca, "requisitos.json")

    def carregar_fundamentos(self, area, peca):
        return self._json(area, peca, "fundamentos.json")

    def carregar_checklist(self, area, peca):
        return self._json(area, peca, "checklist.json")

    def carregar_instrucoes_ia(self, area, peca):
        return self._texto(area, peca, "instrucoes_ia.md")

    def carregar_esqueleto(self, area, peca):
        return self._texto(area, peca, "esqueleto.md")

    def _json(self, area, peca, arquivo) -> Optional[Dict[str, Any]]:
        chave = f"{area}/{peca}/{arquivo}"
        if chave in self._cache:
            return self._cache[chave]
        caminho = self.base_dir / area / peca / arquivo
        if not caminho.exists():
            return None
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            self._cache[chave] = dados
            return dados
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar {caminho}: {e}")
            return None

    def _texto(self, area, peca, arquivo) -> Optional[str]:
        chave = f"{area}/{peca}/{arquivo}"
        if chave in self._cache:
            return self._cache[chave]
        caminho = self.base_dir / area / peca / arquivo
        if not caminho.exists():
            return None
        try:
            texto = caminho.read_text(encoding="utf-8")
            self._cache[chave] = texto
            return texto
        except IOError as e:
            print(f"Erro ao carregar {caminho}: {e}")
            return None
