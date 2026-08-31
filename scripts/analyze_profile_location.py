"""
analyze_profile_location.py — Fase 1 da análise: perfil do imóvel e localização.

Objetivos:
  1. Perfis de imóvel com maior diária anunciada ajustada por data e mês.
  2. Bairros com melhor desempenho.
  3. Teste explícito da hipótese dos compactos (0–1 quarto) no Centro.

NÃO produz recomendação de compra, retorno, cap rate ou payback (próxima fase).

Métrica principal — "diária anunciada ajustada por data e mês" (NÃO é receita/ADR realizado):
  1. mediana do preço por grupo x stay_date;
  2. média das medianas diárias dentro de cada mês;
  3. média igualmente ponderada dos quatro meses (2025-01 a 2025-04);
  4. só calculada quando os 4 meses estiverem presentes.

Bootstrap: reamostra ANÚNCIOS (nunca linhas), seed 42, 1.000 replicações, percentis 2,5/97,5.
  - Réplica sem nenhuma observação em algum dos 4 meses é INVÁLIDA (NaN).
  - CI publicado só quando >= MIN_VALID_REPS réplicas válidas; senão CI=NA e flag.

Robustez da sensibilidade:
  - coverage_sensitivity.csv contém TODOS os grupos de cada cenário (inclusive N<20).
  - N<20: rank e rank_delta = NA.
  - Grupo que desaparece no cenário => N=0, métrica/rank NA.
  - rank_delta > 0 significa piora de posição (queda no ranking).

Fluxo seguro:
  - outputs/analysis/ só é criado APÓS todas as validações e cálculos terminarem.
  - Gravação determinística com LF (equivalente ao pipeline de preparação).
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "outputs" / "processed"
QUAL = ROOT / "outputs" / "quality"
OUT = ROOT / "outputs" / "analysis"

BOOT_SEED = 42
N_REPS = 1000
MIN_VALID_REPS = 950
EXPECTED_MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04"]
MIN_RANK_N = 20

checks: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    checks.append((cond, msg))


def fail_and_exit() -> None:
    failed = [m for ok, m in checks if not ok]
    if not failed:
        return
    print("\n=== VALIDAÇÕES COM FALHA — abortando SEM gravar outputs/analysis/ ===")
    for m in failed:
        print("  [FALHA] " + m)
    sys.exit(1)


def write_csv_lf(df: pd.DataFrame, path: Path) -> None:
    """Grava CSV com LF independente do SO (determinístico)."""
    with path.open("w", encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False, lineterminator="\n")


def write_md_lf(text: str, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def norm_text(s: pd.Series) -> pd.Series:
    def _n(x: object) -> str:
        if pd.isna(x) or str(x).strip().lower() == "none":
            return "<NA>"
        return (
            unicodedata.normalize("NFKD", str(x))
            .encode("ascii", "ignore")
            .decode("ascii")
            .strip()
            .lower()
        )

    return s.map(_n)


def make_profile(d: pd.DataFrame) -> pd.Series:
    lt = d["listing_type"].astype(str)
    prof = pd.Series("hotel/outros", index=d.index, dtype=object)
    apt = lt == "apartamento"
    prof[apt & (d["number_of_bedrooms"] <= 1)] = "1. apartamento compacto (0-1q)"
    prof[apt & (d["number_of_bedrooms"] == 2)] = "2. apartamento (2q)"
    prof[apt & (d["number_of_bedrooms"] >= 3)] = "3. apartamento (3q+)"
    prof[lt == "casa"] = "4. casa"
    return prof


def adjusted_adr(grp: pd.DataFrame) -> float:
    """Mediana diária -> média mensal -> média igual ponderada dos 4 meses."""
    if len(grp) == 0:
        return np.nan
    daily = grp.groupby("stay_date")["price"].median()
    per = pd.DataFrame({"stay_date": daily.index, "mid": daily.values})
    per["mes"] = pd.to_datetime(per["stay_date"]).dt.to_period("M").astype(str)
    month_mean = per.groupby("mes")["mid"].mean()
    present = sorted(month_mean.index.astype(str).tolist())
    if len(present) == 4 and all(m in present for m in EXPECTED_MONTHS):
        return float(month_mean.mean())
    return np.nan


def make_pivot(grp: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Pivô listing x stay_date (preço) e meses das colunas."""
    day = pd.to_datetime(grp["stay_date"]).dt.normalize()
    pv = grp.pivot_table(index="airbnb_listing_id", columns=day, values="price", aggfunc="median")
    arr = pv.to_numpy(dtype=float)
    months = pd.to_datetime(pv.columns).to_period("M").astype(str).to_numpy()
    return arr, months


def bootstrap_adjusted(grp: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Bootstrap reamostrando anúncios; réplica inválida (mês sem dados) = NaN."""
    if len(grp) == 0:
        return np.full(N_REPS, np.nan)
    arr, months = make_pivot(grp)
    n = arr.shape[0]
    u_months = np.unique(months)
    has4 = len(u_months) == 4 and all(m in u_months for m in EXPECTED_MONTHS)
    outb = np.full(N_REPS, np.nan)
    if not has4:
        return outb
    for k in range(N_REPS):
        idx = rng.integers(0, n, size=n)
        sub = arr[idx]
        day_med = np.nanmedian(sub, axis=0)  # colunas all-NaN possíveis => tratadas abaixo
        ok = True
        mv = []
        for mc in u_months:
            seg = day_med[months == mc]
            if np.isnan(seg).all():
                ok = False
                break
            mv.append(float(np.nanmean(seg)))
        if ok:
            outb[k] = float(np.mean(mv))
    return outb


def ci_reps(vals: np.ndarray, req: int = N_REPS, minv: int = MIN_VALID_REPS) -> tuple:
    """CI percentil (2,5/97,5), nº de réplicas válidas e flag de insuficiência."""
    gd = vals[~np.isnan(vals)]
    n_valid = int(len(gd))
    if n_valid < minv:
        return np.nan, np.nan, req, n_valid, True
    return float(np.percentile(gd, 2.5)), float(np.percentile(gd, 97.5)), req, n_valid, False


def summarize_group(
    grp_prices: pd.DataFrame,
    inv_count: int,
    cov_df: pd.DataFrame,
    rng: np.random.Generator,
) -> dict:
    n_priced = grp_prices["airbnb_listing_id"].nunique()
    per_list = grp_prices.groupby("airbnb_listing_id")["price"].median() if n_priced else pd.Series(dtype=float)
    simple_median = float(per_list.median()) if n_priced else np.nan
    med_cov = float(cov_df["coverage"].median()) if len(cov_df) else np.nan
    val = adjusted_adr(grp_prices)

    bv = bootstrap_adjusted(grp_prices, rng)
    lo, hi, rep_rq, rep_vl, ci_if = ci_reps(bv)

    months_c = (
        pd.to_datetime(grp_prices["stay_date"]).dt.to_period("M").astype(str).nunique()
        if len(grp_prices)
        else 0
    )
    dates_c = pd.to_datetime(grp_prices["stay_date"]).nunique() if len(grp_prices) else 0
    return {
        "anuncios_inventario": int(inv_count),
        "anuncios_precificados": int(n_priced),
        "pct_precificado": (100 * n_priced / inv_count) if inv_count else np.nan,
        "pares_listing_data": int(len(grp_prices)),
        "mediana_cobertura_anuncio": med_cov,
        "mediana_simples_preco_anuncio": simple_median,
        "diaria_ajustada": val,
        "ci_025": lo,
        "ci_975": hi,
        "bootstrap_reps_requested": rep_rq,
        "bootstrap_reps_valid": rep_vl,
        "ci_insuficiente": ci_if,
        "n_meses": months_c,
        "n_datas": dates_c,
    }


def main() -> None:
    # NÃO cria outputs/analysis/ aqui — só após o gate final.
    print("[1/4] Carregando bases analíticas...")
    price = pd.read_csv(PROC / "price_analytic.csv", low_memory=False)
    master = pd.read_csv(PROC / "listing_master.csv", low_memory=False)
    cov = pd.read_csv(QUAL / "coverage_analytic.csv", low_memory=False)

    # ---- validações estruturais ----
    check(len(price) == 58600, f"price_analytic deve ter 58.600 pares (tem {len(price)})")
    check(
        price["airbnb_listing_id"].nunique() == 999,
        f"price_analytic deve ter 999 anúncios (tem {price['airbnb_listing_id'].nunique()})",
    )
    check(
        not price.duplicated(["airbnb_listing_id", "stay_date"]).any(),
        "price_analytic sem duplicatas listing x stay_date",
    )
    check(price["price"].notna().all(), "price_analytic sem preço nulo")
    check(price["stay_date"].notna().all(), "price_analytic sem stay_date nulo")
    check(
        cov["airbnb_listing_id"].nunique() == 999,
        f"coverage_analytic deve ter 999 IDs únicos (tem {cov['airbnb_listing_id'].nunique()})",
    )
    check(cov["airbnb_listing_id"].is_unique, "coverage_analytic: airbnb_listing_id único")

    # join N:1 com master
    before = len(price)
    base = price.merge(
        master[
            ["airbnb_listing_id", "listing_type", "number_of_bedrooms", "suburb", "owner_id"]
        ],
        on="airbnb_listing_id",
        how="left",
        validate="many_to_one",
    )
    check(len(base) == before, "join com master deve manter exatamente 58.600 linhas (N:1)")

    extra_ids = set(base["airbnb_listing_id"]) - set(master["airbnb_listing_id"])
    check(len(extra_ids) == 0, "todos os anúncios precificados devem existir no master")

    # join coverage 1:1 (com validate)
    base = base.merge(
        cov[["airbnb_listing_id", "coverage"]],
        on="airbnb_listing_id",
        how="left",
        validate="many_to_one",
    )
    check(len(base) == before, "join com coverage deve manter exatamente 58.600 linhas (many_to_one)")
    check(
        base["coverage"].notna().all(),
        "cobertura deve estar presente para todos os anúncios precificados",
    )

    # suburb normalizado preservando original
    base["suburb_norm"] = norm_text(base["suburb"])
    base["suburb_label"] = np.where(base["suburb_norm"] == "<NA>", "não informado", base["suburb_norm"])
    rastreio = (
        base[["airbnb_listing_id", "stay_date", "price", "listing_type", "number_of_bedrooms", "suburb"]]
        .isin([np.nan, None, ""])
        .sum()
        .sum()
    )
    check(rastreio == 0, "preço, data, perfil e bairro rastreáveis à origem (sem nulos)")

    print(f"  Base analítica: {len(base)} pares, {base['airbnb_listing_id'].nunique()} anúncios")

    # ---- perfis ----
    print("[2/4] Perfis e bairros...")
    for_analysis = base.copy()
    for_analysis["profile"] = make_profile(for_analysis)
    master["profile"] = make_profile(master)

    inv_profile = master.groupby("profile").size()
    inv_suburb = master.assign(sn=norm_text(master["suburb"])).groupby("sn").size()

    rng = np.random.default_rng(BOOT_SEED)

    # ---- resumo por perfil ----
    prof_rows = []
    for prof in sorted(for_analysis["profile"].unique()):
        gp = for_analysis[for_analysis["profile"] == prof]
        inv = int(inv_profile.get(prof, 0))
        gcov = cov[cov["airbnb_listing_id"].isin(gp["airbnb_listing_id"])]
        row = summarize_group(gp, inv, gcov, rng)
        row["group"] = prof
        row["in_ranking"] = row["anuncios_precificados"] >= MIN_RANK_N
        prof_rows.append(row)
    prof_df = pd.DataFrame(prof_rows)

    # ---- resumo por bairro ----
    sub_rows = []
    for sn in for_analysis["suburb_label"].dropna().unique():
        if sn == "não informado":
            continue
        gp = for_analysis[for_analysis["suburb_label"] == sn]
        inv = int(inv_suburb.get(sn, 0))
        gcov = cov[cov["airbnb_listing_id"].isin(gp["airbnb_listing_id"])]
        row = summarize_group(gp, inv, gcov, rng)
        row["group"] = sn
        row["in_ranking"] = (row["anuncios_precificados"] >= MIN_RANK_N) and (inv > 0)
        sub_rows.append(row)
    gp_n = for_analysis[for_analysis["suburb_label"] == "não informado"]
    if len(gp_n):
        inv_n = int(inv_suburb.get("<NA>", 0))
        row = summarize_group(gp_n, inv_n, cov[cov["airbnb_listing_id"].isin(gp_n["airbnb_listing_id"])], rng)
        row["group"] = "não informado"
        row["in_ranking"] = False
        sub_rows.append(row)
    sub_df = pd.DataFrame(sub_rows)

    # ---- ranking auxiliar (perfil e bairro) ----
    def rank_frame(df: pd.DataFrame) -> pd.DataFrame:
        d = df[df["in_ranking"]].copy()
        d = d.sort_values("diaria_ajustada", ascending=False)
        d["rank"] = np.arange(1, len(d) + 1)
        return d[["group", "rank"]]

    prof_rank_full = rank_frame(prof_df)
    sub_rank_full = rank_frame(sub_df)
    prof_df = prof_df.merge(prof_rank_full, on="group", how="left")
    sub_df = sub_df.merge(sub_rank_full, on="group", how="left")

    # ---- reconcialiações ----
    check(
        int(inv_profile.sum()) == 4441,
        f"perfis do inventário devem somar 4.441 (somam {int(inv_profile.sum())})",
    )
    priced_n = int(for_analysis["airbnb_listing_id"].nunique())
    check(
        priced_n == 999,
        f"perfis precificados devem somar 999 anúncios distintos (tem {priced_n})",
    )
    check(
        for_analysis["suburb_label"].notna().all(),
        "bairros (incl. 'não informado') devem cobrir todos os 999 anúncios precificados",
    )
    for label, dff in [("perfil", prof_df), ("bairro", sub_df)]:
        rr = dff[dff["in_ranking"]]
        ok_meses = bool((rr["n_meses"] == 4).all())
        ok_metr = bool(rr["diaria_ajustada"].notna().all())
        check(ok_meses, f"ranking {label}: grupos com n_meses==4")
        check(ok_metr, f"ranking {label}: grupos com diária ajustada não nula")
        if len(rr):
            ci_ok = bool(((rr["ci_025"] <= rr["diaria_ajustada"]) & (rr["diaria_ajustada"] <= rr["ci_975"])).all())
            check(ci_ok, f"ranking {label}: CI inferior <= ponto <= CI superior quando CI existe")

    # ---- sensibilidade à cobertura ----
    print("[3/4] Sensibilidade à cobertura...")
    scenarios = [
        ("todos", None),
        ("cobertura>=25", 0.25),
        ("cobertura>=50", 0.50),
        ("cobertura>=75", 0.75),
    ]
    levels = {"perfil": "profile", "bairro": "suburb_label"}
    # universo de grupos = presentes no cenário completo ("todos")
    full_prof = sorted(for_analysis["profile"].unique())
    full_sub = sorted(for_analysis[for_analysis["suburb_label"] != "não informado"]["suburb_label"].unique())

    sens_rows = []
    rank_by_scn = {}
    for scn, th in scenarios:
        fa = for_analysis if th is None else for_analysis[for_analysis["coverage"] >= th]
        for level, col in levels.items():
            universe = full_prof if level == "perfil" else full_sub
            tab = []
            for g in universe:
                gp = fa[fa[col] == g]
                n = gp["airbnb_listing_id"].nunique() if len(gp) else 0
                val = adjusted_adr(gp) if n else np.nan
                tab.append({"group": g, "n_anuncios": int(n), "diaria_ajustada": val})
            ranked = pd.DataFrame(tab).sort_values("diaria_ajustada", ascending=False)
            included = ranked[ranked["n_anuncios"] >= MIN_RANK_N]
            rank_map = {}
            for i, r in enumerate(included.itertuples(), start=1):
                rank_map[r.group] = i
            rank_by_scn[(scn, level)] = rank_map
            for _, r in ranked.iterrows():
                r_req, r_val, ci_if = N_REPS, 0, True
                gp = fa[fa[col] == r.group]
                if r.n_anuncios:
                    bv = bootstrap_adjusted(gp, rng)
                    rep_rq = N_REPS
                    _, _, rep_rq, rep_val, ci_f = ci_reps(bv)
                    r_val = rep_val
                    ci_if = ci_f
                sens_rows.append(
                    {
                        "level": level,
                        "group": r.group,
                        "scenario": scn,
                        "n_anuncios": int(r.n_anuncios),
                        "diaria_ajustada": r.diaria_ajustada,
                        "in_ranking": r.n_anuncios >= MIN_RANK_N and not np.isnan(r.diaria_ajustada),
                        "bootstrap_reps_requested": N_REPS,
                        "bootstrap_reps_valid": r_val,
                        "ci_insuficiente": ci_if,
                        "rank": np.nan,
                        "rank_delta": np.nan,
                    }
                )
    sens_df = pd.DataFrame(sens_rows)
    # aplicar rank e rank_delta (NA para fora do ranking)
    for level in levels:
        full_map = rank_by_scn.get(("todos", level), {})
        m = sens_df["level"] == level
        for _, r in sens_df[m].iterrows():
            idx = r.name
            if not bool(r["in_ranking"]):
                continue
            rk = rank_by_scn.get((r["scenario"], level), {}).get(r["group"])
            sens_df.at[idx, "rank"] = rk
            full_rank = full_map.get(r["group"])
            sens_df.at[idx, "rank_delta"] = (rk - full_rank) if (rk is not None and full_rank is not None) else np.nan

    # ---- hipótese compact centro ----
    rng_h = np.random.default_rng(BOOT_SEED)
    compact = for_analysis[for_analysis["profile"].str.startswith("1. apartamento compacto")].copy()
    g_centro = compact[compact["suburb_label"] == "centro"]
    g_fora = compact[compact["suburb_label"] != "centro"]
    g_apt_big = for_analysis[
        for_analysis["profile"].str.startswith("2. apartamento")
        | for_analysis["profile"].str.startswith("3. apartamento")
    ]
    g_apt_big_centro = g_apt_big[g_apt_big["suburb_label"] == "centro"]

    # grupos sem sobreposição
    ids_centro = set(g_centro["airbnb_listing_id"])
    ids_fora = set(g_fora["airbnb_listing_id"])
    ids_big = set(g_apt_big_centro["airbnb_listing_id"])
    check(
        ids_centro.isdisjoint(ids_fora) and ids_centro.isdisjoint(ids_big),
        "hipótese: grupos comparados devem ser sem sobreposição",
    )
    check(
        len(ids_centro) == 78 and len(ids_fora) == 36 and len(ids_big) == 115,
        f"população da hipótese alterada: centro={len(ids_centro)}, fora={len(ids_fora)}, big2q+centro={len(ids_big)} "
        f"(esperado 78/36/115)",
    )

    def comp_row(name, gA, gB):
        a_n = gA["airbnb_listing_id"].nunique()
        b_n = gB["airbnb_listing_id"].nunique()
        cov_a = cov[cov["airbnb_listing_id"].isin(gA["airbnb_listing_id"])]["coverage"].median() if a_n else np.nan
        cov_b = cov[cov["airbnb_listing_id"].isin(gB["airbnb_listing_id"])]["coverage"].median() if b_n else np.nan
        vA = adjusted_adr(gA) if a_n else np.nan
        vB = adjusted_adr(gB) if b_n else np.nan
        diff = (vA - vB) if (not np.isnan(vA) and not np.isnan(vB)) else np.nan
        pct = (100 * diff / vB) if (not np.isnan(diff) and vB not in (0, np.nan)) else np.nan
        # bootstrap da diferença
        va = bootstrap_adjusted(gA, rng_h) if a_n else np.full(N_REPS, np.nan)
        vb = bootstrap_adjusted(gB, rng_h) if b_n else np.full(N_REPS, np.nan)
        diffv = va - vb
        gd = diffv[~np.isnan(diffv)]
        n_valid = int(len(gd))
        insuf = n_valid < MIN_VALID_REPS
        if insuf or n_valid == 0:
            lo, hi = np.nan, np.nan
        else:
            lo, hi = float(np.percentile(gd, 2.5)), float(np.percentile(gd, 97.5))
        return {
            "comparacao": name,
            "grupoA": "compactos Centro",
            "nA": a_n, "coberturaA": cov_a, "diariaA": vA,
            "grupoB": None, "nB": b_n, "coberturaB": cov_b, "diariaB": vB,
            "diferenca_abs": diff, "diferenca_pct_sobre_B": pct,
            "ci_diff_025": lo, "ci_diff_975": hi,
            "bootstrap_reps_requested": N_REPS,
            "bootstrap_reps_valid": n_valid,
            "ci_insuficiente": insuf,
        }

    r1 = comp_row("A: compactos Centro vs compactos fora do Centro", g_centro, g_fora)
    r1["grupoB"] = "compactos fora do Centro"
    r2 = comp_row("B: compactos Centro vs apt 2q+ no Centro", g_centro, g_apt_big_centro)
    r2["grupoB"] = "apt 2q+ no Centro"
    hypo_df = pd.DataFrame([r1, r2])

    def verdict(r):
        if pd.isna(r["diferenca_abs"]):
            return "inconclusiva"
        if bool(r["ci_insuficiente"]) or np.isnan(r["ci_diff_025"]) or np.isnan(r["ci_diff_975"]):
            return "inconclusiva (CI não disponível por bootstrap insuficiente)"
        if r["ci_diff_025"] > 0:
            return "sustentada"
        if r["ci_diff_975"] < 0:
            return "rejeitada"
        return "inconclusiva (CI cruza zero)"

    hypo_df["veredito_bootstrap"] = hypo_df.apply(verdict, axis=1)

    # ---- gate final antes de criar outputs/analysis/ ----
    fail_and_exit()

    OUT.mkdir(parents=True, exist_ok=True)
    print("[4/4] Gravando saídas em outputs/analysis/...")
    order_p = [
        "group", "anuncios_inventario", "anuncios_precificados", "pct_precificado",
        "pares_listing_data", "mediana_cobertura_anuncio", "mediana_simples_preco_anuncio",
        "diaria_ajustada", "ci_025", "ci_975", "bootstrap_reps_requested",
        "bootstrap_reps_valid", "ci_insuficiente", "n_meses", "n_datas", "in_ranking", "rank",
    ]
    write_csv_lf(prof_df[order_p], OUT / "profile_summary.csv")
    write_csv_lf(sub_df[order_p], OUT / "suburb_summary.csv")
    sens_cols = [
        "level", "group", "scenario", "n_anuncios", "diaria_ajustada", "in_ranking",
        "bootstrap_reps_requested", "bootstrap_reps_valid", "ci_insuficiente", "rank", "rank_delta",
    ]
    write_csv_lf(sens_df[sens_cols], OUT / "coverage_sensitivity.csv")
    hypo_cols = [
        "comparacao", "grupoA", "nA", "coberturaA", "diariaA", "grupoB", "nB", "coberturaB",
        "diariaB", "diferenca_abs", "diferenca_pct_sobre_B", "ci_diff_025", "ci_diff_975",
        "bootstrap_reps_requested", "bootstrap_reps_valid", "ci_insuficiente", "veredito_bootstrap",
    ]
    write_csv_lf(hypo_df[hypo_cols], OUT / "compact_centro_hypothesis.csv")

    # ---- findings.md ----
    def fmt(x, nd=0):
        return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{nd}f}"

    L = []
    L.append("# Fase 1 — Perfil do imóvel e localização (diária anunciada ajustada)\n")
    L.append("## 1. Pergunta de negócio\n")
    L.append(
        "Quais perfis de imóvel e bairros de Itapema apresentam as maiores **diárias anunciadas ajustadas "
        "por data e mês**? A tese interna de que apartamentos compactos (0–1 quarto) no Centro teriam diária "
        "superior é testada explicitamente. Não há recomendação de compra nesta fase: eficiência do investimento "
        "depende também do preço de aquisição (VivaReal), tratado na próxima fase.\n"
    )
    L.append("\n## 2. Definição das métricas\n")
    L.append(
        "**Diária anunciada ajustada por data e mês** — NÃO é receita realizada nem ADR realizado:\n"
        "1) mediana do preço por (grupo x stay_date);\n"
        "2) média das medianas diárias dentro de cada mês;\n"
        "3) média igualmente ponderada dos quatro meses (jan–abr/2025);\n"
        "4) calculada somente quando os 4 meses estão presentes.\n\n"
        "IC 95% por bootstrap reamostrando anúncios (seed 42, 1.000 réplicas, percentis 2,5/97,5), publicado "
        "somente com >=950 réplicas válidas. Bairros normalizados (sem acento/caixa); `none`/ausente = "
        "'não informado', fora dos rankings.\n"
    )
    L.append("\n## 3. População e cobertura\n")
    cs = cov["coverage"]
    L.append(
        f"Inventário: 4.441 anúncios (Details). Precificados e analisados: 999 anúncios, 58.600 pares "
        f"listing x stay_date. Cobertura por anúncio (n_datas/105): mediana {fmt(cs.median(),3)}, "
        f"min {fmt(cs.min(),3)}, p25 {fmt(cs.quantile(.25),3)}, p75 {fmt(cs.quantile(.75),3)}, "
        f"max {fmt(cs.max(),3)}.\n"
    )

    L.append("\n## 4. Resultados\n")
    L.append("### Perfis (4 perfis elegíveis ao ranking; exige >=20 anúncios precificados)\n")
    for _, r in prof_df[prof_df.in_ranking].sort_values("diaria_ajustada", ascending=False).iterrows():
        L.append(
            f"- **{r['group']}** (rank {int(r['rank'])}): diária ajustada **R$ {fmt(r['diaria_ajustada'])}** "
            f"IC95 [R$ {fmt(r['ci_025'])}; R$ {fmt(r['ci_975'])}]; N={int(r['anuncios_precificados'])}/"
            f"{int(r['anuncios_inventario'])}; pares={int(r['pares_listing_data'])}; "
            f"cobertura mediana {fmt(r['mediana_cobertura_anuncio'],3)}; boot reps válidas "
            f"{int(r['bootstrap_reps_valid'])}/{int(r['bootstrap_reps_requested'])}.\n"
        )
    L.append("\n> `hotel/outros` (N=18) está fora do ranking por ter <20 anúncios precificados. Portanto há **4 perfis elegíveis**.\n")
    L.append("\n### Bairros (ranking com >=20 anúncios precificados)\n")
    for _, r in sub_df[sub_df.in_ranking].sort_values("diaria_ajustada", ascending=False).iterrows():
        L.append(
            f"- **{r['group']}** (rank {int(r['rank'])}): diária ajustada **R$ {fmt(r['diaria_ajustada'])}** "
            f"IC95 [R$ {fmt(r['ci_025'])}; R$ {fmt(r['ci_975'])}]; N={int(r['anuncios_precificados'])}/"
            f"{int(r['anuncios_inventario'])}; pares={int(r['pares_listing_data'])}; "
            f"cobertura mediana {fmt(r['mediana_cobertura_anuncio'],3)}.\n"
        )
    L.append("\n## 5. Estabilidade nos cenários de cobertura\n")
    L.append("`rank_delta > 0` indica PIORA de posição (queda no ranking) em relação ao cenário 'todos'.\n")
    for scn in ("todos", "cobertura>=25", "cobertura>=50", "cobertura>=75"):
        L.append(f"\n### {scn}\n")
        sub_s = sens_df[(sens_df.scenario == scn) & sens_df.in_ranking]
        for level in ("perfil", "bairro"):
            rows = sub_s[sub_s.level == level].sort_values("rank")
            names = "; ".join(f"{r['group']} (N={int(r['n_anuncios'])} rank {int(r['rank'])})" for _, r in rows.iterrows())
            L.append(f"- {level}: {names if names else '— (nenhum grupo com N>=20)'}\n")
    L.append("\n## 6. Resultado da hipótese (compactos 0–1q no Centro)\n")
    for _, r in hypo_df.iterrows():
        L.append(
            f"- **{r['comparacao']}**: compactos Centro R$ {fmt(r['diariaA'])} (N={int(r['nA'])}) vs "
            f"{r['grupoB']} R$ {fmt(r['diariaB'])} (N={int(r['nB'])}); diferença R$ {fmt(r['diferenca_abs'])} "
            f"({fmt(r['diferenca_pct_sobre_B'],1)}%); CI95 dif [R$ {fmt(r['ci_diff_025'])}; "
            f"R$ {fmt(r['ci_diff_975'])}]; boot valid {int(r['bootstrap_reps_valid'])}/"
            f"{int(r['bootstrap_reps_requested'])}. **Veredito: {r['veredito_bootstrap']}.**\n"
        )
    L.append(
        "\n**Veredito consolidado:**\n"
        "- Comparação A (vs compactos fora do Centro): **inconclusiva** — o IC da diferença cruza zero.\n"
        "- Comparação B (vs apt 2q+ no Centro): **rejeitada** — todo o IC é negativo (compactos têm MENOR diária).\n"
        "- Tese geral de diária superior dos compactos no Centro: **não sustentada**.\n\n"
        "Nota: 0 quarto pode ser studio OU informação não preenchida; o grupo deve ser interpretado com cautela. "
        "Não há linguagem causal nem recomendação de investimento; eficiência depende também do preço de compra.\n"
    )
    L.append("\n## 7. Limitações\n")
    L.append(
        "- Diária anunciada ≠ receita: sem reservas/ocupação observada.\n"
        "- Amostra precificada = 999/4.441 (22%); cobertura varia por anúncio.\n"
        "- Snapshots de janeiro/2025; sazonalidade observável apenas jan–abr/2025.\n"
        "- Diferenças pequenas entre grupos não são evidência conclusiva por ranking.\n"
        "- Grupos com N<20 precificados fora do ranking principal.\n"
        "- 0 quarto pode confundir studio x dado ausente.\n"
    )
    L.append("\n## 8. Questões para a fase VivaReal\n")
    L.append(
        "- Quais perfis/bairros de maior diária têm preço de aquisição compatível (R$/m², por bairro/tipo)?\n"
        "- Condomínio/IPTU estimados (não disponíveis em ~30%) afetam o custo de carregamento?\n"
        "- Como a sazonalidade jan–abr se estende ao ano antes de qualquer retorno?\n"
        "- Sensibilidade da eficiência (diária x preço de compra) aos cenários de ocupação.\n"
    )
    write_md_lf("".join(L), OUT / "phase1_findings.md")

    print("\n=== VALIDAÇÕES ===")
    for ok, msg in checks:
        print(("  [OK] " if ok else "  [FALHA] ") + msg)
    npass = sum(1 for ok, _ in checks if ok)
    print(f"\n{npass}/{len(checks)} verificações passaram.")
    print("\nFase 1 concluída. Saídas em outputs/analysis/.")


if __name__ == "__main__":
    main()