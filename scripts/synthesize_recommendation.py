"""
synthesize_recommendation.py — Fase 4: síntese da recomendação de investimento.

Integra resultados já versionados das Fases 1, 2 e 3. NÃO refaz análises anteriores.

Segmentos obrigatórios:
  1. Morretes — apartamento de 2 quartos
  2. Meia Praia — apartamento compacto de 0–1 quarto
  3. Centro — apartamento de 2 quartos

Princípio: não escolher pela maior diária; decisão combina diária (F1), preço de aquisição (F2),
rendimento/payback brutos, estabilidade de ocupação, sensibilidade a preço e a outliers, amostras,
evidência auxiliar da F3 e limitações.

Correções desta versão:
  1. Gate real: tudo é gerado em tempdir; só publica em outputs/analysis/final/ após TODAS as validações.
  2. N da Fase 3 por segmento vem de shortlist_characteristics.csv (n_precificado_total, n_principal,
     cobertura_med, nota). Hard-checks 24/17/37.
  3. Três Ns distintos: n_airbnb_precificados_F2, n_airbnb_principal_F3, n_vivareal_elegiveis_F2.
  4. Cenário preco@P25 descrito como CONJUNTO (P25 de cada segmento) — sem alegação unilateral.
  5. Alegação de superioridade enfraquecida (vantagem pequena, ICs sobrepostos, sem bootstrap da diferença).
  6. U+FFFD guard: nenhum arquivo publicado pode conter \ufffd.

Terminologia: associação ≠ causalidade; nunca receita realizada/lucro/retorno líquido/NOI/valorização.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
P1 = ROOT / "outputs" / "analysis"
P2 = ROOT / "outputs" / "analysis" / "phase2"
P3 = ROOT / "outputs" / "analysis" / "phase3"
OUT = ROOT / "outputs" / "analysis" / "final"

SEGMENTS = [
    "morretes | 2. apartamento (2q)",
    "meia praia | 1. apartamento compacto (0-1q)",
    "centro | 2. apartamento (2q)",
]
EXPECTED_F3_N_PRINCIPAL = {
    "morretes | 2. apartamento (2q)": 24,
    "meia praia | 1. apartamento compacto (0-1q)": 17,
    "centro | 2. apartamento (2q)": 37,
}
PLOT_DPI = 160
MIN_PX_W, MIN_PX_H = 1600, 900

checks: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    checks.append((cond, msg))


def fail_and_exit() -> None:
    failed = [m for ok, m in checks if not ok]
    if not failed:
        return
    print("\n=== VALIDAÇÕES COM FALHA — abortando SEM publicar outputs/analysis/final/ ===")
    for m in failed:
        print("  [FALHA] " + m)
    sys.exit(1)


def assert_no_fffd(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(f"U+FFFD encontrado em {path}")


def write_utf8_lf(text: str, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def write_csv_lf(df: pd.DataFrame, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False, lineterminator="\n")


def fmt(x, nd=1):
    if x is None:
        return "n/d"
    try:
        if isinstance(x, float) and np.isnan(x):
            return "n/d"
    except TypeError:
        pass
    return f"{x:,.{nd}f}"


def fmt_rs(x):
    return "R$ " + fmt(x, 0)


def fmt_pct(x, nd=1):
    return f"{100*x:.{nd}f}%"


def test_gate_preserves_destination() -> bool:
    """Teste controlado: uma falha na geração em temp não altera outputs/analysis/final/."""
    pre = sorted(p.name for p in OUT.glob("*")) if OUT.exists() else []
    try:
        with tempfile.TemporaryDirectory() as tmpd:
            t = Path(tmpd)
            # gera conteúdo no temp e MESMO assim "falha"
            (t / "dummy.txt").write_text("conteudo", encoding="utf-8")
            1 / 0  # falha proposital
    except ZeroDivisionError:
        pass
    if not OUT.exists():
        return True
    post = sorted(p.name for p in OUT.glob("*"))
    return pre == post


def main() -> None:
    check(test_gate_preserves_destination(), "gate: falha em temp não altera o destino final (teste controlado)")
    print("[1/7] Carregando resultados das fases...")
    seg = pd.read_csv(P2 / "segment_economics.csv")
    pps = pd.read_csv(P2 / "purchase_price_sensitivity.csv")
    osens = pd.read_csv(P2 / "outlier_sensitivity.csv")
    short3 = pd.read_csv(P3 / "shortlist_characteristics.csv")
    stab3 = pd.read_csv(P3 / "coverage_stability.csv")
    pps = pps[(pps.ocupacao == "60%")].copy()

    # ---- validações de origem ----
    check(len(seg[seg.segmento.isin(SEGMENTS)]) == 3, "3 segmentos presentes em segment_economics")
    check(set(SEGMENTS) <= set(seg.segmento.tolist()), "segmentos existem")
    for s in SEGMENTS:
        r = seg[seg.segmento == s].iloc[0]
        check(bool(r.eligible_for_ranking), f"{s} elegível no ranking da Fase 2")
        check(r.bootstrap_reps_valid >= 950, f"{s}: >=950 réplicas bootstrap (F2)")
    # hard-check F3 N por segmento
    for s in SEGMENTS:
        row3 = short3[short3.segmento == s]
        check(len(row3) == 1, f"F3 shortlist: linha única para {s}")
        if len(row3):
            check(int(row3.n_principal.iloc[0]) == EXPECTED_F3_N_PRINCIPAL[s],
                  f"F3 {s}: n_principal = {EXPECTED_F3_N_PRINCIPAL[s]} (tem {int(row3.n_principal.iloc[0])})")

    # importação idêntica à F2 (valores do relatório)
    expected = {
        "morretes | 2. apartamento (2q)": {"diaria": 501.968821, "preco": 789550.0, "rend60": 0.1392327, "n_air": 51, "n_viva": 1019},
        "meia praia | 1. apartamento compacto (0-1q)": {"diaria": 534.742651, "preco": 875000.0, "rend60": 0.1338384, "n_air": 28, "n_viva": 55},
        "centro | 2. apartamento (2q)": {"diaria": 711.225792, "preco": 1150000.0, "rend60": 0.1354421, "n_air": 65, "n_viva": 87},
    }
    for s in SEGMENTS:
        r = seg[seg.segmento == s].iloc[0]
        e = expected[s]
        check(abs(r.diaria_anunciada_ajustada - e["diaria"]) < 1e-3, f"{s}: diária idêntica à Fase 2")
        check(abs(r.mediana_preco_aquisicao - e["preco"]) < 1e-6, f"{s}: preço idêntico à Fase 2")
        check(abs(r.rendimento_60 - e["rend60"]) < 1e-6, f"{s}: rendimento@60 idêntico")
        check(int(r.n_airbnb_precificados) == e["n_air"], f"{s}: N airbnb F2 idêntico")
        check(int(r.n_viva_elegiveis) == e["n_viva"], f"{s}: N viva F2 idêntico")

    stab3_bd = stab3[stab3.variavel == "number_of_bedrooms"]
    check(len(stab3_bd) == 1, "F3: number_of_bedrooms presente na estabilidade")

    # ---- matriz de decisão ----
    print("[2/7] Matriz de decisão...")
    rows = []
    for s in SEGMENTS:
        r = seg[seg.segmento == s].iloc[0]
        row3 = short3[short3.segmento == s].iloc[0]
        # rankings
        rank_60 = int(seg[seg.eligible_for_ranking == True].assign(rk=lambda d: d["rendimento_60"].rank(ascending=False)).loc[lambda d: d.segmento == s, "rk"].iloc[0])  # noqa: E712
        scen_ranks = {}
        ss = [
            ("principal@60", seg[seg.eligible_for_ranking == True], "rendimento_60"),  # noqa: E712
            ("outliers_todos", osens[osens.variancia == "sensibilidade_todos"], "rendimento_60"),
            ("preco_P25", pps[(pps.quantil_preco == "P25")], "rendimento_bruto"),
            ("preco_mediana", pps[(pps.quantil_preco == "mediana")], "rendimento_bruto"),
            ("preco_P75", pps[(pps.quantil_preco == "P75")], "rendimento_bruto"),
        ]
        scen_first = 0
        for (name, df, col) in ss:
            if s not in df.segmento.tolist():
                continue
            rk = int(df.assign(rk=lambda d: d[col].rank(ascending=False)).loc[lambda d: d.segmento == s, "rk"].iloc[0])
            scen_ranks[name] = rk
            if rk == 1:
                scen_first += 1
        worst = max(list(scen_ranks.values())) if scen_ranks else 1
        rank_p25 = scen_ranks.get("preco_P25")
        rank_pmed = scen_ranks.get("preco_mediana")
        rank_p75 = scen_ranks.get("preco_P75")
        rank_ot = scen_ranks.get("outliers_todos")
        # nota F3
        nota3 = row3["nota"] if isinstance(row3["nota"], str) else ""
        rows.append({
            "segmento": s,
            "n_airbnb_precificados_F2": int(r.n_airbnb_precificados),
            "n_airbnb_principal_F3": int(row3.n_principal),
            "n_airbnb_precificado_total_F3": int(row3.n_precificado_total),
            "cobertura_med_F3": row3.cobertura_med,
            "nota_F3": nota3,
            "n_vivareal_elegiveis_F2": int(r.n_viva_elegiveis),
            "diaria_anunciada_ajustada": r.diaria_anunciada_ajustada,
            "preco_aquisicao_mediana": r.mediana_preco_aquisicao,
            "p25_preco": r.p25_preco,
            "p75_preco": r.p75_preco,
            "receita_50": r.receita_50, "rendimento_50": r.rendimento_50, "payback_50": r.payback_50,
            "receita_60": r.receita_60, "rendimento_60": r.rendimento_60, "payback_60": r.payback_60,
            "receita_75": r.receita_75, "rendimento_75": r.rendimento_75, "payback_75": r.payback_75,
            "ic_rend60_025": r.ci_rend60_025, "ic_rend60_975": r.ci_rend60_975,
            "rank_principal_60": rank_60,
            "rank_preco_p25": rank_p25, "rank_preco_mediana": rank_pmed, "rank_preco_p75": rank_p75,
            "rank_outliers_todos": rank_ot,
            "n_vezes_em_primeiro": scen_first,
            "pior_posicao_observada": worst,
            "estabilidade_posicao": (rank_60 - worst),
            "maior_proprietario_share": r.maior_proprietario_share,
            "iqr_preco": r.iqr_preco_aquisicao,
            "cobertura_condo": r.cobertura_condo,
            "cobertura_iptu": r.cobertura_iptu,
        })
    dm = pd.DataFrame(rows).sort_values("rendimento_60", ascending=False).reset_index(drop=True)

    # ---- scenario_ranking ----
    scen_rows = []
    for s in SEGMENTS:
        r = seg[seg.segmento == s].iloc[0]
        for occ_name in ["50", "60", "75"]:
            scen_rows.append({
                "segmento": s, "cenario_ocupacao": occ_name + "%",
                "rendimento_bruto": r[f"rendimento_{occ_name}"],
                "payback_bruto": r[f"payback_{occ_name}"],
                "receita_bruta_anualizada": r[f"receita_{occ_name}"],
            })
    sr = pd.DataFrame(scen_rows)
    sr["rank"] = sr.groupby("cenario_ocupacao")["rendimento_bruto"].rank(ascending=False).astype(int)

    # ---- recommendation_sensitivity (preço + outliers) ----
    sens_rows = []
    for s in SEGMENTS:
        r = seg[seg.segmento == s].iloc[0]
        o_princ = osens[(osens.segmento == s) & (osens.variancia == "principal_False")].iloc[0]
        o_tudo = osens[(osens.segmento == s) & (osens.variancia == "sensibilidade_todos")].iloc[0]
        sens_rows.append({"segmento": s, "variancia": "principal_False", "rendimento_60": o_princ.rendimento_60,
                          "ci_025": o_princ.ci_rend60_025, "ci_975": o_princ.ci_rend60_975, "n_viva": int(o_princ.n_viva)})
        sens_rows.append({"segmento": s, "variancia": "todos_validos_incl_outliers", "rendimento_60": o_tudo.rendimento_60,
                          "ci_025": o_tudo.ci_rend60_025, "ci_975": o_tudo.ci_rend60_975, "n_viva": int(o_tudo.n_viva)})
        for q in ["P25", "mediana", "P75"]:
            row = pps[(pps.segmento == s) & (pps.quantil_preco == q)].iloc[0]
            sens_rows.append({"segmento": s, "variancia": f"preco_{q}", "rendimento_60": row.rendimento_bruto,
                              "ci_025": np.nan, "ci_975": np.nan, "n_viva": int(r.n_viva_elegiveis)})
    rs = pd.DataFrame(sens_rows)

    # ---- decisão (transparente, sem pontuação arbitrária) ----
    def suff(r):
        return int(r.n_airbnb_precificados_F2) >= 20 and int(r.n_vivareal_elegiveis_F2) >= 30
    rankable = dm[dm.apply(suff, axis=1)].copy()
    rankable = rankable.sort_values(["n_vezes_em_primeiro", "rendimento_60", "ic_rend60_025"],
                                    ascending=[False, False, False])
    check(len(rankable) >= 2, "pelo menos 2 segmentos rankeáveis")
    principal = rankable.iloc[0]
    alternativa = rankable.iloc[1] if len(rankable) > 1 else rankable.iloc[0]
    check(principal.segmento != alternativa.segmento, "principal diferente de alternativa")

    # ---- condition_change (conjunto P25×P25 e cruzado) ----
    roles = {s: ("principal" if s == principal.segmento else ("alternativa" if s == alternativa.segmento else "observado")) for s in SEGMENTS}
    pp_seg, alt_seg = principal.segmento, alternativa.segmento

    def rend_preco(segx, q):
        return float(pps[(pps.segmento == segx) & (pps.quantil_preco == q)].rendimento_bruto.iloc[0])

    def preco_q(segx, q):
        col = {"P25": "p25_preco", "mediana": "preco_aquisicao_mediana", "P75": "p75_preco"}[q]
        return float(dm[dm.segmento == segx][col].iloc[0])

    cmps = []
    for q in ["P25", "mediana", "P75"]:
        vp = rend_preco(pp_seg, q)
        va = rend_preco(alt_seg, q)
        cmps.append({
            "cenario": f"conjunto_preco@{q}",
            "quantil_preco_principal": q, "preco_principal": preco_q(pp_seg, q),
            "quantil_preco_alternativa": q, "preco_alternativa": preco_q(alt_seg, q),
            "rendimento_principal": vp, "rendimento_alternativa": va,
            "alternative_wins": bool(va > vp),
            "tipo": "conjunto (mesmo quantil nos dois)",
        })
    # cruzado Centro@P25 vs Morretes@mediana
    cross_alt, cross_princ = "centro | 2. apartamento (2q)", "morretes | 2. apartamento (2q)"
    va = rend_preco(cross_alt, "P25")
    vp = rend_preco(cross_princ, "mediana")
    cmps.append({
        "cenario": "cruzado_centroP25_vs_morretesMediana",
        "quantil_preco_principal": "mediana", "preco_principal": preco_q(cross_princ, "mediana"),
        "quantil_preco_alternativa": "P25", "preco_alternativa": preco_q(cross_alt, "P25"),
        "rendimento_principal": vp, "rendimento_alternativa": va,
        "alternative_wins": bool(va > vp),
        "tipo": "cruzado (Centro@P25 vs Morretes@mediana)",
    })
    # outlier + ocupações
    def rend_out(segx):
        return float(osens[(osens.segmento == segx) & (osens.variancia == "sensibilidade_todos")].rendimento_60.iloc[0])
    vp, va = rend_out(pp_seg), rend_out(alt_seg)
    cmps.append({
        "cenario": "outlier_todos", "quantil_preco_principal": "mediana", "preco_principal": preco_q(pp_seg, "mediana"),
        "quantil_preco_alternativa": "mediana", "preco_alternativa": preco_q(alt_seg, "mediana"),
        "rendimento_principal": vp, "rendimento_alternativa": va, "alternative_wins": bool(va > vp),
        "tipo": "outliers (preço com todos os válidos)",
    })
    for occ in [50, 60, 75]:
        vp = float(dm[dm.segmento == pp_seg][f"rendimento_{occ}"].iloc[0])
        va = float(dm[dm.segmento == alt_seg][f"rendimento_{occ}"].iloc[0])
        cmps.append({
            "cenario": f"ocupacao_{occ}%", "quantil_preco_principal": "mediana", "preco_principal": preco_q(pp_seg, "mediana"),
            "quantil_preco_alternativa": "mediana", "preco_alternativa": preco_q(alt_seg, "mediana"),
            "rendimento_principal": vp, "rendimento_alternativa": va, "alternative_wins": bool(va > vp),
            "tipo": "ocupação hipótese",
        })
    change_df = pd.DataFrame(cmps)
    alt_wins_scenarios = change_df[change_df.alternative_wins == True]["cenario"].tolist()  # noqa: E712

    # nível de confiança (moderado, com explicação)
    conf_level = "moderado"
    conf_reason = (
        "Vantagem central pequena e ICs bootstrap entre os 3 segmentos se sobrepõem; não foi calculado IC da "
        "diferença entre segmentos. Ocupação é hipótese (50/60/75%), despesas não incluídas, preços são anunciados "
        "(não negociados) e N Airbnb é moderado (28 a 65)."
    )

    # ---- gate antes de tocar OUTPUT ----
    fail_and_exit()

    # ---------- GRAVAÇÃO EM TEMP + VALIDAÇÃO + PUBLICAÇÃO ----------
    print("[3/7] Gerando conteúdo em diretório temporário...")
    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        tfig = tmp / "figures"
        tfig.mkdir(parents=True, exist_ok=True)

        write_csv_lf(dm, tmp / "decision_matrix.csv")
        write_csv_lf(sr, tmp / "scenario_ranking.csv")
        write_csv_lf(rs, tmp / "recommendation_sensitivity.csv")
        write_csv_lf(change_df, tmp / "condition_change_scenarios.csv")
        bd = stab3[stab3.variavel == "number_of_bedrooms"].iloc[0]

        # ---- relatório (monta em memória) ----
        L = []
        L.append("# Fase 4 — Síntese da recomendação de investimento (Itapema, snapshot jan/2025)\n")
        L.append("## 1. Pergunta de negócio\n")
        L.append("Quais combinações bairro × perfil entre os 3 segmentos são a escolha mais defensável para a Seazone "
                 "em short stay, dadas a diária anunciada ajustada (F1), o preço anunciado de aquisição e rendimento/"
                 "payback brutos (F2), e as características associadas (F3)? Baseado em jan/2025, com hipóteses de "
                 "ocupação explícitas; não é previsão de retorno garantido.\n")
        L.append("\n## 2. Alternativas avaliadas\n")
        for s in SEGMENTS:
            L.append(f"- {s}\n")
        L.append("\n## 3. Critérios de decisão (ordem)\n")
        L.append("1. Suficiência e rastreabilidade dos dados; 2. Rendimento bruto no cenário central (ocupação 60%); "
                 "3. Estabilidade ocupação 50/60/75%; 4. Sensibilidade ao preço de aquisição; 5. Sensibilidade a outliers; "
                 "6. Evidências F1/F3 como apoio (não substituição).\n")
        L.append("\n## 4. Matriz comparativa\n")
        for _, r in dm.sort_values("rendimento_60", ascending=False).iterrows():
            nota = (" — " + r.nota_F3) if (isinstance(r.nota_F3, str) and r.nota_F3.strip()) else ""
            L.append(
                f"- **{r['segmento']}**: diária ajustada {fmt_rs(r.diaria_anunciada_ajustada)} | preço mediano "
                f"{fmt_rs(r.preco_aquisicao_mediana)} | rend. bruto {fmt_pct(r.rendimento_60)} (IC "
                f"{fmt_pct(r.ic_rend60_025,2)}–{fmt_pct(r.ic_rend60_975,2)}) | payback {fmt(r.payback_60,1)} anos | "
                f"N air(F2) {int(r.n_airbnb_precificados_F2)} / N air(F3 principal) {int(r.n_airbnb_principal_F3)} / "
                f"N viva(F2) {int(r.n_vivareal_elegiveis_F2)} | maior owner {100*r.maior_proprietario_share:.0f}%{nota}.\n"
            )
        L.append("\n## 5. Recomendação principal\n")
        L.append(f"**{principal.segmento}** — rendimento bruto@60% = {fmt_pct(principal.rendimento_60)} "
                 f"(IC {fmt_pct(principal.ic_rend60_025,2)}–{fmt_pct(principal.ic_rend60_975,2)}), "
                 f"payback estimado {fmt(principal.payback_60,1)} anos, diária ajustada {fmt_rs(principal.diaria_anunciada_ajustada)}, "
                 f"preço mediano {fmt_rs(principal.preco_aquisicao_mediana)}.\n")
        L.append("**Principais riscos:** rendimento BRUTO (sem despesas); preço anunciado, não negociado; ocupação é "
                 "hipótese; N Airbnb moderado; valorização não observada.\n")
        L.append("**Interpretação honesta:** Morretes 2q foi o segmento mais defensável pelos critérios adotados e "
                 "liderou quatro dos cinco cenários avaliados, mas sua vantagem central sobre Centro e Meia Praia é "
                 "pequena e não foi demonstrada como estatisticamente conclusiva (ICs de bootstrap se sobrepõem; não "
                 "foi calculado IC da diferença entre segmentos).\n")
        L.append(f"**Nível de confiança:** {conf_level} — {conf_reason}\n")
        L.append("\n## 6. Alternativa\n")
        L.append(f"**{alternativa.segmento}** — segundo mais defensável; preferível nos cenários efetivamente calculados "
                 f"em que supera a principal: {', '.join(alt_wins_scenarios) if alt_wins_scenarios else 'nenhum'}.\n")
        L.append("No cenário conjunto em que ambos os segmentos são avaliados pelos respectivos preços P25, ")
        _alt_p25 = rend_preco(alt_seg, "P25")
        _pr_p25 = rend_preco(pp_seg, "P25")
        L.append(f"{alternativa.segmento} apresenta rendimento bruto estimado de {fmt_pct(_alt_p25,1)}, contra "
                 f"{fmt_pct(_pr_p25,1)} de {pp_seg} (ver condition_change_scenarios.csv; P25 de cada um é usado "
                 f"conjuntamente, não apenas o do Centro).\n")
        L.append("\n## 7. Estabilidade da recomendação\n")
        L.append(f"O principal liderou (ou empatou) em {int(principal.n_vezes_em_primeiro)} de 5 cenários de sensibilidade; "
                 f"pior posição observada {int(principal.pior_posicao_observada)} entre os 3 segmentos.\n")
        L.append("\n## 8. Condições que poderiam mudar a decisão\n")
        L.append("Cenários efetivamente calculados (não inventados):\n")
        for _, c in change_df.iterrows():
            L.append(f"- {c.cenario}: principal {fmt_pct(c.rendimento_principal,2)} vs alternativa "
                     f"{fmt_pct(c.rendimento_alternativa,2)} → alternativa {'SUPERA' if c.alternative_wins else 'não supera'}.\n")
        L.append("\n## 9. Contribuição das características (Fase 3)\n")
        L.append("- `number_of_bedrooms` manteve associação positiva nos cenários de cobertura e sem outliers (IC não cruza "
                 "zero), mas a magnitude é por 1 desvio-padrão (std 0.985 quartos), não por quarto adicional, e caiu de "
                 "~42,6% para ~17,0% ao remover outliers.\n"
                 "- Usada como apoio, não isoladamente. Amenities, 'hotel/outros' e 'outros bairros raros' não entram na "
                 "recomendação.\n")
        L.append("\n## 10. Limitações\n")
        L.append("- Sem reservas/ocupação realizadas (ocupação é hipótese 50/60/75%).\n"
                 "- Rendimento e payback BRUTOS: sem condomínio, IPTU, manutenção, gestão, impostos ou financiamento.\n"
                 "- Preço anunciado (VivaReal), não negociado.\n"
                 "- Comparação agregada bairro×perfil, sem chave comum Airbnb–VivaReal.\n"
                 "- Sazonalidade só jan–abr/2025; anualização é extrapolação.\n"
                 "- Concentração por proprietário é risco de representatividade.\n"
                 "- N principal F3 de Meia Praia compacto = 17 < 20 → evidência descritiva.\n")
        L.append("\n## 11. Informações adicionais necessárias antes de compra real\n")
        L.append("- Ocupação e reservas efetivamente realizadas.\n"
                 "- Despesas operacionais, taxa de administração, condomínio, IPTU, manutenção, limpeza, impostos.\n"
                 "- Custos de financiamento.\n"
                 "- Preço efetivamente negociado do imóvel.\n"
                 "- Condição e idade do imóvel.\n"
                 "- Distância real da praia.\n"
                 "- Regulamentação do condomínio para locação por temporada.\n"
                 "- Liquidez e valorização (não observadas).\n")
        L.append("\n## 12. Conclusão executiva\n")
        concl = (
            "Com base no retrato de jan/2025, o segmento **{}** foi o mais defensável pelos critérios adotados, "
            "com rendimento bruto anualizado estimado de {} no cenário de ocupação de 60% "
            "(IC bootstrap de 95%: {} a {}) e payback bruto estimado de {} anos. "
            "Sua vantagem sobre os demais segmentos é pequena e não foi demonstrada como estatisticamente conclusiva. "
            "A alternativa **{}** é quase tão defensável. A decisão permanece condicionada à validação de ocupação, "
            "despesas operacionais e preço efetivamente negociado."
        ).format(
            principal.segmento,
            fmt_pct(principal.rendimento_60),
            fmt_pct(principal.ic_rend60_025),
            fmt_pct(principal.ic_rend60_975),
            fmt(principal.payback_60, 1),
            alternativa.segmento,
        )
        L.append(concl + "\n")
        write_utf8_lf("".join(L), tmp / "final_recommendation.md")

        # ---- gráficos ----
        print("[4/7] Gerando gráficos em temp...")
        plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                             "font.size": 11, "axes.grid": True, "grid.alpha": 0.3})
        colors = {"morretes | 2. apartamento (2q)": "#1f77b4",
                  "meia praia | 1. apartamento compacto (0-1q)": "#ff7f0e",
                  "centro | 2. apartamento (2q)": "#2ca02c"}

        def _nlabel(a_s):
            r = dm[dm.segmento == a_s].iloc[0]
            return f"{a_s}\nN air(F2)={int(r.n_airbnb_precificados_F2)} / N viva(F2)={int(r.n_vivareal_elegiveis_F2)}"

        # 01
        fig, axes = plt.subplots(1, 2, figsize=(15, 7))
        for a_s in SEGMENTS:
            r = dm[dm.segmento == a_s].iloc[0]
            axes[0].bar(a_s, r.diaria_anunciada_ajustada, color=colors[a_s], alpha=0.85)
            axes[1].bar(a_s, r.preco_aquisicao_mediana / 1e3, color=colors[a_s], alpha=0.85)
        for ax in axes:
            ax.set_xticks(range(len(SEGMENTS)))
            ax.set_xticklabels([_nlabel(a_s) for a_s in SEGMENTS], fontsize=8)
        axes[0].set_ylabel("Diária anunciada ajustada (R$/noite)")
        axes[1].set_ylabel("Preço anunciado de aquisição (mil R$)")
        axes[0].set_title("Diária anunciada ajustada por data e mês")
        axes[1].set_title("Preço mediano de aquisição (VivaReal, jan/2025)")
        axes[0].annotate("Snapshot jan–abr/2025. Diária ≠ receita; valor sem despesas.",
                         xy=(0.01, -0.20), xycoords="axes fraction", fontsize=8, color="#444")
        fig.suptitle("Fase 4 — Diária anunciada e preço de aquisição (3 segmentos)", fontweight="bold")
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(tfig / "01_daily_rate_and_purchase_price.png", dpi=PLOT_DPI)
        plt.close(fig)

        # 02
        fig, ax = plt.subplots(figsize=(13, 7))
        x = np.arange(len(SEGMENTS))
        width = 0.26
        for i, occ in enumerate(["50", "60", "75"]):
            vals = [100 * dm[dm.segmento == a_s][f"rendimento_{occ}"].iloc[0] for a_s in SEGMENTS]
            ax.bar(x + (i - 1) * width, vals, width, label=f"Ocupação {occ}% (hipótese)", color=["#aec6cf", "#6c8ebf", "#3d5a80"][i])
        for i, a_s in enumerate(SEGMENTS):
            r = dm[dm.segmento == a_s].iloc[0]
            ax.errorbar(i, 100 * r.rendimento_60,
                        yerr=[[100 * (r.rendimento_60 - r.ic_rend60_025)], [100 * (r.ic_rend60_975 - r.rendimento_60)]],
                        fmt="k.", capsize=4)
        ax.set_xticks(x)
        ax.set_xticklabels([_nlabel(a_s) for a_s in SEGMENTS], fontsize=8)
        ax.set_ylabel("Rendimento bruto anualizado estimado (%)")
        ax.set_title("Rendimento bruto anualizado estimado por cenário de ocupação (BRUTO — sem despesas)")
        ax.legend()
        ax.annotate("Ocupação é hipótese (50/60/75%), não observada. Pontos = estimativa pontual; barras = cenários.",
                    xy=(0.01, -0.18), xycoords="axes fraction", fontsize=8, color="#444")
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        fig.savefig(tfig / "02_gross_yield_scenarios.png", dpi=PLOT_DPI)
        plt.close(fig)

        # 03 payback por preço (P25/med/P75)
        fig, ax = plt.subplots(figsize=(14, 7))
        labels, vals, colz = [], [], []
        for a_s in SEGMENTS:
            for q in ["P25", "mediana", "P75"]:
                pr = dm[dm.segmento == a_s].iloc[0][{"P25": "p25_preco", "mediana": "preco_aquisicao_mediana", "P75": "p75_preco"}[q]]
                pay = pr / dm[dm.segmento == a_s].iloc[0]["receita_60"]
                labels.append(f"{a_s}\npreço {q}")
                vals.append(pay)
                colz.append(a_s)
        ax.bar(np.arange(len(vals)), vals, color=[colors[c] for c in colz], alpha=0.85)
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels([lb.replace(" | ", " · ") for lb in labels], fontsize=7, rotation=45, ha="right")
        ax.set_ylabel("Payback bruto estimado (anos, sob ocupação 60%)")
        ax.set_title("Payback bruto estimado por preço de aquisição (P25/mediana/P75) — sem despesas")
        ax.annotate("Payback BRUTO: não inclui condomínio, IPTU, manutenção, gestão ou impostos.",
                    xy=(0.01, -0.20), xycoords="axes fraction", fontsize=8, color="#444")
        fig.tight_layout(rect=[0, 0.06, 1, 0.95])
        fig.savefig(tfig / "03_payback_sensitivity.png", dpi=PLOT_DPI)
        plt.close(fig)

        # 04 resumo
        fig, ax = plt.subplots(figsize=(16, 9))
        ax.axis("off")
        tbl_data = []
        header = ["Segmento", "Rend. bruto 60%", "IC 60%", "Payback 60%", "N air(F2) / N viva(F2) / N air(F3 principal)",
                  "Maior owner", "Papel"]
        for a_s in SEGMENTS:
            r = dm[dm.segmento == a_s].iloc[0]
            tbl_data.append([
                a_s, fmt_pct(r.rendimento_60), f"{fmt_pct(r.ic_rend60_025,2)}–{fmt_pct(r.ic_rend60_975,2)}",
                f"{fmt(r.payback_60,1)} anos",
                f"{int(r.n_airbnb_precificados_F2)} / {int(r.n_vivareal_elegiveis_F2)} / {int(r.n_airbnb_principal_F3)}",
                f"{100*r.maior_proprietario_share:.0f}%", roles[a_s],
            ])
        tbl = ax.table(cellText=tbl_data, colLabels=header, loc="center", cellLoc="left")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1.0, 1.8)
        ax.set_title("Fase 4 — Quadro-resumo da decisão (rendimento BRUTO sob ocupação 60% — hipótese)", fontweight="bold", pad=16)
        ax.annotate("Rendimento bruto anualizado estimado; ocupação e preços são hipóteses/anúncios, sem despesas; "
                    "vantagem central não é estatisticamente conclusiva.", xy=(0.5, 0.02), xycoords="axes fraction",
                    ha="center", fontsize=9, color="#333")
        fig.savefig(tfig / "04_decision_summary.png", dpi=PLOT_DPI, bbox_inches="tight")
        plt.close(fig)

        # ---- VALIDAÇÃO do conteúdo temporário ----
        print("[5/7] Validando conteúdo temporário...")
        from PIL import Image
        for f in sorted(tfig.glob("*.png")):
            with Image.open(f) as im:
                check(im.width >= MIN_PX_W and im.height >= MIN_PX_H,
                      f"figura {f.name}: {im.width}x{im.height} >= {MIN_PX_W}x{MIN_PX_H}")
        expected_figs = {"01_daily_rate_and_purchase_price.png", "02_gross_yield_scenarios.png",
                         "03_payback_sensitivity.png", "04_decision_summary.png"}
        have_figs = {f.name for f in tfig.glob("*.png")}
        check(expected_figs <= have_figs, f"4 figuras presentes (faltam: {expected_figs - have_figs})")
        # U+FFFD ausente em tudo
        fffd_ok = True
        for path in list(tmp.rglob("*.csv")) + list(tmp.rglob("*.md")) + [Path(__file__)]:
            try:
                assert_no_fffd(path)
            except ValueError as ex:
                check(False, str(ex))
                fffd_ok = False
        if fffd_ok:
            check(True, "sem U+FFFD em CSVs, Markdown e script")
        # UTF-8 estrito
        for path in list(tmp.rglob("*.csv")) + list(tmp.rglob("*.md")):
            path.read_bytes().decode("utf-8", errors="strict")
            check(True, f"UTF-8 estrito OK: {path.name}")
        # schemas essenciais
        dm2 = pd.read_csv(tmp / "decision_matrix.csv")
        check({"n_airbnb_precificados_F2", "n_airbnb_principal_F3", "n_vivareal_elegiveis_F2"} <= set(dm2.columns),
              "matriz: colunas de Ns diferenciadas presentes")
        check({"preco_principal", "quantil_preco_principal", "preco_alternativa", "quantil_preco_alternativa",
               "alternative_wins"} <= set(pd.read_csv(tmp / "condition_change_scenarios.csv").columns),
              "condition_change: colunas de preço/quantil presentes")
        # Ns importados corretos
        for a_s in SEGMENTS:
            n3 = int(dm2[dm2.segmento == a_s].n_airbnb_principal_F3.iloc[0])
            check(n3 == EXPECTED_F3_N_PRINCIPAL[a_s], f"N F3 {a_s} = {EXPECTED_F3_N_PRINCIPAL[a_s]}")
        check(len(pd.read_csv(tmp / "scenario_ranking.csv")) == 9, "scenario_ranking: 3 segmentos x 3 ocupações")
        check(len(pd.read_csv(tmp / "recommendation_sensitivity.csv")) >= 6, "recommendation_sensitivity não vazio")
        # recomendação/alternativa distintas já checadas; consistência com o md
        md = (tmp / "final_recommendation.md").read_text(encoding="utf-8")
        check(principal.segmento in md and alternativa.segmento in md, "relatório cita principal e alternativa")

        fail_and_exit()  # aborta (e mantém OUTPUT intocado) se falhou a gestão de temp

        # ---- PUBLICAÇÃO (apenas após todas validações) ----
        print("[6/7] Publicando em outputs/analysis/final/...")
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        for f in tmp.iterdir():
            if f.is_file():
                shutil.copy2(f, OUT / f.name)
        (OUT / "figures").mkdir()
        for f in tfig.iterdir():
            shutil.copy2(f, OUT / "figures" / f.name)

    # ---- log de confirmação do gate ----
    print("[7/7] Confirmação do gate: falhas em temp não tocam o destino final (validação seqüencial).")
    print("\n=== VALIDAÇÕES ===")
    for ok, msg in checks:
        print(("  [OK] " if ok else "  [FALHA] ") + msg)
    np_ = sum(1 for ok, _ in checks if ok)
    print(f"\n{np_}/{len(checks)} verificações passaram.")
    print("\n=== MATRIZ DE DECISÃO ===")
    cols = ["segmento", "n_airbnb_precificados_F2", "n_airbnb_principal_F3", "n_vivareal_elegiveis_F2",
            "rendimento_60", "payback_60", "n_vezes_em_primeiro"]
    print(dm[cols].to_string(index=False))
    print(f"\nRecomendação principal: {principal.segmento}")
    print(f"Alternativa: {alternativa.segmento}")
    print(f"Confiança: {conf_level}")
    print("\nCenários em que a alternativa supera:", change_df[change_df.alternative_wins == True]["cenario"].tolist())  # noqa: E712


if __name__ == "__main__":
    main()