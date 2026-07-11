"""
Atualização inteligente dos normativos da UnB na base de conhecimento.

Estratégia:
  1. Scraping da página de normativos (saa.unb.br/legislacao-de-graduacao/)
  2. Comparação com manifesto local (data/normativos_manifest.json)
     - URL mudou?   → novo normativo publicado (substitui o anterior)
     - URL igual?   → verifica hash SHA-256 do PDF (conteúdo alterado?)
     - Sem mudança → ignora (zero downloads desnecessários)
  3. Baixa e ingere apenas o que mudou
  4. Atualiza o manifesto

Detecção por tipo de documento:
  - Normativos SAA  → URL muda quando há nova resolução (mais confiável)
  - Estatuto UnB    → URL fixa → detectar por hash SHA-256 do conteúdo
  - Outros PDFs     → hash SHA-256

Uso:
  python scripts/update_normativos.py              # verifica e atualiza
  python scripts/update_normativos.py --dry-run    # só verifica, não altera
  python scripts/update_normativos.py --force      # re-baixa tudo (ignora manifesto)
  python scripts/update_normativos.py --no-ingest  # atualiza .md sem re-indexar
  python scripts/update_normativos.py --list       # mostra manifesto atual

Cron sugerido (mensal):
  0 8 1 * * python /caminho/FCTEBot/scripts/update_normativos.py >> /caminho/FCTEBot/logs/normativos.log 2>&1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Execute: pip install requests beautifulsoup4")
    sys.exit(1)

# ─── Configuração ─────────────────────────────────────────────────────────────

SAA_NORMATIVOS_URL = "https://saa.unb.br/legislacao-de-graduacao/"
KB_DIR = ROOT / "Infos Adms UnB"
MANIFEST_PATH = ROOT / "data" / "normativos_manifest.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FCTEBot/2.0; "
        "+https://github.com/caiobraga/FCTEBot)"
    )
}

# Documentos com URL fixa (não mudam de endereço, apenas de conteúdo)
FIXED_URL_DOCS: list[dict] = [
    {
        "tema": "Estatuto e Regimento Geral da UnB",
        "slug": "estatuto-regimento-unb",
        "url": "https://unb.br/images/Documentos/Estatuto_e_Regimento_Geral_UnB.pdf",
        "fonte": "https://unb.br/",
    },
]

# Mapeamento: texto do link → slug do arquivo .md
# Garante nomes de arquivo estáveis mesmo que a resolução mude de número
SLUG_MAP: dict[str, str] = {
    "Aluno Especial":                              "normativo-aluno-especial",
    "Aluno Refugiado":                             "normativo-aluno-refugiado",
    "Aproveitamento de Estudos":                   "normativo-aproveitamento-estudos",
    "Confirmação de curso":                        "normativo-confirmacao-curso",
    "Distribuição de Vagas":                       "normativo-distribuicao-vagas",
    "IRA e MP":                                    "normativo-ira-mp",
    "Nome Social":                                 "normativo-nome-social",
    "Orientação acadêmica e condições de desligamento": "normativo-orientacao-desligamento",
    "Outorga Antecipada":                          "normativo-outorga-antecipada",
    "Reintegração":                                "normativo-reintegracao",
    "Revisão de menção":                           "normativo-revisao-mencao",
    "Trancamentos":                                "normativo-trancamentos",
    "Transferência Obrigatória":                   "normativo-transferencia-obrigatoria",
    # Aproveitamento tem dois documentos (resolução + instrução)
    "Instrução CEG":                               "normativo-instrucao-aproveitamento",
}


# ─── Manifesto ────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    """Carrega o manifesto local. Retorna {} se não existir."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def hash_file(path: Path) -> str:
    """SHA-256 de um arquivo."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def hash_url_content(url: str) -> Optional[str]:
    """
    Tenta obter o hash do PDF remoto via HEAD (Content-Length + Last-Modified)
    como proxy rápido antes de baixar.
    Retorna None se o servidor não suportar HEAD.
    """
    try:
        resp = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        length = resp.headers.get("Content-Length", "")
        last_mod = resp.headers.get("Last-Modified", "")
        if length or last_mod:
            return hashlib.md5(f"{url}|{length}|{last_mod}".encode()).hexdigest()
    except requests.RequestException:
        pass
    return None


# ─── Scraping ────────────────────────────────────────────────────────────────

def fetch_normativos() -> list[dict]:
    """
    Faz scraping da página de normativos SAA.
    Retorna lista de {tema, resolucao, url, slug}.
    """
    print(f"🌐 Acessando {SAA_NORMATIVOS_URL} ...")
    resp = requests.get(SAA_NORMATIVOS_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[dict] = []

    # O conteúdo da página está em blockquotes: "Tema: Resolução X"
    for bq in soup.find_all(["blockquote", "p"]):
        link = bq.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        if not href.endswith(".pdf"):
            continue

        url = href if href.startswith("http") else "https://saa.unb.br" + href
        resolucao = link.get_text(strip=True)

        # Extrair o tema (texto antes do ":")
        full_text = bq.get_text(separator=" ", strip=True)
        tema = full_text.split(":")[0].strip().lstrip("> ").strip()

        # Determinar slug estável
        slug = _resolve_slug(tema, resolucao)

        results.append({
            "tema": tema,
            "resolucao": resolucao,
            "url": url,
            "slug": slug,
            "fonte": SAA_NORMATIVOS_URL,
        })

    return results


def _resolve_slug(tema: str, resolucao: str) -> str:
    """Retorna o slug estável para um normativo dado seu tema."""
    for key, slug in SLUG_MAP.items():
        if key.lower() in tema.lower() or key.lower() in resolucao.lower():
            return slug
    # Fallback: gerar slug a partir da resolução
    slug = resolucao.lower()
    for ch in "º/. ":
        slug = slug.replace(ch, "-")
    return "normativo-" + slug.strip("-")


# ─── Detecção de mudanças ─────────────────────────────────────────────────────

class ChangeReason:
    NOVO = "novo"                  # Nunca foi ingerido
    URL_MUDOU = "url_mudou"        # Resolução mais nova substituiu a anterior
    CONTEUDO_MUDOU = "conteudo"    # Mesmo URL, mas PDF diferente
    SEM_MUDANCA = "sem_mudanca"    # Tudo igual

def detect_changes(
    normativos: list[dict],
    fixed: list[dict],
    manifest: dict,
    force: bool,
) -> list[dict]:
    """
    Retorna somente os documentos que precisam ser (re)baixados.
    Cada item inclui campo 'reason' com o motivo.
    """
    to_update: list[dict] = []
    all_docs = normativos + fixed

    for doc in all_docs:
        slug = doc["slug"]
        url = doc["url"]
        entry = manifest.get(slug, {})

        if force:
            to_update.append({**doc, "reason": "force"})
            continue

        if not entry:
            to_update.append({**doc, "reason": ChangeReason.NOVO})
            continue

        if entry.get("url") != url:
            to_update.append({
                **doc,
                "reason": ChangeReason.URL_MUDOU,
                "old_resolucao": entry.get("resolucao", "?"),
                "old_url": entry.get("url", ""),
            })
            continue

        # URL igual: verificar conteúdo via proxy (HEAD request)
        remote_proxy = hash_url_content(url)
        local_proxy = entry.get("content_proxy")

        if remote_proxy and local_proxy and remote_proxy != local_proxy:
            to_update.append({**doc, "reason": ChangeReason.CONTEUDO_MUDOU})
            continue

    return to_update


# ─── Download e ingestão ──────────────────────────────────────────────────────

def download_and_hash(url: str) -> tuple[Path, str]:
    """Baixa um PDF para um arquivo temporário e retorna (path, sha256)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    dest = Path(tmp.name)

    print(f"   ⬇️  {url.split('/')[-1]}")
    resp = requests.get(url, headers=HEADERS, timeout=90, stream=True)
    resp.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=16384):
            f.write(chunk)

    file_hash = hash_file(dest)
    return dest, file_hash


def run_ingest_pdf(pdf_path: Path, doc: dict, no_ingest: bool) -> int:
    """Chama ingest_pdf.py para converter e indexar o PDF."""
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "ingest_pdf.py"),
        "--file", str(pdf_path),
        "--name", doc["slug"],
        "--title", doc.get("resolucao") or doc["tema"],
        "--kb-path", str(KB_DIR),
        "--force",
        "--no-ingest",  # sempre sem re-ingest aqui; re-indexamos em lote depois
    ]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def run_ingest() -> bool:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ingest.py"), "--force"],
        cwd=str(ROOT),
    )
    return result.returncode == 0


# ─── Relatório ───────────────────────────────────────────────────────────────

def print_manifest_summary(manifest: dict) -> None:
    if not manifest:
        print("  (manifesto vazio — nenhum normativo ingerido ainda)")
        return

    print(f"\n{'Slug':45} {'Resolução':30} {'Atualizado em'}")
    print("-" * 95)
    for slug, entry in sorted(manifest.items()):
        res = entry.get("resolucao") or entry.get("tema", "?")
        dt = entry.get("ingested_at", "?")[:10]
        print(f"  {slug:43} {res[:28]:30} {dt}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FCTEBot — Atualização inteligente dos normativos UnB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Só verifica mudanças, sem baixar ou alterar nada")
    parser.add_argument("--force", action="store_true",
                        help="Re-baixa todos os documentos ignorando o manifesto")
    parser.add_argument("--no-ingest", action="store_true",
                        help="Cria/atualiza os .md mas não re-indexa a base")
    parser.add_argument("--list", action="store_true",
                        help="Mostra o manifesto atual e sai")
    args = parser.parse_args()

    print("=" * 60)
    print("FCTEBot — Atualização dos Normativos UnB")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    manifest = load_manifest()

    if args.list:
        print("\n📋 Manifesto atual:")
        print_manifest_summary(manifest)
        return

    # 1. Scraping dos normativos SAA
    try:
        normativos = fetch_normativos()
    except requests.RequestException as e:
        print(f"❌ Erro ao acessar {SAA_NORMATIVOS_URL}: {e}")
        sys.exit(1)

    print(f"\n📋 Normativos encontrados no site: {len(normativos)}")
    for n in normativos:
        local_ok = (KB_DIR / f"{n['slug']}.md").exists()
        marker = "✅" if local_ok else "🆕"
        print(f"   {marker} [{n['resolucao']:30}] {n['tema']}")

    print(f"\n📄 Documentos de URL fixa: {len(FIXED_URL_DOCS)}")
    for d in FIXED_URL_DOCS:
        local_ok = (KB_DIR / f"{d['slug']}.md").exists()
        marker = "✅" if local_ok else "🆕"
        print(f"   {marker} {d['tema']}")

    # 2. Detectar o que mudou
    print("\n🔍 Verificando mudanças (HEAD requests)...")
    to_update = detect_changes(normativos, FIXED_URL_DOCS, manifest, args.force)

    if not to_update:
        print("\n✅ Nenhuma mudança detectada. Base já está atualizada.")
        print(f"   Manifesto: {MANIFEST_PATH}")
        return

    print(f"\n🆕 Documentos para atualizar ({len(to_update)}):")
    for doc in to_update:
        reason_label = {
            "novo":           "🆕 novo",
            "url_mudou":      "🔄 resolução atualizada",
            "conteudo":       "📝 conteúdo alterado",
            "force":          "⚡ forçado",
        }.get(doc.get("reason", ""), "?")

        print(f"   {reason_label:30} → {doc.get('resolucao') or doc['tema']}")
        if doc.get("reason") == "url_mudou":
            print(f"              anterior: {doc.get('old_resolucao', '?')}")

    if args.dry_run:
        print("\n[--dry-run] Nenhuma alteração foi feita.")
        return

    # 3. Baixar e ingerir
    errors: list[str] = []
    updated: list[str] = []

    for doc in to_update:
        print(f"\n{'─'*50}")
        print(f"⚙️  Processando: {doc.get('resolucao') or doc['tema']}")

        try:
            pdf_path, file_hash = download_and_hash(doc["url"])
        except requests.RequestException as e:
            print(f"   ❌ Falha no download: {e}")
            errors.append(doc["slug"])
            continue

        # Checar se o conteúdo mudou mesmo com mesma URL
        stored_hash = manifest.get(doc["slug"], {}).get("sha256")
        if stored_hash and stored_hash == file_hash and doc.get("reason") != "force":
            print(f"   ℹ️  Conteúdo idêntico (hash SHA-256 igual). Pulando.")
            pdf_path.unlink(missing_ok=True)
            continue

        rc = run_ingest_pdf(pdf_path, doc, no_ingest=True)
        pdf_path.unlink(missing_ok=True)

        if rc != 0:
            print(f"   ❌ Falha ao processar o PDF.")
            errors.append(doc["slug"])
            continue

        # Proxy para HEAD (evitar re-download na próxima verificação)
        content_proxy = hash_url_content(doc["url"])

        # Atualizar manifesto
        manifest[doc["slug"]] = {
            "tema": doc["tema"],
            "resolucao": doc.get("resolucao") or doc["tema"],
            "url": doc["url"],
            "sha256": file_hash,
            "content_proxy": content_proxy,
            "fonte": doc.get("fonte", ""),
            "ingested_at": datetime.now().isoformat(),
        }
        save_manifest(manifest)
        updated.append(doc["slug"])
        print(f"   ✅ OK — manifesto atualizado")

    # 4. Re-ingestão em lote
    if updated and not args.no_ingest:
        print(f"\n🔄 Re-indexando {len(updated)} documento(s) atualizado(s)...")
        ok = run_ingest()
        if ok:
            print("✅ Base re-indexada com sucesso!")
        else:
            print("⚠️  Re-ingestão falhou. Execute: python scripts/ingest.py --force")
    elif args.no_ingest:
        print("\n📌 Re-ingestão pulada. Execute: python scripts/ingest.py --force")

    # 5. Resumo
    print(f"\n{'='*60}")
    print(f"Resumo:")
    print(f"  Atualizados : {len(updated)}")
    print(f"  Erros       : {len(errors)}")
    if errors:
        print(f"  Falhas      : {', '.join(errors)}")
    print(f"  Manifesto   : {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
