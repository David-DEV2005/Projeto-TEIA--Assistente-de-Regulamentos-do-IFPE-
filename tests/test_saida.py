"""Testes da validacao da saida do LLM (Etapa 3.3)."""
import pytest

from src.rag.saida import extrair_json, validar


def test_json_limpo():
    r = validar('{"encontrou": true, "resposta": "Até 13/11/2026.", "trechos_usados": [1]}', 3)
    assert r.encontrou and r.resposta == "Até 13/11/2026." and r.trechos_usados == [1]


def test_json_dentro_de_bloco_de_codigo_e_com_texto_em_volta():
    texto = 'Claro!\n```json\n{"encontrou": false, "resposta": "Não encontrei.", "trechos_usados": []}\n```\nEspero ter ajudado.'
    assert validar(texto, 5).encontrou is False


def test_descarta_trechos_inexistentes_e_repetidos():
    r = validar('{"encontrou": true, "resposta": "x", "trechos_usados": [3, 1, 1, 9, 0]}', 4)
    assert r.trechos_usados == [1, 3]


def test_trechos_usados_ausente_vira_lista_vazia():
    assert validar('{"encontrou": true, "resposta": "x"}', 4).trechos_usados == []


def test_texto_sem_json_gera_erro():
    with pytest.raises(ValueError):
        extrair_json("o prazo é 13/11")


def test_json_quebrado_gera_erro():
    with pytest.raises(Exception):
        validar('{"encontrou": true, "resposta": ', 3)


def test_resposta_vazia_ou_campo_ausente_gera_erro():
    with pytest.raises(Exception):
        validar('{"encontrou": true, "resposta": "", "trechos_usados": []}', 3)
    with pytest.raises(Exception):
        validar('{"resposta": "x", "trechos_usados": []}', 3)
        