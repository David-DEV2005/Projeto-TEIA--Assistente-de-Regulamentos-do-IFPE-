"""Etapa 2.4: busca por palavras (BM25) e busca hibrida (vetorial + BM25).

Uso:
  python src/indice/busca_hibrida.py "pergunta" [k] [titulo|fixo] [prova|historico|-] [vetorial|bm25|hibrida]
Exemplo:
  python src/indice/busca_hibrida.py "O que significa a sigla LB_PPI?" 5 titulo - hibrida
No codigo:
  from src.indice.busca_hibrida import buscar_com_modo
"""
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PROC = Path("data/processed")
ARQUIVOS = {"titulo": "chunks.json", "fixo": "chunks_fixos.json"}
STOPWORDS = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre
e ou que se ao aos a as ja nao mais muito ate como qual quais quando onde quem quanto
eu me meu minha seu sua nosso voce ser sao foi sera ter tem posso pode podem deve devo
isso essa esse esta este aqui la ha so tambem entre apos antes durante
""".split())


# --------------------------------------------------------------- texto -> termos
SUFIXOS = sorted("""
amentos imentos mentos amento imento mento acoes icoes coes acao icao cao adores adoras
ador adora idades idade mente aveis avel iveis ivel ando endo indo ados adas ado ada
idos idas ido ida antes ante ar er ir ou ei am em as os es s a o e
""".split(), key=len, reverse=True)


def radical(palavra):
    """Stemmer simples para o portugues (sem acento): pagar/pagamento -> pag."""
    for suf in SUFIXOS:
        minimo = 5 if suf in ("mento", "mentos") else 3     # documentos nao vira "docu"
        if palavra.endswith(suf) and len(palavra) - len(suf) >= minimo:
            return palavra[: -len(suf)]
    return palavra


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def tokenizar(texto):
    """minusculas, sem acento; mantem codigos como lb_ppi e datas; reduz o resto ao radical."""
    saida = []
    for t in re.findall(r"[a-z0-9_]+", sem_acento(texto.lower())):
        if t in STOPWORDS:
            continue
        if "_" in t or any(ch.isdigit() for ch in t):
            saida.append(t)                      # codigos e datas ficam inteiros
        else:
            saida.append(radical(t))
    return saida


# --------------------------------------------------------------- BM25 (Okapi)
class BM25:
    def __init__(self, documentos, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(d) for d in documentos]
        self.tam = [len(d) for d in documentos]
        self.media = sum(self.tam) / len(self.tam)
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log((n - f + 0.5) / (f + 0.5) + 1) for t, f in df.items()}

    def pontuar(self, consulta):
        pontos = []
        for doc, tam in zip(self.docs, self.tam):
            s = 0.0
            for t in consulta:
                if t in doc:
                    f = doc[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * tam / self.media))
            pontos.append(s)
        return pontos


_cache = {}


def indice_bm25(estrategia):
    if estrategia not in _cache:
        dados = json.load(open(PROC / ARQUIVOS[estrategia], encoding="utf-8"))
        chunks = [c for c in dados["chunks"] if c["indexar"]]
        bm25 = BM25([tokenizar(c["texto_indexado"]) for c in chunks])
        _cache[estrategia] = (bm25, chunks)
    return _cache[estrategia]


def filtro_ok(chunk, selecao):
    return not selecao or chunk["tipo_selecao"] in (selecao, "geral")


def buscar_bm25(pergunta, k=5, estrategia="titulo", selecao=None):
    bm25, chunks = indice_bm25(estrategia)
    pontos = bm25.pontuar(tokenizar(pergunta))
    ordem = sorted(range(len(chunks)), key=lambda i: pontos[i], reverse=True)
    saida = []
    for i in ordem:
        if pontos[i] <= 0:
            break
        if filtro_ok(chunks[i], selecao):
            saida.append({"id": chunks[i]["id"], "chunk": chunks[i], "score": pontos[i]})
        if len(saida) == k:
            break
    return saida


# --------------------------------------------------------------- fusao (RRF)
def fundir_rrf(listas, k, constante=60):
    """listas: {nome: [id1, id2, ...]} em ordem de relevancia."""
    total, origem = Counter(), {}
    for nome, ids in listas.items():
        for pos, id_ in enumerate(ids, 1):
            total[id_] += 1 / (constante + pos)
            origem.setdefault(id_, []).append(f"{nome}{pos}")
    ordem = sorted(total, key=lambda i: total[i], reverse=True)[:k]
    return [(i, total[i], "+".join(origem[i])) for i in ordem]


def buscar_com_modo(pergunta, k=5, estrategia="titulo", selecao=None, modo="hibrida", candidatos=20):
    """Devolve lista de dicts: id, texto, meta, score, origem."""
    from src.indice.busca import buscar            # so precisa do Ollama/Chroma nos modos vetorial e hibrida

    if modo == "vetorial":
        return [{"id": r["id"], "texto": r["texto"], "meta": r["meta"], "score": r["score"],
                 "origem": f"v{n}"} for n, r in enumerate(buscar(pergunta, k, estrategia, selecao), 1)]

    bm25 = buscar_bm25(pergunta, candidatos if modo == "hibrida" else k, estrategia, selecao)
    if modo == "bm25":
        return [{"id": r["id"], "texto": r["chunk"]["texto"], "meta": r["chunk"], "score": r["score"],
                 "origem": f"b{n}"} for n, r in enumerate(bm25[:k], 1)]

    vet = buscar(pergunta, candidatos, estrategia, selecao)
    por_id = {r["id"]: {"texto": r["texto"], "meta": r["meta"]} for r in vet}
    for r in bm25:
        por_id.setdefault(r["id"], {"texto": r["chunk"]["texto"], "meta": r["chunk"]})
    fundidos = fundir_rrf({"v": [r["id"] for r in vet], "b": [r["id"] for r in bm25]}, k)
    return [{"id": i, "texto": por_id[i]["texto"], "meta": por_id[i]["meta"], "score": s, "origem": o}
            for i, s, o in fundidos]


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python src/indice/busca_hibrida.py "pergunta" [k] [titulo|fixo] [prova|historico|-] [vetorial|bm25|hibrida]')
    a = sys.argv
    pergunta = a[1]
    k = int(a[2]) if len(a) > 2 else 5
    estrategia = a[3] if len(a) > 3 else os.getenv("CHUNKING", "titulo")
    selecao = a[4] if len(a) > 4 and a[4] != "-" else None
    modo = a[5] if len(a) > 5 else "hibrida"

    print(f"Pergunta: {pergunta} | modo: {modo} | estratégia: {estrategia}")
    for n, r in enumerate(buscar_com_modo(pergunta, k, estrategia, selecao, modo), 1):
        m = r["meta"]
        pag = m["pagina_inicio"] if m["pagina_inicio"] == m["pagina_fim"] else f"{m['pagina_inicio']}-{m['pagina_fim']}"
        print(f"\n[{n}] {r['id']} | p. {pag} | origem {r['origem']} | score {r['score']:.3f}")
        print(f"    {(m.get('caminho') or m['tipo'])[:110]}")
        print("    " + r["texto"][:240].replace("\n", " "))


if __name__ == "__main__":
    main()