"""Etapa 1.2: tabelas dos anexos do edital -> uma frase por linha.
Cobre o Anexo A (cursos e vagas) e o Anexo B (cronogramas e inicio das aulas).
O resto do documento continua sendo tratado como texto corrido.
"""
import json
import re
import warnings
from pathlib import Path

import pdfplumber

warnings.filterwarnings("ignore")

RAW = Path("data/raw")
OUT = Path("data/processed")

PEQUENAS = {"em", "de", "do", "da", "dos", "das", "e", "no", "na", "para", "a", "o", "ao"}
DATA_RE = re.compile(r"\d{1,2}º?/\d{1,2}/\d{4}")


def cel(c):
    return re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip()


def titulo(texto):
    """CAIXA ALTA -> Caixa Alta, mantendo preposicoes em minuscula."""
    palavras = cel(texto).lower().split()
    saida = " ".join(
        p if (i > 0 and p in PEQUENAS) else p.capitalize() for i, p in enumerate(palavras)
    )
    return saida.replace("Ead", "EaD")


def arrumar_url(texto):
    return re.sub(r"ifpe\.edu\.\s+br", "ifpe.edu.br", texto)


def localizar_anexos(pdf):
    """Devolve {'A': (pag_ini, pag_fim), ...} procurando 'ANEXO X' no topo das paginas."""
    inicios = {}
    for i, pagina in enumerate(pdf.pages, start=1):
        linhas = [l.strip() for l in (pagina.extract_text() or "").splitlines() if l.strip()]
        for l in linhas[:3]:
            m = re.fullmatch(r"ANEXO ([A-Z])", l)
            if m and m.group(1) not in inicios:
                inicios[m.group(1)] = i
    letras = sorted(inicios)
    fim = {}
    for k, letra in enumerate(letras):
        proximo = inicios[letras[k + 1]] if k + 1 < len(letras) else len(pdf.pages) + 1
        fim[letra] = (inicios[letra], proximo - 1)
    return fim


def notas_de_rodape(pagina):
    notas = {}
    for l in (pagina.extract_text() or "").splitlines():
        m = re.match(r"^(\d{1,2}) ([A-Za-zÀ-ú].{30,})$", l.strip())
        if m:
            notas[m.group(1)] = m.group(2)
    return notas


# ---------------------------------------------------------------- Anexo A
def anexo_a(pdf, paginas):
    itens, avisos = [], []
    titulo_atual, codigos = None, None
    ultimo_campus, rotulo = "", "campus"
    for n in paginas:
        pagina = pdf.pages[n - 1]
        notas = notas_de_rodape(pagina)
        for t in pagina.extract_tables():
            if not t or max(len(r) for r in t) != 15:
                continue
            for r in t:
                r = [cel(c) for c in r]
                if r[0] and not any(r[1:]):          # linha de titulo da tabela
                    titulo_atual = titulo(r[0])
                    continue
                if r[0] in ("CAMPUS", "POLO"):       # cabecalho (1a linha)
                    rotulo = r[0].lower()
                    continue
                if r[3] == "AC":                      # cabecalho (2a linha): codigos
                    codigos = r[3:14]
                    continue
                if not (r[3].isdigit() and r[14].isdigit()):
                    continue
                campus = r[0] or ultimo_campus
                ultimo_campus = campus
                nota_n = None
                m = re.fullmatch(r"(.*?[A-ZÇÃÕÁÉÍÓÚ])(\d{1,2})", campus)
                if m:
                    campus, nota_n = m.group(1), m.group(2)
                curso, turno, total = r[1], r[2], int(r[14])
                valores = [int(x) for x in r[3:14]]
                if sum(valores) != total:
                    avisos.append(f"p{n} {campus} / {curso}: soma {sum(valores)} != total {total}")
                dist = "; ".join(f"{c} {v}" for c, v in zip(codigos, valores))
                turno_txt = "sem turno definido" if "NÃO SE APLICA" in turno else f"turno {turno.lower()}"
                frase = (
                    f"Anexo A ({titulo_atual}): {rotulo} {titulo(campus)}, curso {titulo(curso)}, "
                    f"{turno_txt}: {total} vagas no total. "
                    f"Distribuição por grupo de vaga: {dist}."
                )
                if nota_n and nota_n in notas:
                    frase += f" Nota: {notas[nota_n]}"
                itens.append({
                    "tipo": "tabela", "anexo": "A", "pagina": n,
                    "tabela": titulo_atual, "campus": titulo(campus),
                    "curso": titulo(curso), "turno": turno.lower(),
                    "total_vagas": total, "texto": frase,
                })
    return itens, avisos


# ---------------------------------------------------------------- Anexo B
def modalidade_acima(pagina, bbox):
    """Procura 'PARA CURSOS COM ...' no texto acima da tabela."""
    topo = max(bbox[1], 1)
    texto = pagina.crop((0, 0, pagina.width, topo)).extract_text() or ""
    achados = re.findall(r"PARA CURSOS COM ([^\n]+)", texto)
    return titulo(achados[-1]) if achados else None


def eh_tabela_de_aulas(t):
    """Titulo 'PREVISAO...' ou linhas no formato CAMPUS | DATA | CAMPUS | DATA."""
    if t[0][0].startswith("PREVISÃO"):
        return True
    return any(DATA_RE.search(r[3]) for r in t) and all(
        DATA_RE.search(r[1]) or not r[1] for r in t
    )


def anexo_b(pdf, paginas):
    itens = []
    modalidade, etapa = None, ""
    for n in paginas:
        pagina = pdf.pages[n - 1]
        for ft in pagina.find_tables():
            t = [[cel(c) for c in r] for r in ft.extract()]
            if not t:
                continue
            ncol = max(len(r) for r in t)
            if ncol != 4:
                continue
            cab = t[0]
            if cab == ["ETAPA", "ATIVIDADE", "DATA", "LOCAL"]:   # novo calendario
                modalidade = modalidade_acima(pagina, ft.bbox) or modalidade
                etapa = ""
                t = t[1:]
            if eh_tabela_de_aulas(t):
                for r in t:                               # previsao de inicio das aulas
                    for campo, data in ((r[0], r[1]), (r[2], r[3])):
                        if campo and DATA_RE.search(data):
                            itens.append({
                                "tipo": "tabela", "anexo": "B", "pagina": n,
                                "tabela": "Previsão de início das aulas", "campus": campo,
                                "texto": f"Anexo B, previsão de início das aulas: campus {campo}: {data}.",
                            })
                    if r[0].startswith("IMPORTANTE"):
                        itens.append({
                            "tipo": "tabela", "anexo": "B", "pagina": n,
                            "tabela": "Previsão de início das aulas", "texto": r[0],
                        })
                continue
            for r in t:                                   # calendario (ETAPA/ATIVIDADE/DATA/LOCAL)
                if r[0]:
                    etapa = r[0]
                if not r[1] or not r[2]:
                    continue
                data, local = arrumar_url(r[2]), arrumar_url(r[3])
                if not local and "http" in data:
                    data, url = data.split("http", 1)
                    data, local = data.strip(), "http" + url
                local = local or "não informado na tabela"
                frase = (
                    f"Anexo B, calendário do processo (cursos com {modalidade}): "
                    f"etapa {titulo(etapa)}, atividade: {r[1]}. "
                    f"Data: {data}. Local: {local}."
                )
                itens.append({
                    "tipo": "tabela", "anexo": "B", "pagina": n,
                    "tabela": f"Calendário - cursos com {modalidade}",
                    "etapa": titulo(etapa), "atividade": r[1], "texto": frase,
                })
    return itens


def main():
    pdf_path = next(RAW.glob("*.pdf"))
    with pdfplumber.open(pdf_path) as pdf:
        anexos = localizar_anexos(pdf)
        print("Anexos localizados:", {k: v for k, v in anexos.items() if k in "ABC"})
        a_ini, a_fim = anexos["A"]
        b_ini, b_fim = anexos["B"]
        itens_a, avisos = anexo_a(pdf, range(a_ini, a_fim + 1))
        itens_b = anexo_b(pdf, range(b_ini, b_fim + 1))

    itens = itens_a + itens_b
    print(f"Anexo A: {len(itens_a)} linhas de curso | Anexo B: {len(itens_b)} linhas")
    print(f"Divergências de soma de vagas: {len(avisos)}")
    for a in avisos:
        print("  !", a)

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "tabelas.json", "w", encoding="utf-8") as f:
        json.dump({"arquivo": pdf_path.name, "itens": itens,
                   "paginas_cobertas": [a_ini, b_fim]}, f, ensure_ascii=False, indent=1)
    return itens


if __name__ == "__main__":
    main()