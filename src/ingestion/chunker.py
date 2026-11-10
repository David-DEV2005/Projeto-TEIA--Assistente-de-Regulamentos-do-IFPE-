"""Etapa 1.3: chunks por titulo numerado do edital.

Entradas (geradas antes):
  data/processed/paginas.json   <- extrair_texto.py
  data/processed/tabelas.json   <- tabelas.py
  data/curado/*.json            <- conteudo escrito a mao
Saida:
  data/processed/chunks.json
"""
import json
import re
import statistics
from pathlib import Path

PROC = Path("data/processed")
CURADO = Path("data/curado")

DOCUMENTO = "Edital de Ingresso IFPE 2027.1"
MAX_CHARS = 1800
TITULO_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\s+(.+)$")
ANEXO_RE = re.compile(r"^ANEXO ([A-Z])$")


# ----------------------------------------------------------------- utilitarios
def caixa_alta(texto):
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 4 and all(c.isupper() for c in letras)


def reconhecer_titulo(linha):
    m = TITULO_RE.match(linha)
    if m and caixa_alta(m.group(2)):
        return m.group(1), m.group(2).strip()
    return None


def tipo_selecao(numero):
    """Divisao oficial do edital (pagina 3): 1-6 geral, 7-13 prova,
    14-17 historico escolar, 18-21 resultados e matricula (geral)."""
    capitulo = int(numero.split(".")[0])
    if 7 <= capitulo <= 13:
        return "prova"
    if 14 <= capitulo <= 17:
        return "historico"
    return "geral"


def reflow(linhas):
    """Junta linhas quebradas no meio da frase, preservando itens de lista."""
    saida = []
    for l in linhas:
        if (
            saida
            and not re.search(r"[.:;!?)”]$", saida[-1])
            and l[:1].islower()
        ):
            saida[-1] = saida[-1].rstrip("-") + ("" if saida[-1].endswith("-") else " ") + l
        else:
            saida.append(l)
    return saida


def dividir(linhas_pag, max_chars=MAX_CHARS):
    """linhas_pag = [(pagina, linha)]. Divide em partes de ate max_chars."""
    partes, atual, tam = [], [], 0
    for pag, l in linhas_pag:
        if atual and tam + len(l) > max_chars:
            partes.append(atual)
            atual, tam = [], 0
        atual.append((pag, l))
        tam += len(l) + 1
    if atual:
        partes.append(atual)
    return partes


def novo_chunk(base, linhas_pag, parte, total):
    # marcadores soltos ("●" sozinho numa linha) nao carregam informacao
    linhas = reflow([l for _, l in linhas_pag if l.strip() not in {"●", "•"}])
    corpo = "\n".join(linhas)
    c = dict(base)
    c.update({
        "pagina_inicio": linhas_pag[0][0],
        "pagina_fim": linhas_pag[-1][0],
        "texto": corpo,
        "parte": f"{parte}/{total}" if total > 1 else None,
    })
    c["texto_indexado"] = f"{DOCUMENTO}. {base['caminho']}.\n{corpo}"
    return c


# ----------------------------------------------------------------- estrutura
def localizar_limites(paginas):
    """Devolve (primeira_pag_corpo, primeira_pag_anexos, paginas_sumario)."""
    corpo_ini = anexos_ini = None
    for p in paginas:
        for l in p["texto"].splitlines():
            if corpo_ini is None and reconhecer_titulo(l) == ("1", "QUAIS SÃO OS CURSOS OFERECIDOS?"):
                corpo_ini = p["pagina"]
            if anexos_ini is None and l.strip() == "ANEXOS" and corpo_ini:
                anexos_ini = p["pagina"]
    sumario = [
        p["pagina"] for p in paginas
        if p["texto"].startswith("SUMÁRIO") or (
            p["pagina"] > 3 and corpo_ini and p["pagina"] < corpo_ini
        )
    ]
    return corpo_ini, anexos_ini, sumario


def chunks_introducao(paginas, sumario):
    """Paginas 2 e 3 (antes do sumario): apresentacao e estrutura do edital."""
    saida = []
    for p in paginas:
        limite = min(sumario) if sumario else 4
        if p["pagina"] == 1 or p["pagina"] >= limite:
            continue
        linhas = [(p["pagina"], l) for l in p["texto"].splitlines() if l.strip()]
        if not linhas:
            continue
        partes = dividir(linhas)
        for k, parte in enumerate(partes, 1):
            base = {
                "id": f"intro-p{p['pagina']}" + (f"-{k}" if len(partes) > 1 else ""),
                "tipo": "texto", "item": "Introdução",
                "titulo": f"Apresentação do edital (página {p['pagina']})",
                "caminho": f"Introdução do edital (página {p['pagina']})",
                "secao": "Introdução", "tipo_selecao": "geral", "indexar": True,
            }
            saida.append(novo_chunk(base, parte, k, len(partes)))
    return saida


def chunks_corpo(paginas, corpo_ini, anexos_ini):
    # 1) varre as linhas e separa por titulo
    secoes, atual, pilha = [], None, []
    for p in paginas:
        if not (corpo_ini <= p["pagina"] < anexos_ini):
            continue
        linhas = [l for l in p["texto"].splitlines() if l.strip()]
        i = 0
        while i < len(linhas):
            t = reconhecer_titulo(linhas[i])
            if t:
                numero, titulo = t
                # titulo quebrado em mais de uma linha
                while (
                    i + 1 < len(linhas)
                    and not titulo.endswith(("?", ".", ":"))
                    and caixa_alta(linhas[i + 1])
                    and not reconhecer_titulo(linhas[i + 1])
                    and len(linhas[i + 1]) < 60
                    and not linhas[i + 1].rstrip().endswith(":")
                ):
                    titulo += " " + linhas[i + 1].strip()
                    i += 1
                nivel = numero.count(".") + 1
                pilha = [x for x in pilha if x[0] < nivel] + [(nivel, numero, titulo)]
                atual = {
                    "numero": numero, "titulo": titulo,
                    "caminho": " > ".join(f"{n} {tt}" for _, n, tt in pilha),
                    "secao": f"{pilha[0][1]} {pilha[0][2]}",
                    "linhas": [], "pagina_titulo": p["pagina"],
                }
                secoes.append(atual)
            elif atual is not None:
                atual["linhas"].append((p["pagina"], linhas[i]))
            i += 1

    # 2) transforma cada secao em chunk(s)
    saida = []
    for s in secoes:
        if sum(len(l) for _, l in s["linhas"]) < 25:
            continue                       # titulo sem corpo proprio (so agrupa subitens)
        partes = dividir(s["linhas"])
        for k, parte in enumerate(partes, 1):
            base = {
                "id": f"item-{s['numero']}" + (f"-{k}" if len(partes) > 1 else ""),
                "tipo": "texto", "item": s["numero"], "titulo": s["titulo"],
                "caminho": s["caminho"], "secao": s["secao"],
                "tipo_selecao": tipo_selecao(s["numero"]), "indexar": True,
            }
            saida.append(novo_chunk(base, parte, k, len(partes)))
    return saida


def chunks_anexos(paginas, anexos_ini, cobertas):
    """Anexos C em diante (texto corrido). A e B vem das tabelas."""
    inicios = []
    for p in paginas:
        if p["pagina"] < anexos_ini:
            continue
        linhas = [l for l in p["texto"].splitlines() if l.strip()]
        if linhas and "FICHA TÉCNICA" in linhas[0]:
            fim = p["pagina"]
            break
        if linhas and ANEXO_RE.match(linhas[0]):
            inicios.append((ANEXO_RE.match(linhas[0]).group(1), p["pagina"]))
    else:
        fim = paginas[-1]["pagina"] + 1
    saida = []
    for k, (letra, ini) in enumerate(inicios):
        if cobertas[0] <= ini <= cobertas[1]:
            continue
        ate = (inicios[k + 1][1] if k + 1 < len(inicios) else fim) - 1
        linhas_pag = []
        for p in paginas:
            if ini <= p["pagina"] <= ate:
                linhas_pag += [(p["pagina"], l) for l in p["texto"].splitlines() if l.strip()]
        linhas_pag = [(pg, l) for pg, l in linhas_pag if not ANEXO_RE.match(l)]
        if not linhas_pag:
            continue
        titulo = linhas_pag[0][1]
        corpo_txt = " ".join(l for _, l in linhas_pag)
        formulario = corpo_txt.count("____") >= 3
        partes = dividir(linhas_pag)
        for j, parte in enumerate(partes, 1):
            base = {
                "id": f"anexo-{letra}" + (f"-{j}" if len(partes) > 1 else ""),
                "tipo": "anexo", "item": f"Anexo {letra}", "titulo": titulo,
                "caminho": f"Anexo {letra} - {titulo}", "secao": f"Anexo {letra}",
                "tipo_selecao": "geral", "formulario": formulario,
                "indexar": not formulario,
            }
            saida.append(novo_chunk(base, parte, j, len(partes)))
    return saida


def chunks_tabelas():
    caminho = PROC / "tabelas.json"
    if not caminho.exists():
        return [], (0, 0)
    dados = json.load(open(caminho, encoding="utf-8"))
    saida = []
    for n, it in enumerate(dados["itens"], 1):
        tab = it.get("tabela", "")
        sel = "prova" if "Provas" in tab else "historico" if "Análise" in tab else "geral"
        base = {
            "id": f"tabela-{it['anexo']}-p{it['pagina']}-{n:03d}",
            "tipo": "tabela", "item": f"Anexo {it['anexo']}", "titulo": tab,
            "caminho": f"Anexo {it['anexo']} - {tab}", "secao": f"Anexo {it['anexo']}",
            "tipo_selecao": sel, "indexar": True,
            "pagina_inicio": it["pagina"], "pagina_fim": it["pagina"],
            "texto": it["texto"], "parte": None,
        }
        base["texto_indexado"] = f"{DOCUMENTO}. {it['texto']}"
        saida.append(base)
    return saida, tuple(dados["paginas_cobertas"])


def chunks_curados():
    saida = []
    for arq in sorted(CURADO.glob("*.json")) if CURADO.exists() else []:
        for it in json.load(open(arq, encoding="utf-8"))["itens"]:
            base = {
                "id": it["id"], "tipo": "curado", "item": it["item"],
                "titulo": it["titulo"], "caminho": f"{it['item']} {it['titulo']}",
                "secao": it["item"], "tipo_selecao": "geral", "indexar": True,
                "pagina_inicio": it["pagina"], "pagina_fim": it["pagina"],
                "texto": it["texto"], "parte": None,
            }
            base["texto_indexado"] = f"{DOCUMENTO}. {it['titulo']}.\n{it['texto']}"
            saida.append(base)
    return saida


def main():
    dados = json.load(open(PROC / "paginas.json", encoding="utf-8"))
    paginas = dados["paginas"]
    corpo_ini, anexos_ini, sumario = localizar_limites(paginas)
    print(f"Corpo: p{corpo_ini}-p{anexos_ini - 1} | Anexos a partir da p{anexos_ini} | Sumário: p{sumario}")

    tabelas, cobertas = chunks_tabelas()
    chunks = (
        chunks_introducao(paginas, sumario)
        + chunks_corpo(paginas, corpo_ini, anexos_ini)
        + tabelas
        + chunks_anexos(paginas, anexos_ini, cobertas or (0, 0))
        + chunks_curados()
    )
    for c in chunks:
        c["documento"] = DOCUMENTO

    saida = {"documento": DOCUMENTO, "arquivo": dados["arquivo"], "chunks": chunks}
    with open(PROC / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    # ---- resumo
    por_tipo = {}
    for c in chunks:
        por_tipo.setdefault(c["tipo"], []).append(c)
    print(f"Total de chunks: {len(chunks)} | indexáveis: {sum(c['indexar'] for c in chunks)}")
    for t, lista in por_tipo.items():
        print(f"  {t}: {len(lista)}")
    tam = [len(c["texto"]) for c in chunks if c["tipo"] == "texto"]
    print(f"Chunks de texto: min {min(tam)}, mediana {int(statistics.median(tam))}, máx {max(tam)} caracteres")
    print("Excluídos do índice (formulários):",
          sorted({c["item"] for c in chunks if not c["indexar"]}))


if __name__ == "__main__":
    main()