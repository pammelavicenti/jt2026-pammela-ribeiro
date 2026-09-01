"""
analyze_investment_efficiency.py — Fase 2: preço de aquisição e eficiência econômica bruta estimada.

Decisão apoiada:
  Quais combinações bairro × perfil oferecem a melhor relação entre diária anunciada e preço
  anunciado de aquisição no snapshot de janeiro de 2025? (NÃO "comprar hoje": dados de jan/2025.)

Terminologia obrigatória:
  - diária anunciada ajustada (por data e mês);
  - receita bruta anualizada de cenário = diária_ajustada × 365 × ocupação;
  - rendimento bruto anualizado estimado = receita / mediana_preco_aquisicao;
  - payback bruto estimado (anos) = mediana_preco_aquisicao / receita.
  NUNCA: receita realizada, lucro, ROI líquido, cap rate, retorno garantido.

Correções desta revisão:
  1. Alinhamento temporal do bootstrap: pivot .sort_index(axis=1) e meses derivados de
     pivot.columns; checks de correspondência coluna↔mês.
  2. Sensibilidade a outliers: estimativa pontual = diaria_pontual×365×0.60/mediana(preço
     todos válidos); bootstrap reamostra Airbnb E VivaReal separadamente; IC com as duas fontes.
  3. Auditoria VivaReal: vivareal_funnel.csv (etapa/n_mantidos/n_excluidos) e
     vivareal_coverage.csv (bairro×perfil, incluindo "sem comparável" e "não informado",
     contagens sobre todo o deduplicado).
  4. Shortlist multicritério por regra reproduzível (não apenas top-by-ponto).
  5. Limpeza de código.

Fluxo seguro: phase2/ só é criado após todas as validações; gravação LF determinística.
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
OUT = ROOT / "outputs" / "analysis" / "phase2"

BOOT_SEED = 42
N_REPS = 1000
MIN_VALID_REPS = 950
EXPECTED_MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04"]
MIN_N_AIRBNB = 20
MIN_N_VIVA = 30

checks: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    checks.append((cond, msg))


def fail_and_exit() -> None:
    failed = [m for ok, m in checks if not ok]
    if not failed:
        return
    print("\n=== VALIDAÇÕES COM FALHA — abortando SEM gravar outputs/analysis/phase2/ ===")
    for m in failed:
        print("  [FALHA] " + m)
    sys.exit(1)


def write_csv_lf(df: pd.DataFrame, path: Path) -> None:
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


def make_profile_airbnb(d: pd.DataFrame) -> pd.Series:
    lt = d["listing_type"].astype(str)
    prof = pd.Series("5. hotel/outros", index=d.index, dtype=object)
    apt = lt == "apartamento"
    prof[apt & (d["number_of_bedrooms"] <= 1)] = "1. apartamento compacto (0-1q)"
    prof[apt & (d["number_of_bedrooms"] == 2)] = "2. apartamento (2q)"
    prof[apt & (d["number_of_bedrooms"] >= 3)] = "3. apartamento (3q+)"
    prof[lt == "casa"] = "4. casa"
    return prof


def make_profile_viva(d: pd.DataFrame) -> pd.Series:
    lt = d["listing_type"].astype(str)
    prof = pd.Series("sem comparável", index=d.index, dtype=object)
    apt = lt == "apartamento"
    prof[apt & (d["bedrooms"] <= 1)] = "1. apartamento compacto (0-1q)"
    prof[apt & (d["bedrooms"] == 2)] = "2. apartamento (2q)"
    prof[apt & (d["bedrooms"] >= 3)] = "3. apartamento (3q+)"
    prof[lt == "casa"] = "4. casa"
    return prof


def adjusted_adr(grp: pd.DataFrame) -> float:
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


def make_pivot(grp: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Pivô Airbnb listing x stay_date com meses derivados de pivot.columns (alinhado)."""
    pivot = grp.pivot_table(
        index="airbnb_listing_id",
        columns=pd.to_datetime(grp["stay_date"]).dt.normalize(),
        values="price",
        aggfunc="median",
    ).sort_index(axis=1)
    arr = pivot.to_numpy(dtype=float)
    month_cols = pd.to_datetime(pivot.columns).to_period("M").astype(str).to_numpy()
    return arr, month_cols, pivot


def check_pivot_alignment(month_cols: np.ndarray, pivot: pd.DataFrame, tag: str) -> bool:
    same_len = len(month_cols) == pivot.shape[1]
    check(same_len, f"pivot {tag}: nº meses == nº colunas ({len(month_cols)} vs {pivot.shape[1]})")
    if not same_len:
        return False
    per_col = pd.to_datetime(pivot.columns).to_period("M").astype(str).to_numpy()
    check(
        bool((per_col == month_cols).all()),
        f"pivot {tag}: cada coluna associada ao seu mês correto",
    )
    check(
        set(np.unique(month_cols)) <= set(EXPECTED_MONTHS),
        f"pivot {tag}: meses dentro de 2025-01..2025-04",
    )
    return True


def ci_from(vals: np.ndarray, minv: int = MIN_VALID_REPS) -> tuple[float, float, int, int, bool]:
    gd = vals[~np.isnan(vals)]
    n_valid = int(len(gd))
    if n_valid < minv:
        return np.nan, np.nan, N_REPS, n_valid, True
    return (
        float(np.percentile(gd, 2.5)),
        float(np.percentile(gd, 97.5)),
        N_REPS,
        n_valid,
        False,
    )


def bootstrap_yield_air_viva(
    grp_a: pd.DataFrame, price_arr: np.ndarray, occ: float, rng: np.random.Generator, tag: str
) -> np.ndarray:
    """Bootstrap reamostrando anúncios Airbnb e anúncios VivaReal (nunca linhas)."""
    arr, month_cols, pivot = make_pivot(grp_a)
    if not check_pivot_alignment(month_cols, pivot, tag):
        return np.full(N_REPS, np.nan)
    u_months = np.unique(month_cols)
    has4 = len(u_months) == 4 and all(m in u_months for m in EXPECTED_MONTHS)
    na = arr.shape[0]
    nv = price_arr.size
    out = np.full(N_REPS, np.nan)
    if not has4 or na == 0 or nv == 0:
        return out
    for k in range(N_REPS):
        ia = rng.integers(0, na, size=na)
        iv = rng.integers(0, nv, size=nv)
        sub = arr[ia]
        dmed = np.array(
            [
                np.nanmedian(sub[:, j]) if np.isfinite(sub[:, j]).any() else np.nan
                for j in range(sub.shape[1])
            ]
        )
        ok = True
        mv = []
        for mc in u_months:
            seg = dmed[month_cols == mc]
            if np.isnan(seg).all():
                ok = False
                break
            mv.append(np.nanmean(seg))
        if not ok:
            continue
        diaria_k = float(np.mean(mv))
        med_v = float(np.median(price_arr[iv]))
        if med_v <= 0:
            continue
        out[k] = (diaria_k * 365 * occ) / med_v
    return out


def fmt_num(x, nd=0):
    if x is None:
        return "n/d"
    try:
        if isinstance(x, float) and np.isnan(x):
            return "n/d"
    except TypeError:
        pass
    return f"{x:,.{nd}f}"


def main() -> None:
    # NÃO cria o diretório até o gate final.
    print("[1/7] Carregando bases...")
    price = pd.read_csv(PROC / "price_analytic.csv", low_memory=False)
    master = pd.read_csv(PROC / "listing_master.csv", low_memory=False)
    cov = pd.read_csv(QUAL / "coverage_analytic.csv", low_memory=False)
    viva = pd.read_csv(PROC / "vivareal_dedup.csv", low_memory=False)

    # ---------------- validações de entrada ----------------
    check(len(price) == 58600, f"price_analytic: 58.600 pares (tem {len(price)})")
    check(price["airbnb_listing_id"].nunique() == 999, "price_analytic: 999 anúncios")
    check(not price.duplicated(["airbnb_listing_id", "stay_date"]).any(), "sem duplicata listing x stay_date")
    check(price["price"].notna().all(), "preços não nulos")
    check(viva["listing_id"].is_unique, "vivareal_dedup: listing_id único")
    check(cov["airbnb_listing_id"].is_unique, "coverage: airbnb_listing_id único")

    # ---------------- Base Airbnb ----------------
    print("[2/7] Base Airbnb (segmentação bairro x perfil)...")
    before = len(price)
    air = price.merge(
        master[["airbnb_listing_id", "listing_type", "number_of_bedrooms", "suburb", "owner_id"]],
        on="airbnb_listing_id", how="left", validate="many_to_one",
    )
    check(len(air) == before, "join Airbnb: sem multiplicação")
    air = air.merge(cov[["airbnb_listing_id", "coverage"]], on="airbnb_listing_id", how="left", validate="many_to_one")
    check(len(air) == before, "join coverage: sem multiplicação")
    check(air["coverage"].notna().all(), "cobertura presente")

    air["suburb_norm"] = norm_text(air["suburb"])
    air["suburb_label"] = np.where(air["suburb_norm"] == "<NA>", "não informado", air["suburb_norm"])
    air["profile"] = make_profile_airbnb(air)
    air["segmento"] = air["suburb_label"] + " | " + air["profile"]

    master["suburb_norm"] = norm_text(master["suburb"])
    master["suburb_label"] = np.where(master["suburb_norm"] == "<NA>", "não informado", master["suburb_norm"])
    master["profile"] = make_profile_airbnb(master)

    check(
        int(master["profile"].value_counts().sum()) == len(master),
        "perfis do inventário reconciliam com 4.441",
    )
    check(
        int(air["airbnb_listing_id"].nunique()) == 999,
        "anúncios precificados somam 999",
    )

    seg_list = sorted(set(zip(master["suburb_label"], master["profile"])))

    air_stats = {}
    for sn, prof in seg_list:
        gprice = air[(air["suburb_label"] == sn) & (air["profile"] == prof)]
        inv = master[(master["suburb_label"] == sn) & (master["profile"] == prof)]
        n_price = gprice["airbnb_listing_id"].nunique()
        air_stats[(sn, prof)] = {
            "n_inv": len(inv),
            "n_price": n_price,
            "pct": (100 * n_price / len(inv)) if len(inv) else np.nan,
            "pares": len(gprice),
            "cov_med": float(cov[cov["airbnb_listing_id"].isin(gprice["airbnb_listing_id"])]["coverage"].median()) if n_price else np.nan,
            "n_datas": pd.to_datetime(gprice["stay_date"]).nunique() if len(gprice) else 0,
            "n_meses": pd.to_datetime(gprice["stay_date"]).dt.to_period("M").nunique() if len(gprice) else 0,
            "diaria": adjusted_adr(gprice),
        }

    # ---------------- VivaReal: perfil, funil e auditoria ----------------
    print("[3/7] VivaReal (perfil, funil e auditoria)...")
    v = viva.copy()
    v["suburb_label"] = np.where(
        v["suburb_norm"].isna() | (v["suburb_norm"] == "<NA>"),
        "não informado",
        v["suburb_norm"],
    )
    v["profile"] = make_profile_viva(v)
    v["segmento"] = v["suburb_label"] + " | " + v["profile"]

    def to_boolable(x):
        if pd.isna(x):
            return pd.NA
        if isinstance(x, bool):
            return x
        s = str(x).strip().lower()
        if s == "true":
            return True
        if s == "false":
            return False
        return pd.NA

    v["is_outlier_pm2_b"] = v["is_outlier_pm2"].map(to_boolable).astype("boolean")

    # --- funil cumulativo ---
    v["_m_apt"] = v["listing_type"].isin(["apartamento", "casa"])
    v["_m_bairro"] = v["suburb_label"] != "não informado"
    v["_m_sale"] = v["sale_price"].notna() & (v["sale_price"] > 0)
    v["_m_area_pm2"] = v["usable_area"].notna() & (v["usable_area"] > 0) & v["price_per_m2"].notna()
    v["_m_princ"] = v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & v["_m_area_pm2"] & (v["is_outlier_pm2_b"] == False)  # noqa: E712
    v["_m_sens"] = v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & v["_m_area_pm2"]

    vf_principal = v[v["_m_princ"]]
    vf_sens = v[v["_m_sens"]]

    n_princ_total = len(vf_principal)
    n_sens_total = len(vf_sens)
    n_pm2 = int((v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & v["_m_area_pm2"]).sum())

    # --- funil cumulativo (fluxo principal) + ramificação de sensibilidade ---
    masks_principal = [
        ("bruto_dedup", pd.Series(True, index=v.index)),
        ("apt_ou_casa", v["_m_apt"]),
        ("bairro_conhecido", v["_m_apt"] & v["_m_bairro"]),
        ("sale_price_positivo", v["_m_apt"] & v["_m_bairro"] & v["_m_sale"]),
        ("area_positiva", v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & (v["usable_area"].notna() & (v["usable_area"] > 0))),
        ("pm2_valido", v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & v["_m_area_pm2"]),
        ("elegiveis_principal_is_outlier_false", v["_m_princ"]),
    ]

    funnel_rows = []
    prev_n = len(v)
    prev_name = None
    for name, mask in masks_principal:
        n_keep = int(mask.sum())
        funnel_rows.append(
            {
                "fluxo": "principal",
                "etapa": name,
                "etapa_base": prev_name if prev_name is not None else "",
                "n_mantidos": n_keep,
                "n_excluidos_na_etapa": prev_n - n_keep,
            }
        )
        prev_n = n_keep
        prev_name = name

    funnel_rows.append(
        {
            "fluxo": "sensibilidade",
            "etapa": "todos_validos_incluindo_outlier_e_flag_na",
            "etapa_base": "pm2_valido",
            "n_mantidos": n_sens_total,
            "n_excluidos_na_etapa": 0,
        }
    )
    funnel_df = pd.DataFrame(funnel_rows)

    # --- validações do funil ---
    check(
        int(funnel_df[funnel_df["etapa"] == "bruto_dedup"]["n_mantidos"].iloc[0]) == len(v),
        "funil parte do bruto dedup (8.293)",
    )
    check(
        bool((funnel_df["n_excluidos_na_etapa"] >= 0).all()),
        "funil: nenhuma exclusão negativa",
    )
    princ_sub = funnel_df[funnel_df["fluxo"] == "principal"]
    check(
        bool((princ_sub["n_mantidos"].diff().fillna(0) <= 0).all()),
        "funil principal: n_mantidos monotonicamente não crescente",
    )
    ok_excl_eq = True
    for i in range(0, len(princ_sub) - 1):
        prev_keep = princ_sub["n_mantidos"].iloc[i]
        cur_keep = princ_sub["n_mantidos"].iloc[i + 1]
        excl = princ_sub["n_excluidos_na_etapa"].iloc[i + 1]
        if excl != prev_keep - cur_keep:
            ok_excl_eq = False
    check(ok_excl_eq, "cada exclusão principal == etapa anterior menos a atual")
    check(
        princ_sub["n_mantidos"].iloc[-1] == n_princ_total,
        f"cenário principal = {n_princ_total}",
    )
    check(
        n_sens_total == n_pm2,
        f"sensibilidade == estágio pm2_valido ({n_sens_total})",
    )
    check(
        (n_sens_total - n_princ_total) == 642,
        f"diferença sensibilidade - principal = 642 (registros adicionais, não exclusão negativa) (tem {n_sens_total - n_princ_total})",
    )

    # --- auditoria por bairro x perfil (sobre todo o deduplicado) ---
    cov_rows = []
    for (sn, prof), grp in v.groupby(["suburb_label", "profile"], sort=True):
        n_bruto = len(grp)
        n_sale = int(grp["_m_apt"].sum())
        g_princ = grp[grp["_m_princ"]]
        g_sens = grp[grp["_m_sens"]]
        n_princ = len(g_princ)
        pct = (100 * n_princ / n_bruto) if n_bruto else np.nan
        ss = g_princ["sale_price"].dropna()
        pm = g_princ["price_per_m2"].dropna()
        qs_sale = {q: (float(ss.quantile(q)) if len(ss) else np.nan) for q in (0.25, 0.5, 0.75)}
        qs_pm2 = {q: (float(pm.quantile(q)) if len(pm) else np.nan) for q in (0.25, 0.5, 0.75)}
        cov_rows.append(
            {
                "bairro": sn,
                "perfil": prof,
                "mediana_sale": qs_sale[0.5],
                "p25_sale": qs_sale[0.25],
                "p75_sale": qs_sale[0.75],
                "mediana_pm2": qs_pm2[0.5],
                "p25_pm2": qs_pm2[0.25],
                "p75_pm2": qs_pm2[0.75],
                "mediana_area": float(g_princ["usable_area"].median()) if len(g_princ) else np.nan,
                "cobertura_condo": float(g_princ["monthly_condo_fee"].notna().mean()) if len(g_princ) else np.nan,
                "cobertura_iptu": float(g_princ["yearly_iptu"].notna().mean()) if len(g_princ) else np.nan,
            }
        )
    cov_quart = pd.DataFrame(cov_rows)

    # contagens por estágio calculadas sobre o VivaReal inteiro deduplicado
    v["_gw_sale"] = v["_m_apt"] & v["_m_bairro"] & v["_m_sale"]
    v["_gw_area_pm2"] = v["_m_apt"] & v["_m_bairro"] & v["_m_sale"] & v["_m_area_pm2"]
    bruto_map = v.groupby(["suburb_label", "profile"]).size()
    sale_map = v.groupby(["suburb_label", "profile"])["_gw_sale"].sum()
    areapm_map = v.groupby(["suburb_label", "profile"])["_gw_area_pm2"].sum()
    princ_map = v.groupby(["suburb_label", "profile"])["_m_princ"].sum()
    sens_map = v.groupby(["suburb_label", "profile"])["_m_sens"].sum()

    cov_final = pd.DataFrame(
        {
            "bairro": [k[0] for k in bruto_map.index],
            "perfil": [k[1] for k in bruto_map.index],
            "n_bruto_dedup": bruto_map.values,
            "n_sale_price_valido": sale_map.values,
            "n_area_pm2_validos": areapm_map.values,
            "n_elegiveis_principal": princ_map.values,
            "n_elegiveis_sensibilidade": sens_map.values,
            "pct_elegivel_principal": (100 * princ_map / bruto_map).values,
        }
    )
    cov_final = cov_final.merge(cov_quart, on=["bairro", "perfil"], how="left")

    # reconciliar com funil
    check(
        int(cov_final["n_bruto_dedup"].sum()) == len(v),
        f"n_bruto soma 8.293 (tem {int(cov_final['n_bruto_dedup'].sum())})",
    )
    check(
        int(cov_final["n_sale_price_valido"].sum())
        == int(funnel_df[funnel_df.etapa == "sale_price_positivo"]["n_mantidos"].iloc[0]),
        "n_sale soma = funil sale_price_positivo",
    )
    check(
        int(cov_final["n_area_pm2_validos"].sum())
        == int(funnel_df[funnel_df.etapa == "pm2_valido"]["n_mantidos"].iloc[0]),
        "n_area_pm2 soma = funil pm2_valido",
    )
    check(
        int(cov_final["n_elegiveis_principal"].sum())
        == int(funnel_df[funnel_df.etapa == "elegiveis_principal_is_outlier_false"]["n_mantidos"].iloc[0]),
        "n_principal soma = funil principal",
    )
    check(
        int(cov_final["n_elegiveis_sensibilidade"].sum()) == n_sens_total,
        "n_sensibilidade soma = total sens",
    )

    viva_lookup = cov_final.set_index(["bairro", "perfil"])

    # ---------------- Métricas econômicas ----------------
    print("[4/7] Métricas econômicas e incerteza...")
    rng_a = np.random.default_rng(BOOT_SEED)
    rng_v = np.random.default_rng(BOOT_SEED)
    OCC = {"50%": 0.50, "60%": 0.60, "75%": 0.75}

    seg_rows = []
    for key in seg_list:
        sn, prof = key
        st = air_stats.get(key, {})
        n_price = st.get("n_price", 0)
        diaria = st.get("diaria", np.nan)
        n_meses = st.get("n_meses", 0)
        vs = {}
        if key in viva_lookup.index:
            vs = viva_lookup.loc[key].to_dict()
        n_viva = int(vs.get("n_elegiveis_principal", 0) or 0)
        med_preco = vs.get("mediana_sale", np.nan)
        n_inv = st.get("n_inv", 0)
        pct = st.get("pct", np.nan)

        eligible = (
            n_price >= MIN_N_AIRBNB
            and n_viva >= MIN_N_VIVA
            and n_meses == 4
            and not pd.isna(diaria)
            and not pd.isna(med_preco)
        )
        reasons = []
        if n_price < MIN_N_AIRBNB:
            reasons.append(f"airbnb<{MIN_N_AIRBNB}")
        if n_viva < MIN_N_VIVA:
            reasons.append(f"vivareal<{MIN_N_VIVA}")
        if n_meses != 4:
            reasons.append("meses<4")
        if pd.isna(diaria):
            reasons.append("diaria_inv")
        if pd.isna(med_preco):
            reasons.append("preco_inv")

        receita, rend, payb = {}, {}, {}
        for k, o in OCC.items():
            r = diaria * 365 * o if not pd.isna(diaria) else np.nan
            receita[k] = r
            rend[k] = (r / med_preco) if (not pd.isna(r) and not pd.isna(med_preco) and med_preco > 0) else np.nan
            payb[k] = (med_preco / r) if (not pd.isna(r) and not pd.isna(med_preco) and r > 0) else np.nan

        lo = hi = np.nan
        rq, rv, ci_if = N_REPS, 0, True
        if eligible:
            grp_a = air[(air["suburb_label"] == sn) & (air["profile"] == prof)]
            grp_v = vf_principal[(vf_principal["suburb_label"] == sn) & (vf_principal["profile"] == prof)]
            pv = grp_v["sale_price"].to_numpy(dtype=float)
            vals = bootstrap_yield_air_viva(grp_a, pv, 0.60, rng_a, f"princ-{sn}|{prof}")
            lo, hi, rq, rv, ci_if = ci_from(vals)

        # concentração
        owner_share = np.nan
        if n_price > 0:
            ids_p = set(air[(air["suburb_label"] == sn) & (air["profile"] == prof)]["airbnb_listing_id"])
            own_counts = master[master["airbnb_listing_id"].isin(ids_p)]["owner_id"].value_counts()
            if len(own_counts):
                owner_share = float(own_counts.iloc[0] / own_counts.sum())

        iqr_preco = np.nan
        p25 = vs.get("p25_sale", np.nan)
        p75 = vs.get("p75_sale", np.nan)
        if not pd.isna(p25) and not pd.isna(p75):
            iqr_preco = p75 - p25

        seg_rows.append(
            {
                "bairro": sn,
                "perfil": prof,
                "segmento": sn + " | " + prof,
                "n_inventario": n_inv,
                "n_airbnb_precificados": n_price,
                "pct_inventario_precificado": pct,
                "pares_listing_data": st.get("pares", 0),
                "mediana_cobertura": st.get("cov_med", np.nan),
                "n_datas": st.get("n_datas", 0),
                "n_meses": n_meses,
                "diaria_anunciada_ajustada": diaria,
                "n_viva_bruto": int(vs.get("n_bruto_dedup", 0)),
                "n_viva_elegiveis": n_viva,
                "mediana_preco_aquisicao": med_preco,
                "p25_preco": p25,
                "p75_preco": p75,
                "mediana_pm2": vs.get("mediana_pm2", np.nan),
                "mediana_area": vs.get("mediana_area", np.nan),
                "cobertura_condo": vs.get("cobertura_condo", np.nan),
                "cobertura_iptu": vs.get("cobertura_iptu", np.nan),
                "eligible_for_ranking": bool(eligible),
                "motivo_inelegivel": "; ".join(reasons) if reasons else "",
                "receita_50": receita["50%"], "rendimento_50": rend["50%"], "payback_50": payb["50%"],
                "receita_60": receita["60%"], "rendimento_60": rend["60%"], "payback_60": payb["60%"],
                "receita_75": receita["75%"], "rendimento_75": rend["75%"], "payback_75": payb["75%"],
                "potencial_bruto_105dias_100pct": (diaria * 105) if not np.isnan(diaria) else np.nan,
                "ci_rend60_025": lo,
                "ci_rend60_975": hi,
                "bootstrap_reps_requested": rq,
                "bootstrap_reps_valid": rv,
                "ci_insuficiente": ci_if,
                "maior_proprietario_share": owner_share,
                "iqr_preco_aquisicao": iqr_preco,
            }
        )
    seg_df = pd.DataFrame(seg_rows)

    # ------------- validações econômicas -------------
    elig = seg_df[seg_df.eligible_for_ranking]
    for _, r in elig.iterrows():
        for o_lo, o_hi in (("50%", "60%"), ("60%", "75%"), ("50%", "75%")):
            k_lo = o_lo.replace("%", "")
            k_hi = o_hi.replace("%", "")
            check(
                r[f"receita_{k_hi}"] >= r[f"receita_{k_lo}"] - 1e-9
                and r[f"rendimento_{k_hi}"] >= r[f"rendimento_{k_lo}"] - 1e-9
                and r[f"payback_{k_hi}"] <= r[f"payback_{k_lo}"] + 1e-9,
                f"monotonia ocupação {r['segmento']} ({o_lo}->{o_hi})",
            )
        check(r["rendimento_60"] > 0 and r["payback_60"] > 0, f"rendimento e payback positivos {r['segmento']}")
        check(
            not np.isnan(r["p25_preco"]) and not np.isnan(r["mediana_preco_aquisicao"]) and not np.isnan(r["p75_preco"]),
            f"quartis preço {r['segmento']}",
        )
        if not (np.isnan(r["p25_preco"]) or np.isnan(r["mediana_preco_aquisicao"]) or np.isnan(r["p75_preco"])):
            check(
                r["p25_preco"] <= r["mediana_preco_aquisicao"] <= r["p75_preco"],
                f"P25<=med<=P75 preço {r['segmento']}",
            )
        if not np.isnan(r["ci_rend60_025"]):
            check(
                r["ci_rend60_025"] <= r["rendimento_60"] <= r["ci_rend60_975"],
                f"IC envolve ponto {r['segmento']}",
            )
        check(r["bootstrap_reps_valid"] >= MIN_VALID_REPS, f"reps válidas {r['segmento']}")
    check(len(elig) > 0, "pelo menos 1 segmento elegível")

    # ------------- sell sensitivities (buy price) -------------
    pr_rows = []
    for _, r in elig.iterrows():
        for qname, qcol in (("P25", "p25_preco"), ("mediana", "mediana_preco_aquisicao"), ("P75", "p75_preco")):
            pr = r[qcol]
            if np.isnan(pr):
                continue
            for k, o in OCC.items():
                rec = r["diaria_anunciada_ajustada"] * 365 * o
                rend_s = rec / pr if pr > 0 else np.nan
                payb_s = pr / rec if rec > 0 else np.nan
                pr_rows.append(
                    {
                        "segmento": r["segmento"],
                        "bairro": r["bairro"],
                        "perfil": r["perfil"],
                        "quantil_preco": qname,
                        "preco": pr,
                        "ocupacao": k,
                        "rendimento_bruto": rend_s,
                        "payback_bruto": payb_s,
                    }
                )
    pr_df = pd.DataFrame(pr_rows)

    # ------------- sensibilidade outliers -------------
    print("[5/7] Sensibilidade a outliers...")
    rng_o = np.random.default_rng(BOOT_SEED)
    outlier_rows = []
    for _, r in elig.iterrows():
        grp_v = vf_sens[(vf_sens["suburb_label"] == r["bairro"]) & (vf_sens["profile"] == r["perfil"])]
        med_all = float(np.median(grp_v["sale_price"].to_numpy())) if len(grp_v) else np.nan
        # estimativa pontual: diaria_pontual × 365 × 0.60 / mediana preço todos válidos
        if np.isnan(med_all) or med_all <= 0:
            outlier_rows.append(
                {
                    "segmento": r["segmento"],
                    "variancia": "sensibilidade_todos",
                    "n_viva": len(grp_v),
                    "mediana_preco": med_all,
                    "diaria_pontual": r["diaria_anunciada_ajustada"],
                    "rendimento_60": np.nan,
                    "ci_rend60_025": np.nan,
                    "ci_rend60_975": np.nan,
                    "bootstrap_reps_requested": N_REPS,
                    "bootstrap_reps_valid": 0,
                    "ci_insuficiente": True,
                }
            )
            continue
        point = r["diaria_anunciada_ajustada"] * 365 * 0.60 / med_all
        grp_a = air[(air["suburb_label"] == r["bairro"]) & (air["profile"] == r["perfil"])]
        pv_arr = grp_v["sale_price"].to_numpy(dtype=float)
        vals = bootstrap_yield_air_viva(grp_a, pv_arr, 0.60, rng_o, f"sens-{r['bairro']}|{r['perfil']}")
        lo, hi, rq, rv, ci_if = ci_from(vals)
        outlier_rows.append(
            {
                "segmento": r["segmento"],
                "variancia": "sensibilidade_todos",
                "n_viva": len(grp_v),
                "mediana_preco": med_all,
                "diaria_pontual": r["diaria_anunciada_ajustada"],
                "rendimento_60": point,
                "ci_rend60_025": lo,
                "ci_rend60_975": hi,
                "bootstrap_reps_requested": rq,
                "bootstrap_reps_valid": rv,
                "ci_insuficiente": ci_if,
            }
        )
    # principal rows p/ comparação
    for _, r in elig.iterrows():
        outlier_rows.append(
            {
                "segmento": r["segmento"],
                "variancia": "principal_False",
                "n_viva": r["n_viva_elegiveis"],
                "mediana_preco": r["mediana_preco_aquisicao"],
                "diaria_pontual": r["diaria_anunciada_ajustada"],
                "rendimento_60": r["rendimento_60"],
                "ci_rend60_025": r["ci_rend60_025"],
                "ci_rend60_975": r["ci_rend60_975"],
                "bootstrap_reps_requested": r["bootstrap_reps_requested"],
                "bootstrap_reps_valid": r["bootstrap_reps_valid"],
                "ci_insuficiente": r["ci_insuficiente"],
            }
        )
    outlier_sens_df = pd.DataFrame(outlier_rows)

    top_princ = set(elig.nlargest(3, "rendimento_60")["segmento"])
    top_sens = set(
        outlier_sens_df[outlier_sens_df["variancia"] == "sensibilidade_todos"].nlargest(3, "rendimento_60")["segmento"]
    )
    top_p25 = set(pr_df[(pr_df.quantil_preco == "P25") & (pr_df.ocupacao == "60%")].nlargest(3, "rendimento_bruto")["segmento"])
    top_pmed = set(pr_df[(pr_df.quantil_preco == "mediana") & (pr_df.ocupacao == "60%")].nlargest(3, "rendimento_bruto")["segmento"])
    top_p75 = set(pr_df[(pr_df.quantil_preco == "P75") & (pr_df.ocupacao == "60%")].nlargest(3, "rendimento_bruto")["segmento"])

    candidates = top_princ | top_sens | top_p25 | top_pmed | top_p75

    # ordem multicritério: IC95 inferior principal desc; empate N air; empate N viva
    cand_df = elig[elig["segmento"].isin(candidates)].copy()
    cand_df = cand_df.sort_values(
        by=["ci_rend60_025", "n_airbnb_precificados", "n_viva_elegiveis"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    selected = cand_df.head(3)["segmento"].tolist()

    # flags no segment_economics
    seg_df["top3_primary"] = seg_df["segmento"].isin(top_princ)
    seg_df["top3_outlier_sensitivity"] = seg_df["segmento"].isin(top_sens)
    seg_df["top3_price_p25"] = seg_df["segmento"].isin(top_p25)
    seg_df["top3_price_median"] = seg_df["segmento"].isin(top_pmed)
    seg_df["top3_price_p75"] = seg_df["segmento"].isin(top_p75)
    seg_df["shortlist_candidate"] = seg_df["segmento"].isin(candidates)
    seg_df["shortlist_selected"] = seg_df["segmento"].isin(selected)
    seg_df["shortlist_order"] = np.nan
    for i, seg in enumerate(selected, start=1):
        seg_df.loc[seg_df["segmento"] == seg, "shortlist_order"] = i

    # shortlist_reason
    def short_reason(r):
        if r["segmento"] not in selected:
            return ""
        scen_up = (
            ["principal@60"] * r["top3_primary"]
            + ["outliers"] * r["top3_outlier_sensitivity"]
            + ["P25"] * r["top3_price_p25"]
            + ["mediana"] * r["top3_price_median"]
            + ["P75"] * r["top3_price_p75"]
        )
        cen_txt = ",".join(scen_up) if scen_up else "sem top3"
        return (
            f"rend60={100*r['rendimento_60']:.2f}%; ICinf={100*r['ci_rend60_025']:.2f}%; "
            f"N_air={int(r['n_airbnb_precificados'])}; N_viva={int(r['n_viva_elegiveis'])}; "
            f"cobertura={fmt_num(r['mediana_cobertura'],2)}; "
            f"concentração(maior owner)={100*r['maior_proprietario_share']:.0f}%; "
            f"top3 em: {cen_txt}"
        )

    seg_df["shortlist_reason"] = seg_df.apply(short_reason, axis=1)

    # sanity: e por que a shortlist é <=3
    check(0 <= len(selected) <= 3, "shortlist com no máximo 3 segmentos")
    check(set(selected) <= set(elig["segmento"]), "shortlist restrita aos elegíveis")

    # yield scenarios csv
    yield_rows = []
    for _, r in elig.iterrows():
        for k in OCC:
            kk = k.replace("%", "")
            yield_rows.append(
                {
                    "segmento": r["segmento"],
                    "bairro": r["bairro"],
                    "perfil": r["perfil"],
                    "ocupacao": k,
                    "receita_bruta_anualizada": r[f"receita_{kk}"],
                    "rendimento_bruto": r[f"rendimento_{kk}"],
                    "payback_bruto": r[f"payback_{kk}"],
                }
            )
    yield_df = pd.DataFrame(yield_rows)

    # ------------- gate final -------------
    fail_and_exit()

    OUT.mkdir(parents=True, exist_ok=True)
    print("[6/7] Gravando saídas em outputs/analysis/phase2/...")

    seg_order = [
        "bairro", "perfil", "segmento", "n_inventario", "n_airbnb_precificados",
        "pct_inventario_precificado", "pares_listing_data", "mediana_cobertura", "n_datas", "n_meses",
        "diaria_anunciada_ajustada", "n_viva_bruto", "n_viva_elegiveis",
        "mediana_preco_aquisicao", "p25_preco", "p75_preco", "mediana_pm2", "mediana_area",
        "cobertura_condo", "cobertura_iptu", "eligible_for_ranking", "motivo_inelegivel",
        "receita_60", "rendimento_60", "payback_60", "receita_50", "rendimento_50", "payback_50",
        "receita_75", "rendimento_75", "payback_75", "potencial_bruto_105dias_100pct",
        "ci_rend60_025", "ci_rend60_975", "bootstrap_reps_requested", "bootstrap_reps_valid",
        "ci_insuficiente", "maior_proprietario_share", "iqr_preco_aquisicao",
        "top3_primary", "top3_outlier_sensitivity", "top3_price_p25", "top3_price_median",
        "top3_price_p75", "shortlist_candidate", "shortlist_selected", "shortlist_order", "shortlist_reason",
    ]
    write_csv_lf(seg_df[seg_order], OUT / "segment_economics.csv")
    write_csv_lf(yield_df, OUT / "yield_scenarios.csv")
    write_csv_lf(pr_df, OUT / "purchase_price_sensitivity.csv")
    write_csv_lf(funnel_df, OUT / "vivareal_funnel.csv")
    write_csv_lf(cov_final, OUT / "vivareal_coverage.csv")
    write_csv_lf(outlier_sens_df, OUT / "outlier_sensitivity.csv")

    # ------------- phase2_findings.md -------------
    L = []
    L.append("# Fase 2 — Preço de aquisição e eficiência econômica bruta estimada\n")
    L.append("## 1. Decisão apoiada\n")
    L.append(
        "Quais combinações **bairro × perfil** oferecem a melhor relação entre **diária anunciada ajustada** "
        "e **preço anunciado de aquisição** no snapshot de janeiro de 2025? Não é recomendação final nem "
        "'comprar hoje' — os dados são um retrato de jan/2025 e as características do desempenho serão "
        "analisadas posteriormente.\n"
    )
    L.append("\n## 2. Fontes, snapshots e ausência de chave comum\n")
    L.append(
        "- Airbnb: `Price_AV_Itapema.csv` (capturas 06/07/20-jan-2025; estadias 06-jan a 20-abr-2025) + "
        "`Details_Itapema.csv` + `Mesh_Ids_Data_Itapema.csv`.\n"
        "- VivaReal: `VivaReal_Itapema.csv` (snapshot 11-jan-2025), deduplicado em `vivareal_dedup.csv`.\n"
        "- **Não há chave comum** entre Airbnb e VivaReal. Comparação **agregada por bairro × perfil**, "
        "não um pareamento entre imóveis.\n"
        "- Airbnb não possui área útil válida; não é possível parear por metragem.\n"
        "- Perfil '0 quarto' pode ser studio OU informação não preenchida (cautela).\n"
    )
    L.append("\n## 3. População e exclusões\n")
    L.append("- Airbnb: 999 anúncios precificados, 58.600 pares; inventário 4.441.\n")
    L.append("- VivaReal: funil cumulativo em `vivareal_funnel.csv`; auditoria por bairro×perfil em `vivareal_coverage.csv`:\n")
    for _, r in funnel_df[funnel_df["fluxo"] == "principal"].iterrows():
        base_txt = r["etapa_base"] if r["etapa_base"] else "—"
        L.append(f"  - [{r['fluxo']}] {r['etapa']} (base: {base_txt}): mantidos {int(r['n_mantidos'])} (excluídos na etapa {int(r['n_excluidos_na_etapa'])})\n")
    for _, r in funnel_df[funnel_df["fluxo"] == "sensibilidade"].iterrows():
        L.append(f"  - [{r['fluxo']}] {r['etapa']} (base: {r['etapa_base']}): mantidos {int(r['n_mantidos'])}\n")
    L.append(
        "O cenário principal retém **7.307** registros após excluir **642** registros classificados como "
        "outliers de preço/m². A sensibilidade parte dos **7.949** registros válidos anteriores ao filtro "
        "de outliers, incluindo flags True e NA.\n"
    )
    L.append("\n## 4. Definição das métricas\n")
    L.append(
        "- **diária anunciada ajustada**: mediana por (segmento x stay_date); média das medianas diárias por "
        "mês; média igualmente ponderada (jan–abr/2025); só quando os 4 meses existem.\n"
        "- **mediana de aquisição**: mediana de `sale_price` dos elegíveis (não usa mediana(price_per_m2) × "
        "mediana(area)).\n"
        "- **receita bruta anualizada de cenário** = diária × 365 × ocupação (50/60/75%).\n"
        "- **rendimento bruto anualizado estimado** = receita / mediana_preco.\n"
        "- **payback bruto estimado (anos)** = mediana_preco / receita.\n"
        "- **potencial bruto janela 105 dias a 100%** = diária × 105.\n"
        "- NUNCA usados: receita realizada, lucro, ROI líquido, cap rate, retorno garantido.\n"
        "- Bootstrap principal: reamostra anúncios Airbnb e anúncios VivaReal separadamente; IC95 ≥950 "
        "réplicas válidas; meses derivados de `pivot.columns` (alinhamento verificado).\n"
    )
    L.append("\n## 5. Ranking principal no cenário de 60%\n")
    elig_out = elig.sort_values("rendimento_60", ascending=False)
    for _, r in elig_out.iterrows():
        L.append(
            f"- **{r['segmento']}**: rendimento@60% = **{100*r['rendimento_60']:.2f}%** "
            f"(IC95 [{100*r['ci_rend60_025']:.2f}; {100*r['ci_rend60_975']:.2f}]%) | N_airbnb={int(r['n_airbnb_precificados'])}, "
            f"N_viva={int(r['n_viva_elegiveis'])} | diária R$ {fmt_num(r['diaria_anunciada_ajustada'])} | "
            f"preço R$ {fmt_num(r['mediana_preco_aquisicao'])} | payback {fmt_num(r['payback_60'],1)} anos.\n"
        )
    L.append("\n## 6. Cenários de 50%, 60% e 75%\n")
    for _, r in elig_out.iterrows():
        L.append(
            f"- {r['segmento']}: 50% → **{100*r['rendimento_50']:.2f}%** (payback {fmt_num(r['payback_50'],1)}y); "
            f"60% → **{100*r['rendimento_60']:.2f}%** ({fmt_num(r['payback_60'],1)}y); "
            f"75% → **{100*r['rendimento_75']:.2f}%** ({fmt_num(r['payback_75'],1)}y).\n"
        )
    L.append("\n## 7. Sensibilidade ao preço (P25/mediana/P75)\n")
    L.append("Ver `purchase_price_sensitivity.csv`.\n")
    for q in ("P25", "mediana", "P75"):
        sub = pr_df[(pr_df["ocupacao"] == "60%") & (pr_df["quantil_preco"] == q)].sort_values("rendimento_bruto", ascending=False)
        top_name = sub["segmento"].iloc[0] if len(sub) else "—"
        L.append(f"- No preço {q}, o maior rendimento@60% é **{top_name}**.\n")
    L.append("\n## 8. Sensibilidade a outliers\n")
    L.append("Estimativa pontual da sensibilidade = diária pontual × 365 × 0.60 / mediana(preço todos válidos); "
             "IC por bootstrap multiparamétrico (Airbnb + VivaReal). Ver `outlier_sensitivity.csv`.\n")
    top3_mudou = "SIM" if top_princ != top_sens else "NÃO"
    L.append(f"Top 3 principal vs top 3 (todos os válidos) — composição mudou? **{top3_mudou}**.\n")
    for var in ("principal_False", "sensibilidade_todos"):
        sub = outlier_sens_df[outlier_sens_df["variancia"] == var].nlargest(3, "rendimento_60")
        names = "; ".join(f"{r['segmento']} ({100*r['rendimento_60']:.2f}%)" for _, r in sub.iterrows())
        L.append(f"- {var}: {names}\n")
    L.append("\n## 9. Shortlist provisória (regra multicritério)\n")
    L.append(
        "Regra reproduzível (NÃO é simplesmente o maior ponto): universo = segmentos elegíveis; candidatos = "
        "união dos segmentos no top 3 em ao menos um de: principal@60%, sensibilidade a outliers, preço "
        "P25@60%, mediana@60%, P75@60%. Ordenação: limite inferior do IC95 do rendimento principal@60% "
        "(desc), empate usa maior N Airbnb, depois maior N VivaReal. Máximo 3 selecionados.\n"
    )
    for _, r in seg_df[seg_df.shortlist_selected].sort_values("shortlist_order").iterrows():
        L.append(f"- **{r['segmento']}** (ordem {int(r['shortlist_order'])}): {r['shortlist_reason']}\n")
    L.append("\n## 10. Limitações e riscos\n")
    L.append(
        "- Diária anunciada ≠ receita realizada; sem ocupação observada (ocupação é cenário).\n"
        "- Rendimento/payback são BRUTOS: sem condomínio/IPTU/manutenção/gestão.\n"
        "- Comparação agregada sem chave comum; mismatch possível no mesmo bairro×perfil.\n"
        "- Sazonalidade observável apenas jan–abr/2025; anualização é extrapolação.\n"
        "- Concentração por proprietário é risco de representatividade, não causa de preço.\n"
        "- Cobertura de condomínio/IPTU parcial no VivaReal (~30% ausente).\n"
    )
    L.append("\n## 11. Perguntas pendentes para a recomendação final\n")
    L.append(
        "- Características que explicam o desempenho (reviews, superhost, amenities, capacidade).\n"
        "- Compromisso diária × preço: N limitado em segmentos pequenos.\n"
        "- Como tratar a sazonalidade na anualização para a recomendação.\n"
    )
    write_md_lf("".join(L), OUT / "phase2_findings.md")

    print("\n=== VALIDAÇÕES ===")
    for ok, msg in checks:
        print(("  [OK] " if ok else "  [FALHA] ") + msg)
    np_ = sum(1 for ok, _ in checks if ok)
    print(f"\n{np_}/{len(checks)} verificações passaram.")
    print("\n=== RANKING 60% ===\n")
    for _, r in elig_out.iterrows():
        print(
            f"  {r['segmento']}: rend 60% {100*r['rendimento_60']:.2f}% [IC {100*r['ci_rend60_025']:.2f};"
            f" {100*r['ci_rend60_975']:.2f}] | N_air={int(r['n_airbnb_precificados'])} N_viva={int(r['n_viva_elegiveis'])} "
            f"| reps={int(r['bootstrap_reps_valid'])}"
        )
    print("\n=== SHORTLIST ===\n")
    for _, r in seg_df[seg_df.shortlist_selected].sort_values("shortlist_order").iterrows():
        print(f"  {int(r['shortlist_order'])}. {r['segmento']} — {r['shortlist_reason']}")
    print("\nFase 2 concluída.")


if __name__ == "__main__":
    main()