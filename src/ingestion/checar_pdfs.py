from pathlib import Path
import pymupdf

for pdf in sorted(Path("data/raw").glob("*.pdf")):
    doc = pymupdf.open(pdf)
    com_texto = sum(1 for p in doc if len(p.get_text().strip()) > 50)
    print(f"{pdf.name}: {len(doc)} páginas, {com_texto} com texto")
    amostra = doc[min(3, len(doc) - 1)].get_text()[:300].replace("\n", " ")
    print("  amostra:", amostra)