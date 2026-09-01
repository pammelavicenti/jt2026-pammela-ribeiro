"""
generate_readme.py — Gera o README.md principal a partir dos resultados versionados.

Importa automaticamente a matriz de decisão (outputs/analysis/final/decision_matrix.csv)
para preencher a tabela de 'Principais números', evitando digitação manual.

NÃO cria relatório técnico; apenas o README do repositório.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DM = ROOT / "outputs" / "analysis" / "final" / "decision_matrix.csv"
README = ROOT / "README.md"


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").strip().lower()


def pct(x, nd=1):
    return f"{100*x:.{nd}f}%"


def brl(x):
    return f"R$ {x:,.0f}"


def main() -> None:
    dm = pd.read_csv(DM)
    expected = {
        "morretes | 2. apartamento (2q)",
        "meia praia | 1. apartamento compacto (0-1q)",
        "centro | 2. apartamento (2q)",
    }
    have = set(dm["segmento"].map(norm))
    exp = {norm(s) for s in expected}
    if not exp <= have:
        raise SystemExit(f"decision_matrix.csv não contém os 3 segmentos esperados: {exp - have}")

    # ordem: principal (morretes), alternativa (centro), observado (meia pr)
    order = ["morretes | 2. apartamento (2q)", "centro | 2. apartamento (2q)",
             "meia praia | 1. apartamento compacto (0-1q)"]
    # posição na decisão
    role = {
        "morretes | 2. apartamento (2q)": "Recomendação principal",
        "centro | 2. apartamento (2q)": "Alternativa",
        "meia praia | 1. apartamento compacto (0-1q)": "Observado (N<20 na F3: descritivo)",
    }

    rows = []
    for s in order:
        r = dm[dm["segmento"] == s].iloc[0]
        seg_label = s.replace(" | ", " — ")
        rows.append({
            "seg": seg_label,
            "n_air": int(r["n_airbnb_precificados_F2"]),
            "n_air_f3": int(r["n_airbnb_principal_F3"]),
            "n_viva": int(r["n_vivareal_elegiveis_F2"]),
            "rend60": pct(r["rendimento_60"]),
            "ic": f"{pct(r['ic_rend60_025'],2)}–{pct(r['ic_rend60_975'],2)}",
            "payback": f"{r['payback_60']:.1f} anos",
            "role": role[s],
        })

    md = []
    md.append("[LINK PENDENTE — será inserido separadamente antes da entrega]\n")
    md.append("")
    md.append("# Jovens Talentos 2026 — Recomendação de investimento imobiliário em Itapema\n")
    md.append("- **Autora:** Pâmmela Vicenti Ribeiro")
    md.append("- **Repositório:** https://github.com/pammelavicenti/jt2026-pammela-ribeiro\n")
    # ---------------------------------------------------------------
    md.append("## 1. Resumo executivo\n")
    md.append(
        "Este repositório consolida a análise do mercado imobiliário de Itapema (SC), baseada no snapshot de "
        "janeiro de 2025 (Airbnb + VivaReal), com o objetivo de apoiar a decisão de investimento em short stay. "
        "A recomendação principal é **Morretes — apartamento de 2 quartos**, com **rendimento bruto anualizado "
        "estimado de 13,9%** no cenário hipotético de ocupação de 60%, **IC bootstrap de 95%: 12,9% a 15,1%** e "
        "**payback bruto estimado de 7,2 anos**. A alternativa é **Centro — apartamento de 2 quartos**. A "
        "confiança é **moderada**: a vantagem do segmento principal sobre os demais é pequena e **não foi "
        "demonstrada como estatisticamente conclusiva** (os intervalos de bootstrap se sobrepõem). A decisão é "
        "**condicionada à validação de ocupação, despesas operacionais e preço efetivamente negociado**.\n"
    )
    md.append("\n> Terminologia: usamos **diária anunciada ajustada**, **receita bruta anualizada estimada**, "
              "**rendimento bruto anualizado estimado** e **payback bruto estimado**. Não há receita realizada, "
              "lucro, retorno líquido, ocupação observada ou garantia.\n")
    # ---------------------------------------------------------------
    md.append("\n## 2. Pergunta de negócio\n")
    md.append(
        "Qual o melhor perfil e localização para a Seazone investir em imóveis de short stay em Itapema, "
        "considerando a diária anunciada, o preço de aquisição, o rendimento bruto estimado, a incerteza e a "
        "estabilidade nas sensibilidades? O desafio também pede uma posição sobre a tese interna de que "
        "apartamentos compactos (0–1 quarto) no Centro seriam a aposta mais eficiente.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 3. Recomendação principal\n")
    md.append(
        "**Morretes — apartamento de 2 quartos.** Foi o segmento mais defensável pelos critérios adotados: "
        "rendimento bruto anualizado estimado de 13,9% no cenário central (ocupação 60%), IC bootstrap de 95% "
        "entre 12,9% e 15,1%, payback bruto estimado de 7,2 anos, amostra VivaReal ampla (1.019) e liderança em "
        "quatro dos cinco cenários de sensibilidade. Risco principal: a vantagem é pequena e não demonstrada como "
        "estatisticamente conclusiva.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 4. Alternativa\n")
    md.append(
        "**Centro — apartamento de 2 quartos.** Segundo mais defensável. Seria preferível nos cenários "
        "conjuntos em que o preço de aquisição assumido é o P25 de cada segmento (rendimento do Centro de 17,8% "
        "contra 16,2% de Morretes) e no cenário cruzado Centro@P25 versus Morretes@mediana (detalhes em "
        "`outputs/analysis/final/condition_change_scenarios.csv`).\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 5. Principais números\n")
    md.append("Fonte: `outputs/analysis/final/decision_matrix.csv` (importada automaticamente).\n")
    md.append("| Segmento | N Airbnb (F2) | N Airbnb principal (F3) | N VivaReal elegível | Rend. bruto 60% | IC bootstrap 95% | Payback bruto | Posição na decisão |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        md.append(f"| {r['seg']} | {r['n_air']} | {r['n_air_f3']} | {r['n_viva']} | {r['rend60']} | {r['ic']} | {r['payback']} | {r['role']} |")
    md.append("\nVídeo de apresentação pendente na primeira linha do README. Outros cenários (50%, 75%, preço P25/P75, outliers) em "
              "`outputs/analysis/final`.")
    # ---------------------------------------------------------------
    md.append("\n## 6. Como interpretar as métricas\n")
    md.append(
        "- **Diária anunciada ajustada por data e mês:** média ponderada igual dos quatro meses (jan–abr/2025), "
        "calculada apenas quando os 4 meses estão presentes. Não é receita realizada.\n"
        "- **Receita bruta anualizada estimada:** diária ajustada × 365 × cenário de ocupação (50/60/75% — "
        "hipóteses, não ocupação observada).\n"
        "- **Rendimento bruto anualizado estimado:** receita bruta ÷ preço anunciado de aquisição (mediana "
        "VivaReal). É bruto: exclui condomínio, IPTU, manutenção, gestão e impostos.\n"
        "- **Payback bruto estimado:** inverso do rendimento bruto (anos).\n"
        "- **IC bootstrap de 95%:** reamostragem por anúncio/owner, seed 42, 1.000 réplicas. Não é intervalo causal.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 7. Bases utilizadas\n")
    md.append(
        "Snapshot estático de janeiro/2025 (Itapema/SC):\n"
        "- `data/Details_Itapema.csv` — anúncios Airbnb (4.441);\n"
        "- `data/Hosts_ids_Itapema.csv` — anfitriões;\n"
        "- `data/Mesh_Ids_Data_Itapema.csv` — localização/bairro;\n"
        "- `data/Price_AV_Itapema.csv` — preços anunciados por anúncio e data (3 ondas jan/2025);\n"
        "- `data/VivaReal_Itapema.csv` — anúncios de venda (8.293 após dedupe).\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 8. Metodologia resumida\n")
    md.append(
        "1. **Preparação** (`scripts/build_base.py`): dedupe e limpeza reproduzíveis; 33 verificações;\n"
        "2. **Fase 1** (`analyze_profile_location.py`): diária anunciada ajustada por perfil e bairro; teste da "
        "tese dos compactos no Centro (não sustentada);\n"
        "3. **Fase 2** (`analyze_investment_efficiency.py`): preço de aquisição (VivaReal) e rendimento/payback "
        "brutos por segmento em cenários de ocupação;\n"
        "4. **Fase 3** (`analyze_listing_characteristics.py`): características associadas à diária (associação ≠ "
        "causalidade);\n"
        "5. **Fase 4** (`synthesize_recommendation.py`): matriz de decisão e recomendação integrada.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 9. Estrutura do repositório\n")
    md.append(
        "```\n"
        "data/                      dados brutos (snapshot jan/2025)\n"
        "scripts/                   pipeline (build_base e Fases 1–4)\n"
        "docs/                      metodologia de dados e rastreabilidade\n"
        "outputs/processed/         bases derivadas (reproduzíveis; não versionadas)\n"
        "outputs/quality/           auditorias da preparação\n"
        "outputs/analysis/          results fases 1–4 + figuras\n"
        "ai-log/                    conversas com a IA (exportadas em texto)\n"
        "relatorio.md               relatório técnico consolidado\n"
        "README.md                  este documento\n"
        "requirements.txt           dependências\n"
        "```\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 10. Como reproduzir\n")
    md.append("Windows PowerShell:\n")
    md.append("```powershell")
    md.append("python -m venv .venv")
    md.append(".venv\\Scripts\\Activate.ps1")
    md.append("python -m pip install --upgrade pip")
    md.append("pip install -r requirements.txt")
    md.append("")
    md.append("python scripts\\build_base.py")
    md.append("python scripts\\analyze_profile_location.py")
    md.append("python scripts\\analyze_investment_efficiency.py")
    md.append("python scripts\\analyze_listing_characteristics.py")
    md.append("python scripts\\synthesize_recommendation.py")
    md.append("```")
    md.append("Python 3.13.5 · pandas 3.0.5 · numpy 2.4.4 (ver `requirements.txt`). Cada script aborta sem "
              "gravar se alguma verificação estrutural falhar; `outputs/processed/*.csv` são regenerados "
              "automaticamente (não versionados).")
    # ---------------------------------------------------------------
    md.append("\n## 11. Resultados por fase\n")
    md.append("- **Fase 1 — Perfil e localização:** maiores diárias ajustadas em aptos 3q+ (R$ 793) e Meia "
              "Praia (R$ 674); a tese dos compactos no Centro **não foi sustentada** (vs aptos 2q+ no Centro, IC da "
              "diferença todo negativo).\n")
    md.append("- **Fase 2 — Preço e eficiência econômica:** ranking central a 60% liderado por Morretes·2q "
              "(13,9%), Centro·2q (13,5%) e Meia Praia·compacto (13,4%).\n")
    md.append("- **Fase 3 — Características:** nº de quartos com associação positiva à diária (por 1 desvio-"
              "padrão), mas sensível à presença de outliers (42,6% → 17,0%); nenhuma comodidade isolada "
              "atendeu aos critérios de estabilidade; sem evidência causal.\n")
    md.append("- **Fase 4 — Síntese:** matriz de decisão e esta recomendação (veja `outputs/analysis/final/"
              "final_recommendation.md`).\n")
    # ---------------------------------------------------------------
    md.append("\n## 12. Limitações\n")
    md.append(
        "- Diária anunciada ≠ receita; sem reservas/ocupação observadas (ocupação é cenário).\n"
        "- Rendimento e payback **brutos**: sem condomínio, IPTU, manutenção, gestão, impostos ou financiamento.\n"
        "- Preço de aquisição é o **anunciado** (VivaReal), não o negociado.\n"
        "- Comparação agregada bairro×perfil sem chave comum entre Airbnb e VivaReal.\n"
        "- Sazonalidade observável apenas jan–abr/2025; anualização é extrapolação.\n"
        "- Concentração por proprietário representa risco de representatividade.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 13. Uso de inteligência artificial\n")
    md.append(
        "Todo o pipeline (preparação, análises 1–4 e esta documentação) foi construído de forma **iterativa com "
        "IA (OpenCode)**, com revisões metodológicas explícitas a cada fase: deduplicação, elegibilidade de "
        "preços, bootstrap por clusters de owner preservando multiplicidade, validação cruzada por owner, gate "
        "de saída (gravar apenas após todas as verificações) e revisão crítica de resultados. As conversas "
        "completas estão exportadas em texto em `ai-log/`.\n"
    )
    # ---------------------------------------------------------------
    md.append("\n## 14. Link para o relatório técnico\n")
    md.append("- Relatório técnico consolidado: [relatorio.md](relatorio.md)")
    md.append("- Rastreabilidade dos resultados: [docs/rastreabilidade.md](docs/rastreabilidade.md)")
    md.append("- Metodologia de dados: [docs/metodologia_dados.md](docs/metodologia_dados.md)")
    md.append("- Recomendação final: [outputs/analysis/final/final_recommendation.md]"
              "(outputs/analysis/final/final_recommendation.md)")
    md.append("- Matriz de decisão: [outputs/analysis/final/decision_matrix.csv]"
              "(outputs/analysis/final/decision_matrix.csv)")
    md.append("- Registro completo do uso de IA: [ai-log/](ai-log/)")
    md.append("- Figuras: [outputs/analysis/final/figures/](outputs/analysis/final/figures/)")
    md.append("\n### Figuras (Fase 4)\n")
    md.append("![Diária anunciada e preço de aquisição](outputs/analysis/final/figures/01_daily_rate_and_purchase_price.png)")
    md.append("![Rendimento bruto por cenário de ocupação](outputs/analysis/final/figures/02_gross_yield_scenarios.png)")
    md.append("![Payback por preço de aquisição](outputs/analysis/final/figures/03_payback_sensitivity.png)")
    md.append("![Quadro-resumo da decisão](outputs/analysis/final/figures/04_decision_summary.png)")
    # ---------------------------------------------------------------
    md.append("\n## 15. Pendências para a entrega\n")
    md.append("- [ ] Inserir o **link do vídeo** (seção 1), compartilhado com 'qualquer pessoa com o link'.")
    md.append("- [ ] Revisão final em aba anônima do repositório público.")
    md.append("- [ ] Enviar o formulário de entrega com os links do repositório e do vídeo.")

    text = "\n".join(md)
    # remover múltiplas linhas em branco consecutivas
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    with README.open("w", encoding="utf-8", newline="") as f:
        f.write(text + "\n")
    print("README.md gerado.")


if __name__ == "__main__":
    main()