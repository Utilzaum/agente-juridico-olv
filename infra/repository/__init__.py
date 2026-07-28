# infra/repository/__init__.py
"""
Pacote de Repositórios (Camada de Persistência - Sprint 1)
----------------------------------------------------------
Este arquivo expõe a API pública da nossa infraestrutura de dados.
Ele esconde a complexidade interna (em qual arquivo cada classe está) 
e oferece uma interface limpa para o resto da aplicação.
"""

# 1. Conexão e Controle Transacional (Tarefa 2)
from .connection import conectar, Transaction

# 2. Modelos de Domínio (Tarefa 1)
from .models import Publicacao, Evento, PipelineExecucao

# 3. Repositórios Específicos (Tarefas 3, 4, 5 e 6)
from .publicacoes import PublicacoesRepository
from .eventos import EventosRepository
from .cursores import CursorRepository
from .auditoria import AuditoriaRepository
from .pipeline import PipelineRepository

# 4. Definição da API Pública (Boas práticas)
# Isso garante que se alguém der um `from infra.repository import *`, 
# ele só puxe o que é essencial.
__all__ = [
    # Core
    "conectar",
    "Transaction",
    
    # Models
    "Publicacao",
    "Evento",
    "PipelineExecucao",
    
    # Repos
    "PublicacoesRepository",
    "EventosRepository",
    "CursorRepository",
    "AuditoriaRepository",
    "PipelineRepository",
]
