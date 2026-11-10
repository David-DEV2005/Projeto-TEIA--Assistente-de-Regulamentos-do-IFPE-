"""Etapa 1.5: testes da ingestao (chunks do edital).
Precisam dos arquivos gerados antes:
  python src/ingestion/extrair_texto.py
  python src/ingestion/tabelas.py
  python src/ingestion/chunker.py
  python src/ingestion/chunker_fixo.py
"""
import json
import re
from pathlib import Path

import pytest

from src.ingestion.chunker import caixa_alta, reconhecer_titulo, tipo_selecao

PROC = Path("data/processed")
TOTAL_PAGINAS = 82


def carregar(nome):
    caminho = PROC / nome
    if not caminho.exists():
        pytest.skip(f"{nome} não encontrado: rode os scripts de ingestão antes")
    return json.load(open(caminho, encoding="utf-8"))


@pytest.fixture(scope="module")
def chunks():
    return carregar("chunks.json")["chunks"]


@pytest.fixture(scope="module")
def indexaveis(chunks):
    return [c for c in chunks if c["indexar"]]


# ------------------------------------------------------------ funcoes de titulo
def test_reconhece_titulo_numerado_em_caixa_alta():
    assert reconhecer_titulo("10.4 ORIENTAÇÕES SOBRE A PROVA") == ("10.4", "ORIENTAÇÕES SOBRE A PROVA")
    assert reconhecer_titulo("6.6.1 LISTA PRELIMINAR DA VERIFICAÇÃO ÉTNICO-RACIAL")[0] == "6.6.1"


def test_nao_confunde_nota_de_rodape_com_titulo():
    assert reconhecer_titulo("1 De acordo com a Lei nº 12.711, de 29 de agosto de 2012") is None
    assert reconhecer_titulo("Quando terminar a prova, o candidato deverá entregar") is None


def test_caixa_alta():
    assert caixa_alta("COMO SERÁ A AEM?")
    assert not caixa_alta("Como será a AEM?")


def test_tipo_selecao_segue_a_divisao_do_edital():
    assert tipo_selecao("3") == "geral"
    assert tipo_selecao("7.1") == "prova"
    assert tipo_selecao("12.2.1") == "prova"
    assert tipo_selecao("14.3") == "historico"
    assert tipo_selecao("17.4") == "historico"
    assert tipo_selecao("18") == "geral"
    assert tipo_selecao("21.8") == "geral"


# ------------------------------------------------------------ chunks de texto
def test_item_10_4_esta_na_pagina_30(chunks):
    achados = [c for c in chunks if c["item"] == "10.4"]
    assert achados, "item 10.4 não encontrado"
    assert achados[0]["pagina_inicio"] == 30
    assert "ORIENTAÇÕES SOBRE A PROVA" in achados[0]["titulo"]


def test_todos_os_capitulos_tem_algum_chunk(chunks):
    itens = {c["item"] for c in chunks if c["tipo"] == "texto"}
    for n in range(1, 22):
        assert any(i == str(n) or i.startswith(f"{n}.") for i in itens), f"capítulo {n} sem chunk"


def test_quantidade_razoavel_de_itens(chunks):
    itens = {c["item"] for c in chunks if c["id"].startswith("item-")}
    assert 95 <= len(itens) <= 110


def test_menu_repetido_nao_entrou_nos_chunks(chunks):
    for c in chunks:
        assert "1 Cursos 2 Vagas" not in c["texto"]
        assert "21 Importante Anexos" not in c["texto"]


def test_sumario_nao_virou_chunk(chunks):
    for c in chunks:
        assert not c["texto"].lstrip().startswith("SUMÁRIO")
        assert c["pagina_inicio"] not in (4, 5)


# ------------------------------------------------------------ tabelas
def test_soma_das_vagas_bate_com_o_total_em_todas_as_linhas(chunks):
    linhas = [c for c in chunks if c["tipo"] == "tabela" and c["item"] == "Anexo A"]
    assert len(linhas) >= 120
    for c in linhas:
        m = re.search(r"(\d+) vagas no total\. Distribuição por grupo de vaga: (.+?)\.", c["texto"])
        assert m, c["texto"][:120]
        total = int(m.group(1))
        soma = sum(int(x) for x in re.findall(r"[A-Z_]+ (\d+)", m.group(2)))
        assert soma == total, c["texto"][:160]


def test_data_fica_junto_da_atividade_no_cronograma(chunks):
    def tem(atividade, data):
        return any(
            c["tipo"] == "tabela" and atividade in c["texto"] and data in c["texto"]
            for c in chunks
        )
    assert tem("Pagamento da taxa de inscrição", "14/10 a 13/11/2026")
    assert tem("Divulgação do gabarito definitivo", "14/12/2026")
    assert tem("Aplicação da prova", "6/12/2026")


def test_calendarios_distinguem_prova_e_analise(chunks):
    cal = [c for c in chunks if c["tipo"] == "tabela" and "Calendário" in c["titulo"]]
    assert {c["tipo_selecao"] for c in cal} == {"prova", "historico"}


def test_conteudo_curado_da_pagina_12(chunks):
    c = next(c for c in chunks if c["id"] == "curado-p12-exemplo-40-vagas")
    assert "LB_Q 1" in c["texto"] and "Total: 40 vagas" in c["texto"]


# ------------------------------------------------------------ propriedades gerais
def test_ids_unicos(chunks):
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_indexaveis_nao_estao_vazios(indexaveis):
    assert len(indexaveis) > 300
    for c in indexaveis:
        assert len(c["texto"].strip()) >= 30, c["id"]


def test_paginas_validas(chunks):
    for c in chunks:
        assert 1 <= c["pagina_inicio"] <= c["pagina_fim"] <= TOTAL_PAGINAS, c["id"]


def test_tamanho_maximo(chunks):
    for c in chunks:
        if c["tipo"] in ("texto", "anexo"):
            assert len(c["texto"]) <= 2000, c["id"]


def test_formularios_ficam_fora_do_indice(chunks):
    for c in chunks:
        if c.get("formulario"):
            assert c["indexar"] is False


def test_todo_chunk_tem_campos_de_citacao(indexaveis):
    for c in indexaveis:
        for campo in ("id", "tipo", "item", "titulo", "caminho", "tipo_selecao",
                      "pagina_inicio", "pagina_fim", "texto", "texto_indexado"):
            assert c.get(campo) not in (None, ""), (c["id"], campo)


# ------------------------------------------------------------ linha de base
def test_chunks_fixos_sao_validos():
    dados = carregar("chunks_fixos.json")
    fixos = dados["chunks"]
    assert len(fixos) > 150
    assert all(c["texto"].strip() for c in fixos)
    assert all(a["pagina_inicio"] <= b["pagina_inicio"] for a, b in zip(fixos, fixos[1:]))
    assert max(len(c["texto"]) for c in fixos) <= dados["parametros"]["tamanho"]