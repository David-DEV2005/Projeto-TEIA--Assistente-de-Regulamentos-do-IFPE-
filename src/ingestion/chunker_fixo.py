"""Etapa 1.4: chunker de tamanho fixo (linha de base para o experimento da Fase 6).
Corta o texto limpo em janelas de TAMANHO caracteres com SOBREPOSICAO, sem usar
titulos nem tratar tabelas. Usa as mesmas paginas do chunker estruturado
(exclui capa, sumario, ficha tecnica e contracapa) para a comparacao ser justa.

Entrada: data/processed/paginas.json
Saida:   data/processed/chunks_fixos.json
"""
import json
import statistics
from bisect import bisect_right
from pathlib import Path

PROC = Path("data/processed")
DOCUMENTO = "Edital de Ingresso IFPE 2027.1"
TAMANHO = 800
SOBREPOSICAO = 100


def paginas_validas(paginas):
    """Descarta capa (p1), sumario, ficha tecnica e paginas vazias."""
    corpo_ini = next(
        p["pagina"] for p in paginas
        if any(l.startswith("1 QUAIS SÃO OS CURSOS OFERECIDOS?") for l in p["texto"].splitlines())
    )
    sumario = {p["pagina"] for p in paginas if 3 < p["pagina"] < corpo_ini}
    saida = []
    for p in paginas:
        if p["pagina"] == 1 or p["pagina"] in sumario or not p["texto"].strip():
            continue
        if p["texto"].lstrip().startswith("FICHA TÉCNICA"):
            continue
        saida.append(p)
    return saida


def dividir_fixo(paginas, tamanho=TAMANHO, sobreposicao=SOBREPOSICAO):
    texto, inicios = "", []          # inicios[i] = (offset, pagina)
    for p in paginas:
        inicios.append((len(texto), p["pagina"]))
        texto += p["texto"].strip() + "\n"
    offsets = [o for o, _ in inicios]

    def pagina_de(pos):
        return inicios[max(bisect_right(offsets, pos) - 1, 0)][1]

    chunks, pos, passo = [], 0, tamanho - sobreposicao
    while pos < len(texto):
        fim = min(pos + tamanho, len(texto))
        if fim < len(texto):                          # evita cortar no meio de uma palavra
            espaco = texto.rfind(" ", pos + passo, fim)
            fim = espaco if espaco != -1 else fim
        pedaco = texto[pos:fim].strip()
        if pedaco:
            chunks.append({
                "id": f"fixo-{len(chunks) + 1:04d}",
                "tipo": "texto_fixo",
                "texto": pedaco,
                "texto_indexado": f"{DOCUMENTO}.\n{pedaco}",
                "pagina_inicio": pagina_de(pos),
                "pagina_fim": pagina_de(max(fim - 1, pos)),
                "tipo_selecao": "geral",
                "indexar": True,
                "documento": DOCUMENTO,
            })
        if fim >= len(texto):
            break
        pos = max(fim - sobreposicao, pos + 1)
    return chunks


def main():
    dados = json.load(open(PROC / "paginas.json", encoding="utf-8"))
    paginas = paginas_validas(dados["paginas"])
    chunks = dividir_fixo(paginas)
    saida = {
        "documento": DOCUMENTO, "arquivo": dados["arquivo"],
        "parametros": {"tamanho": TAMANHO, "sobreposicao": SOBREPOSICAO},
        "chunks": chunks,
    }
    with open(PROC / "chunks_fixos.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    tam = [len(c["texto"]) for c in chunks]
    print(f"Páginas usadas: {len(paginas)} | chunks fixos: {len(chunks)}")
    print(f"Tamanho: min {min(tam)}, mediana {int(statistics.median(tam))}, máx {max(tam)} caracteres")
    print(f"Parâmetros: tamanho={TAMANHO}, sobreposição={SOBREPOSICAO}")


if __name__ == "__main__":
    main()