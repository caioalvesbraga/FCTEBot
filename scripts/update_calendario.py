"""
Atualização automática dos calendários acadêmicos da UnB.

Mantém na base de conhecimento:
  - O semestre VIGENTE (período letivo em andamento hoje)
  - O semestre SEGUINTE (já publicado, ainda não iniciado)
  - Semesters encerrados são marcados mas mantidos por 30 dias após o fim

Cada semestre vira um arquivo independente:
  Infos Adms UnB/calendario-2026-1.md   ← vigente ou encerrado
  Infos Adms UnB/calendario-2026-2.md   ← próximo semestre

O arquivo principal `calendario.md` é regenerado como índice
indicando qual semestre está ativo.

Uso:
  python scripts/update_calendario.py              # verifica e atualiza
  python scripts/update_calendario.py --dry-run    # só verifica
  python scripts/update_calendario.py --force      # força mesmo sem mudança
  python scripts/update_calendario.py --no-ingest  # atualiza .md mas não re-indexa

Cron mensal (WSL/Linux):
  0 9 1 * * python /caminho/FCTEBot/scripts/update_calendario.py >> /caminho/FCTEBot/logs/calendario.log 2>&1
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Compatibilidade: garante que o script acha o python correto

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Dependências faltando. Execute: pip install requests beautifulsoup4")
    sys.exit(1)


SAA_URL = "https://saa.unb.br/calendario-academico/"
KB_DIR = ROOT / "Infos Adms UnB"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FCTEBot/2.0; "
        "+https://github.com/caiobraga/FCTEBot)"
    )
}

# Períodos letivos conhecidos — usados para determinar o semestre ativo.
# O script atualiza isso automaticamente ao fazer scraping dos PDFs.
# Formato: semestre → (início_aulas, fim_aulas)
KNOWN_PERIODS: dict[str, tuple[date, date]] = {
    "2025.1": (date(2025, 3, 24), date(2025, 7, 26)),
    "2025.2": (date(2025, 8, 18), date(2025, 12, 15)),
    "2026.1": (date(2026, 3, 16), date(2026, 7, 18)),
    "2026.2": (date(2026, 8, 10), date(2026, 12, 14)),
    "2027.1": (date(2027, 3, 15), date(2027, 7, 16)),
    "2027.2": (date(2027, 8, 9), date(2027, 12, 16)),
}


# ─── Modelo de dados ──────────────────────────────────────────────────────────

@dataclass
class SemesterStatus:
    semestre: str
    status: str          # "vigente" | "proximo" | "encerrado" | "futuro"
    inicio: Optional[date]
    fim: Optional[date]
    days_remaining: Optional[int]

    @property
    def emoji(self) -> str:
        return {
            "vigente": "🟢",
            "proximo": "📅",
            "encerrado": "🔴",
            "futuro": "🔵",
        }.get(self.status, "❓")

    @property
    def label(self) -> str:
        labels = {
            "vigente": "SEMESTRE VIGENTE",
            "proximo": "PRÓXIMO SEMESTRE",
            "encerrado": "SEMESTRE ENCERRADO",
            "futuro": "SEMESTRE FUTURO",
        }
        return labels.get(self.status, self.status.upper())


def classify_semester(semestre: str, today: date = None) -> SemesterStatus:
    """
    Classifica um semestre com base na data de hoje:
      - vigente:   hoje está dentro do período de aulas
      - proximo:   período ainda não começou
      - encerrado: período já terminou
      - futuro:    sem dados de período (semestre muito no futuro)
    """
    if today is None:
        today = date.today()

    period = KNOWN_PERIODS.get(semestre)
    if not period:
        return SemesterStatus(semestre, "futuro", None, None, None)

    inicio, fim = period

    if today < inicio:
        return SemesterStatus(semestre, "proximo", inicio, fim, (inicio - today).days)
    elif today <= fim:
        remaining = (fim - today).days
        return SemesterStatus(semestre, "vigente", inicio, fim, remaining)
    else:
        return SemesterStatus(semestre, "encerrado", inicio, fim, 0)


def get_relevant_semesters(today: date = None) -> list[str]:
    """
    Retorna os semestres relevantes para manter na base:
    - Semestre vigente (ou o mais recente se estiver entre semestres)
    - Próximo semestre (se já publicado)
    """
    if today is None:
        today = date.today()

    semesters = sorted(KNOWN_PERIODS.keys())
    relevant = []

    for sem in semesters:
        status = classify_semester(sem, today)
        if status.status in ("vigente", "proximo"):
            relevant.append(sem)
        elif status.status == "encerrado":
            # Manter por 30 dias após o encerramento (útil para revisão de menção)
            days_after = (today - status.fim).days
            if days_after <= 30:
                relevant.append(sem)

    # Garantir pelo menos o semestre vigente (ou o último encerrado)
    if not relevant:
        last = max(
            (s for s in semesters if classify_semester(s, today).status == "encerrado"),
            default=semesters[-1] if semesters else None,
        )
        if last:
            relevant.append(last)

    return relevant


# ─── Scraping ────────────────────────────────────────────────────────────────

def fetch_calendar_links() -> list[dict]:
    """Scraping do site SAA → lista de {semestre, data_pub, url, tipo}."""
    print(f"🌐 Acessando {SAA_URL} ...")
    resp = requests.get(SAA_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[dict] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        text: str = a.get_text(strip=True)

        if not href.endswith(".pdf"):
            continue

        is_ativ = "Atividade" in text or "Atividades" in text
        if not is_ativ:
            continue

        sem = re.search(r"20\d\d\.[124]", text)
        if not sem:
            continue

        data = re.search(r"\((\d{2}/\d{2}/\d{4})\)", text)
        url = href if href.startswith("http") else "https://saa.unb.br" + href

        results.append({
            "semestre": sem.group(0),
            "data_pub": data.group(1) if data else "?",
            "url": url,
        })

    return results


# ─── Controle de versões locais ───────────────────────────────────────────────

def local_calendar_path(semestre: str) -> Path:
    slug = f"calendario-{semestre.replace('.', '-')}"
    return KB_DIR / f"{slug}.md"


def get_local_semesters() -> list[str]:
    """Retorna os semestres que já existem localmente como arquivos .md."""
    pattern = re.compile(r"calendario-(\d{4}-\d)\.md")
    semesters = []
    for f in KB_DIR.glob("calendario-*.md"):
        m = pattern.match(f.name)
        if m:
            semesters.append(m.group(1).replace("-", "."))
    return sorted(semesters)


# ─── Índice principal (calendario.md) ────────────────────────────────────────

def rebuild_index(today: date = None) -> None:
    """
    Regera o arquivo `calendario.md` como índice dos semestres disponíveis,
    com indicação clara de qual está vigente.
    """
    if today is None:
        today = date.today()

    local = get_local_semesters()
    lines = [
        "# Calendários Acadêmicos UnB",
        "",
        f"> Atualizado em: {today.strftime('%d/%m/%Y')}  ",
        f"> Fonte: [{SAA_URL}]({SAA_URL})",
        "",
        "---",
        "",
        "## Situação dos Semestres",
        "",
    ]

    all_semesters = sorted(set(list(KNOWN_PERIODS.keys()) + local), reverse=True)

    for sem in all_semesters:
        status = classify_semester(sem, today)
        file_exists = local_calendar_path(sem).exists()
        file_ref = f"calendario-{sem.replace('.', '-')}.md"

        if status.status == "vigente":
            extra = f" — {status.days_remaining} dias restantes"
        elif status.status == "proximo":
            extra = f" — começa em {status.inicio.strftime('%d/%m/%Y')} ({status.days_remaining} dias)"
        elif status.status == "encerrado":
            extra = f" — encerrado em {status.fim.strftime('%d/%m/%Y')}"
        else:
            extra = ""

        if file_exists:
            lines.append(f"- {status.emoji} **[{sem} — {status.label}]({file_ref})**{extra}")
        else:
            lines.append(f"- {status.emoji} **{sem} — {status.label}**{extra} _(não baixado)_")

    lines += [
        "",
        "---",
        "",
        "## Como usar",
        "",
        "- Para datas do **semestre em andamento**, consulte o arquivo marcado com 🟢",
        "- Para planejar o **próximo semestre**, consulte o marcado com 📅",
        "- Os arquivos individuais (`calendario-AAAA-S.md`) contêm todos os prazos detalhados",
        "",
        "## Atualização automática",
        "",
        "```bash",
        "# Verificar e atualizar calendários",
        "python scripts/update_calendario.py",
        "",
        "# Cron mensal configurado em:",
        "bash scripts/setup_cron.sh --status",
        "```",
    ]

    index_path = KB_DIR / "calendario.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"📋 Índice atualizado: {index_path.name}")


# ─── Geração do arquivo de prazos consolidados ───────────────────────────────

# Padrões de atividades a extrair dos calendários
_PRAZOS_PATTERNS = [
    (r"Solicitação de Matrícula de \d", "Matrícula (solicitação)"),
    (r"Solicitação de Rematrícula de \d", "Rematrícula (solicitação)"),
    (r"Solicitação de Matrícula Extraordinária", "Matrícula Extraordinária"),
    (r"TRANCAMENTO PARCIAL DE MATRÍCULA AUTOMÁTICO", "Trancamento Parcial de Matrícula (automático)"),
    (r"TRANCAMENTO GERAL DE MATRÍCULA AUTOMÁTICO|TRANCAMENTO GERAL DE —", "Trancamento Geral de Matrícula (automático)"),
    (r"INÍCIO DAS AULAS", "Início das aulas"),
    (r"FIM DAS AULAS|TÉRMINO DAS AULAS|ENCERRAMENTO DAS AULAS", "Fim das aulas"),
    (r"MENÇÃO FINAL", "Lançamento de menção final (docente)"),
]


def _extract_date_from_line(line: str) -> str:
    """Extrai a data/período de uma linha do calendário."""
    # Formato: — Estudante — 14/03 a 18/05/2026 —  ou  — Até 09/10/2026 —
    m = re.search(
        r"—\s*(?:Estudante\s*—\s*|Docente\s*—\s*|DEG/SAA\s*—\s*)?([^—]+?\d{4}[^—]*?)(?:\s*—|$)",
        line,
    )
    if m:
        return m.group(1).strip()
    # Fallback: pega o primeiro trecho com data
    m2 = re.search(r"(\d{2}/\d{2}(?:/\d{4})?(?:\s*a\s*\d{2}/\d{2}(?:/\d{4})?)?)", line)
    return m2.group(1) if m2 else "—"


def generate_prazos_doc(today: date = None) -> None:
    """
    Gera prazos-semestres.md com TODAS as atividades de cada semestre,
    extraídas diretamente dos arquivos calendario-AAAA-S.md.
    """
    if today is None:
        today = date.today()

    local_sems = get_local_semesters()
    if not local_sems:
        return

    lines = [
        "# Prazos dos Semestres Letivos — FCTE/UnB",
        "",
        f"> Atualizado automaticamente em {today.strftime('%d/%m/%Y')}",
        "",
    ]

    for sem in sorted(local_sems, reverse=True)[:4]:
        status = classify_semester(sem, today)
        cal_path = local_calendar_path(sem)
        if not cal_path.exists():
            continue

        label_extra = f" ({status.label})" if status.status in ("vigente", "proximo") else ""
        lines += [
            f"## Semestre {sem}{label_extra}",
            "",
        ]

        text = cal_path.read_text(encoding="utf-8")
        atividades = []
        secao_atual = ""

        # Padrões de linhas a ignorar (ruído do PDF)
        _ruido = re.compile(
            r"^(C\s+A\s+L\s+E|D\s+—\s+S|^\s*[-\d —/]+$|MARÇO|ABRIL|MAIO|JUNHO"
            r"|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO"
            r"|^\s*\d{2}/\d{2}\s*[-a]\s*\d{2}/\d{2})",
            re.IGNORECASE,
        )

        for raw_line in text.splitlines():
            line = raw_line.strip()

            # Captura seções (## Título da seção)
            if line.startswith("## "):
                secao_atual = line.lstrip("# ").strip()
                secao_atual = re.sub(r"^\[\d{4}\.\d\]\s*", "", secao_atual)
                continue

            # Captura linhas de atividade (começam com "- ")
            if line.startswith("- "):
                entrada = re.sub(r"^\- \[\d{4}\.\d\]\s*", "", line)
                # Filtra ruído: grade do calendário, linhas só com datas/números
                conteudo = entrada.lstrip("- ").strip()
                if not conteudo:
                    continue
                if _ruido.search(conteudo):
                    continue
                # Filtra linhas que são só dígitos, traços e barras (grade visual)
                if re.fullmatch(r"[\d\s—/\-–]+", conteudo):
                    continue
                if entrada:
                    atividades.append((secao_atual, entrada))

        if atividades:
            secao_anterior = None
            for secao, entrada in atividades:
                if secao and secao != secao_anterior:
                    lines += ["", f"### {secao}", ""]
                    secao_anterior = secao
                lines.append(f"- {entrada}")
        else:
            lines.append("- _(sem dados extraídos)_")

        lines.append("")

    lines += [
        "> Fonte: Calendário Acadêmico SAA/UnB",
    ]

    out = KB_DIR / "prazos-semestres.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"📋 prazos-semestres.md atualizado com {len(local_sems)} semestre(s).")


# ─── Ingestão via ingest_pdf.py ───────────────────────────────────────────────

def run_ingest_pdf(url: str, semestre: str, no_ingest: bool) -> int:
    """Delega download + parse + .md para ingest_pdf.py."""
    status = classify_semester(semestre)
    slug = f"calendario-{semestre.replace('.', '-')}"

    # Título inclui o status do semestre
    title = f"Calendário Acadêmico {semestre} — {status.label}"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "ingest_pdf.py"),
        "--url", url,
        "--name", slug,
        "--title", title,
        "--kb-path", str(KB_DIR),
        "--force",
    ]
    if no_ingest:
        cmd.append("--no-ingest")

    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def run_ingest() -> bool:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ingest.py"), "--force"],
        cwd=str(ROOT),
    )
    return result.returncode == 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FCTEBot — Atualização automática dos calendários acadêmicos UnB"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Só verifica disponibilidade, sem alterar nada")
    parser.add_argument("--force", action="store_true",
                        help="Força download mesmo que o arquivo já exista localmente")
    parser.add_argument("--no-ingest", action="store_true",
                        help="Atualiza os .md mas não re-indexa")
    args = parser.parse_args()

    today = date.today()
    print("=" * 60)
    print("FCTEBot — Atualização dos Calendários Acadêmicos")
    print(f"Data atual: {today.strftime('%d/%m/%Y')}")
    print("=" * 60)

    # 1. Classificar semestres relevantes com base na data de hoje
    relevant = get_relevant_semesters(today)
    print(f"\n📌 Semestres relevantes hoje:")
    for sem in relevant:
        s = classify_semester(sem, today)
        print(f"   {s.emoji} {sem} — {s.label}", end="")
        if s.days_remaining is not None and s.status == "vigente":
            print(f" ({s.days_remaining} dias restantes)", end="")
        elif s.status == "proximo":
            print(f" (começa em {s.days_remaining} dias)", end="")
        print()

    # 2. Buscar links disponíveis no SAA
    try:
        available = fetch_calendar_links()
    except requests.RequestException as e:
        print(f"\n❌ Erro ao acessar o SAA: {e}")
        print("   Trabalhando com os arquivos locais existentes.")
        available = []

    print(f"\n🌐 Disponíveis no SAA ({len(available)} calendários por atividade):")
    for c in available:
        status = classify_semester(c["semestre"], today)
        local_exists = local_calendar_path(c["semestre"]).exists()
        marker = "✅" if local_exists else "⬇️ "
        print(f"   {marker} {c['semestre']} — pub. {c['data_pub']} {status.emoji}")

    # 3. Determinar quais precisam de download
    to_download = []
    for c in available:
        if c["semestre"] not in relevant:
            continue  # Não é relevante agora (ex: semestre encerrado há muito)
        local = local_calendar_path(c["semestre"])
        if not local.exists() or args.force:
            to_download.append(c)

    if not to_download:
        print("\n✅ Todos os calendários relevantes já estão atualizados.")
        rebuild_index(today)
        generate_prazos_doc(today)
        return

    print(f"\n🆕 Para baixar/atualizar: {[c['semestre'] for c in to_download]}")

    if args.dry_run:
        print("   [--dry-run] Nenhuma alteração foi feita.")
        return

    # 4. Baixar e ingerir cada semestre necessário
    errors = []
    for c in to_download:
        print(f"\n{'─'*50}")
        print(f"📥 Processando: {c['semestre']}")
        rc = run_ingest_pdf(c["url"], c["semestre"], no_ingest=True)  # ingest depois
        if rc != 0:
            errors.append(c["semestre"])

    # 5. Regenerar o índice e prazos consolidados
    rebuild_index(today)
    generate_prazos_doc(today)

    # 6. Re-ingestão única (mais eficiente do que re-indexar para cada PDF)
    if not args.no_ingest and not errors:
        ok = run_ingest()
        if ok:
            print("\n🎉 Calendários atualizados e base re-indexada!")
        else:
            print("\n⚠️  Re-ingestão falhou. Execute manualmente:")
            print("   python scripts/ingest.py --force")
    elif errors:
        print(f"\n⚠️  Falhas: {errors}")
        print("   Tente novamente ou baixe os PDFs manualmente.")
    else:
        print("\n📌 Re-ingestão pulada (--no-ingest).")
        print("   Quando pronto: python scripts/ingest.py --force")

    # 7. Resumo final
    print("\n" + "=" * 60)
    print("Resumo da situação atual dos calendários:")
    for sem in sorted(set(list(KNOWN_PERIODS.keys()) + get_local_semesters()), reverse=True)[:4]:
        s = classify_semester(sem, today)
        local = local_calendar_path(sem)
        exists = "✅ na base" if local.exists() else "❌ não baixado"
        print(f"  {s.emoji} {sem} — {s.label} — {exists}")


if __name__ == "__main__":
    main()
