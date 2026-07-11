"""
Pipeline genérico: PDF (URL ou arquivo local) → Markdown → base de conhecimento.

Uso básico:
  # A partir de URL
  python scripts/ingest_pdf.py --url "https://..." --name "resolucao-cepe-123"

  # A partir de arquivo local
  python scripts/ingest_pdf.py --file /caminho/para/norma.pdf --name "politica-tcc"

  # Sem re-ingestão automática (só cria o .md)
  python scripts/ingest_pdf.py --url "..." --name "doc" --no-ingest

  # Forçar sobrescrever arquivo existente
  python scripts/ingest_pdf.py --url "..." --name "doc" --force

Flags:
  --url URL          URL do PDF para baixar
  --file PATH        Caminho local de um PDF já baixado
  --name SLUG        Nome do arquivo de saída (sem extensão), ex: resolucao-123
  --kb-path PATH     Pasta destino na base (padrão: "Infos Adms UnB")
  --no-ingest        Não executa re-ingestão após criar o .md
  --force            Sobrescreve o .md se já existir
  --dry-run          Mostra o que faria, sem alterar nada
  --raw              Salva o texto bruto sem tentar formatar
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    import requests
except ImportError:
    print("❌ requests não instalado. Execute: pip install requests")
    sys.exit(1)

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FCTEBot/2.0; "
        "+https://github.com/caiobraga/FCTEBot)"
    )
}

DEFAULT_KB = ROOT / "Infos Adms UnB"


# ─── Download ────────────────────────────────────────────────────────────────

def download_pdf(url: str, dest: Optional[Path] = None) -> Path:
    """Baixa o PDF e retorna o caminho local."""
    if dest is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        dest = Path(tmp.name)
        tmp.close()

    print(f"⬇️  Baixando: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    resp.raise_for_status()

    with open(dest, "wb") as f:
        total = 0
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            total += len(chunk)
    print(f"   {total / 1024:.1f} KB baixados → {dest.name}")
    return dest


# ─── Extração de texto ────────────────────────────────────────────────────────

def extract_with_pdfplumber(pdf_path: Path) -> str:
    """
    Extrai texto do PDF usando pdfplumber.
    Trata tabelas separadamente (mais estruturado) e texto livre.
    """
    parts: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_parts: list[str] = []

            # Tenta extrair tabelas primeiro
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                }
            )

            if tables:
                for table in tables:
                    for row in table:
                        clean_row = [
                            (cell or "").replace("\n", " ").strip()
                            for cell in row
                        ]
                        if any(clean_row):
                            page_parts.append(" | ".join(clean_row))
            else:
                # Fallback: texto bruto
                text = page.extract_text(x_tolerance=2, y_tolerance=4)
                if text:
                    page_parts.append(text)

            if page_parts:
                parts.append(f"\n<!-- página {i} -->\n" + "\n".join(page_parts))

    return "\n".join(parts)


def extract_with_pypdf(pdf_path: Path) -> str:
    """Fallback simples usando pypdf (sem suporte a tabelas)."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"\n<!-- página {i} -->\n{text}")
    return "\n".join(pages)


SCANNED_THRESHOLD_CHARS_PER_PAGE = 50  # abaixo disso → provável PDF escaneado


def detect_scanned(text: str, n_pages: int) -> bool:
    """Retorna True se o PDF parece ser uma imagem escaneada (sem texto real)."""
    if n_pages == 0:
        return True
    return len(text.strip()) / n_pages < SCANNED_THRESHOLD_CHARS_PER_PAGE


def extract_with_ocr(pdf_path: Path) -> str:
    """
    OCR via pytesseract + pdf2image.
    Só utilizado como último recurso para PDFs escaneados.
    Requer: pip install pytesseract pdf2image
            apt install tesseract-ocr tesseract-ocr-por poppler-utils
    """
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except ImportError:
        return ""

    print("🔍 PDF escaneado detectado — usando OCR (pode demorar)...")
    pages = convert_from_path(str(pdf_path), dpi=200)
    texts = []
    for i, img in enumerate(pages, start=1):
        text = pytesseract.image_to_string(img, lang="por")
        if text.strip():
            texts.append(f"\n<!-- página {i} (OCR) -->\n{text}")
    return "\n".join(texts)


def extract_text(pdf_path: Path) -> str:
    """
    Escolhe o melhor extrator:
    1. pdfplumber (tabelas + texto) — para PDFs digitais
    2. pypdf (fallback simples)
    3. OCR via pytesseract — somente se PDF for escaneado
    """
    n_pages = 0

    if HAS_PDFPLUMBER:
        print("📖 Extraindo com pdfplumber (tabelas + texto)...")
        with pdfplumber.open(str(pdf_path)) as pdf:
            n_pages = len(pdf.pages)
        raw = extract_with_pdfplumber(pdf_path)
    elif HAS_PYPDF:
        print("📖 Extraindo com pypdf (texto simples)...")
        reader = PdfReader(str(pdf_path))
        n_pages = len(reader.pages)
        raw = extract_with_pypdf(pdf_path)
    else:
        print("❌ Nenhum extrator de PDF disponível.")
        print("   Execute: pip install pdfplumber")
        sys.exit(1)

    # Verificar se o PDF tem texto real
    if detect_scanned(raw, n_pages):
        print(f"⚠️  PDF com pouco texto ({len(raw.strip())} chars em {n_pages} páginas).")
        print("   Pode ser um PDF escaneado (imagem sem camada de texto).")

        # Tentar OCR se disponível
        ocr_text = extract_with_ocr(pdf_path)
        if ocr_text.strip():
            print("✅ OCR concluído.")
            return ocr_text

        print("   Para habilitar OCR:")
        print("     pip install pytesseract pdf2image")
        print("     sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils")
        print("   O arquivo .md será criado com o conteúdo parcial disponível.")

    return raw


# ─── Formatação Markdown ──────────────────────────────────────────────────────

# Padrões para identificar seções / títulos
_HEADING_PATTERNS = [
    re.compile(r"^(artigo|art\.?\s*\d+)", re.IGNORECASE),
    re.compile(r"^(capítulo|cap\.?\s*[IVXLC\d]+)", re.IGNORECASE),
    re.compile(r"^(seção|seção\s+[IVXLC\d]+)", re.IGNORECASE),
    re.compile(r"^(resolução|portaria|instrução\s+normativa)", re.IGNORECASE),
    re.compile(r"^(calendário\s+\w+\s+\d{4})", re.IGNORECASE),
]

_DATE_PATTERN = re.compile(r"\d{2}/\d{2}(?:/\d{2,4})?")
_PIPE_ROW = re.compile(r".+\|.+")


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 5 or len(stripped) > 120:
        return False
    # Linha toda maiúscula (como títulos de seção em PDFs)
    if stripped.isupper() and len(stripped.split()) <= 8:
        return True
    return any(p.match(stripped) for p in _HEADING_PATTERNS)


def format_as_markdown(raw: str, title: str, source: str) -> str:
    """
    Converte texto bruto (extraído de PDF) em Markdown estruturado.

    Heurísticas aplicadas:
    - Linhas totalmente maiúsculas → ## cabeçalho
    - Linhas com padrão "palavra | data | descrição" → bullet formatado
    - Linhas com datas → bullet
    - Comentários de página removidos do output final
    - Linhas muito curtas (artefatos de PDF) → ignoradas
    """
    today = datetime.now().strftime("%d/%m/%Y")
    lines_out: list[str] = [
        f"# {title}",
        "",
        f"> Fonte: {source}  ",
        f"> Atualização: {today}",
        "",
    ]

    prev_blank = False

    for line in raw.splitlines():
        # Remover comentários de página
        if line.startswith("<!-- página"):
            continue

        stripped = line.strip()

        # Linhas vazias
        if not stripped:
            if not prev_blank:
                lines_out.append("")
            prev_blank = True
            continue
        prev_blank = False

        # Artefatos de PDF (linhas muito curtas sem conteúdo útil)
        if len(stripped) < 3:
            continue

        # Cabeçalho de seção
        if _is_heading(stripped):
            lines_out.append(f"\n## {stripped.title()}")
            continue

        # Linha de tabela com pipe (vem de pdfplumber)
        if _PIPE_ROW.match(stripped):
            cols = [c.strip() for c in stripped.split("|")]
            cols = [c for c in cols if c]
            if cols:
                # Primeira coluna pode ser o ator (Estudante, STI etc.)
                # Formata como bullet para facilitar leitura do RAG
                lines_out.append("- " + " — ".join(cols))
            continue

        # Linha com data → bullet
        if _DATE_PATTERN.search(stripped):
            lines_out.append(f"- {stripped}")
            continue

        # Texto normal
        lines_out.append(stripped)

    return "\n".join(lines_out)


# ─── Utilitários ─────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Garante que o nome seja seguro para usar como nome de arquivo."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    return name


def run_ingest() -> bool:
    """Executa ingest.py --force. Retorna True se bem-sucedido."""
    print("\n🔄 Re-indexando base de conhecimento...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ingest.py"), "--force"],
        cwd=str(ROOT),
    )
    return result.returncode == 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FCTEBot — Ingestão de PDF genérico para a base de conhecimento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="URL do PDF")
    source.add_argument("--file", type=Path, help="Caminho local do PDF")

    parser.add_argument(
        "--name",
        required=True,
        help="Slug do arquivo de saída (sem extensão). Ex: resolucao-cepe-123",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Título para o cabeçalho do Markdown (padrão: derivado do --name)",
    )
    parser.add_argument(
        "--kb-path",
        type=Path,
        default=DEFAULT_KB,
        help=f"Pasta da base de conhecimento (padrão: {DEFAULT_KB})",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Não executa re-ingestão após criar o .md",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve o .md se já existir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que faria, sem alterar arquivos",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Salva o texto bruto sem tentar formatar",
    )

    args = parser.parse_args()

    slug = slugify(args.name)
    title = args.title or slug.replace("-", " ").title()
    dest_md = args.kb_path / f"{slug}.md"
    source_label = args.url or str(args.file)

    print("=" * 60)
    print(f"FCTEBot — Ingestão de PDF")
    print("=" * 60)
    print(f"  Fonte : {source_label}")
    print(f"  Saída : {dest_md}")
    print(f"  Título: {title}")

    # Verificar se destino já existe
    if dest_md.exists() and not args.force:
        print(f"\n⚠️  Arquivo já existe: {dest_md}")
        print("   Use --force para sobrescrever.")
        sys.exit(1)

    if args.dry_run:
        print("\n[--dry-run] Nenhuma alteração foi feita.")
        return

    # 1. Obter o PDF
    if args.url:
        pdf_path = download_pdf(args.url)
        cleanup = True
    else:
        pdf_path = args.file
        if not pdf_path.exists():
            print(f"❌ Arquivo não encontrado: {pdf_path}")
            sys.exit(1)
        cleanup = False

    # 2. Extrair texto
    raw = extract_text(pdf_path)

    if not raw.strip():
        print("⚠️  PDF sem texto extraível (pode ser uma imagem escaneada).")
        print("   Considere usar OCR: pip install pytesseract pdf2image")
        if cleanup:
            pdf_path.unlink(missing_ok=True)
        sys.exit(1)

    # 3. Formatar
    if args.raw:
        content = f"# {title}\n\n> Fonte: {source_label}\n\n{raw}"
    else:
        content = format_as_markdown(raw, title, source_label)

    # 4. Salvar
    args.kb_path.mkdir(parents=True, exist_ok=True)
    dest_md.write_text(content, encoding="utf-8")
    print(f"\n✅ Markdown salvo: {dest_md}")
    print(f"   Tamanho: {len(content):,} caracteres")

    # Preview
    print(f"\n📝 Preview (primeiras 25 linhas):")
    print("-" * 40)
    for line in content.splitlines()[:25]:
        print(line)
    print("...")

    # Limpar PDF temporário se baixamos
    if cleanup:
        pdf_path.unlink(missing_ok=True)

    # 5. Re-ingestão
    if not args.no_ingest:
        ok = run_ingest()
        if ok:
            print("\n🎉 PDF ingerido e base re-indexada com sucesso!")
        else:
            print("\n⚠️  Re-ingestão falhou. Execute manualmente:")
            print("   python scripts/ingest.py --force")
    else:
        print("\n📌 Re-ingestão pulada (--no-ingest).")
        print("   Quando pronto: python scripts/ingest.py --force")


if __name__ == "__main__":
    main()
