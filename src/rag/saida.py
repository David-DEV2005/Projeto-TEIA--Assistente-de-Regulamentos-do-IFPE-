"""Etapa 3.3: validacao da saida JSON do LLM com Pydantic."""
import json

from pydantic import BaseModel, Field


class Resposta(BaseModel):
    encontrou: bool
    resposta: str = Field(min_length=1)
    trechos_usados: list[int] = Field(default_factory=list)


def extrair_json(texto):
    """Pega o objeto JSON mesmo que o modelo tenha escrito texto ou ``` em volta."""
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini == -1 or fim <= ini:
        raise ValueError("a saída não contém um objeto JSON")
    return json.loads(texto[ini:fim + 1])


def validar(texto, n_trechos):
    """Devolve uma Resposta valida; descarta numeros de trecho que nao existem."""
    r = Resposta.model_validate(extrair_json(texto))
    r.trechos_usados = sorted({i for i in r.trechos_usados if 1 <= i <= n_trechos})
    return r