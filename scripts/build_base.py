"""
build_base.py — Construção das bases derivadas do Hackathon Seazone (Itapema).

Regras implementadas (validadas na etapa de diagnóstico):
  * Price: 1 preço por (airbnb_listing_id x stay_date); elegibilidade aq_date <= stay_date.
    Dois níveis: full (1.005) e analítico (999). 6 órfãos registrados.
  * Hosts: 1 linha por owner_id = snapshot MAIS RECENTE (host_snapshot_ts decrescente),
    desempate pela última aparição no arquivo (_ord = False). Auditoria compara com a
    regra antiga (snapshot mais antigo) e verifica selected_ts == max(ts).
  * VivaReal: dedupe por listing_id; ordenação (listing_id, _n_nulos, _ord) com
    ascending=[True, True, False] e keep='first' (última aparição no empate).
    Conflitos NA-aware em TODAS as colunas originais. Flags de duplicidade.
    Outliers de preço/m² por hierarquia: bairro x tipologia (N>=30) -> IQR próprio;
    10<=N<30 -> fallback tipologia Itapema; N<10 -> apenas reportar.
    Flag is_outlier_pm2 bool anulável; registros mantidos.
  * Cobertura: n_stay_dates_unicas / 105 (denominador da janela).
  * Comparação ajustada por data: monthly_equal_weight_adr() — mediana por grupo x
    stay_date; média das medianas diárias por grupo x mês; média dos quatro resultados
    mensais SOMENTE quando os 4 meses esperados (2025-01..2025-04) existirem; caso
    contrário retorna NA com insufficient_month_coverage=True.
  * Fluxo seguro: todas as verificações essenciais rodam ANTES da gravação; qualquer
    falha aborta sem escrever nada (nada de saídas parcialmente atualizadas).

O script falha (exit != 0) se alguma verificação essencial não passar.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PROCESSED = ROOT / "outputs" / "processed"
OUT_QUALITY = ROOT / "outputs" / "quality"

RAW_FILES = {
    "details": "Details_Itapema.csv",
    "hosts": "Hosts_ids_Itapema.csv",
    "mesh": "Mesh_Ids_Data_Itapema.csv",
    "price": "Price_AV_Itapema.csv",
    "vivareal": "VivaReal_Itapema.csv",
}

PRICE_LEVEL_FULL = 1005
PRICE_LEVEL_ANALYTIC = 999
IVIVAREAL_DEDUP = 8293
VIVAREAL_RAW = 8329
HOSTS_DEDUP = 3057
DETAILS_ROWS = 4441
EXPECTED_MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04"]

checks: list[tuple[bool, str]] = []


def check(condition: bool, message: str) -> None:
    checks.append((condition, message))
    if not condition:
        print(f"[FALHA] {message}")


def normalize_text(s: pd.Series) -> pd.Series:
    def _norm(x: object) -> str:
        if pd.isna(x):
            return "<NA>"
        return (
            unicodedata.normalize("NFKD", str(x))
            .encode("ascii", "ignore")
            .decode("ascii")
            .strip()
            .lower()
        )

    return s.map(_norm)


def write_csv_lf(df: pd.DataFrame, path: Path) -> None:
    """Grava CSV com quebras de linha LF, independente do SO."""
    with path.open("w", encoding="utf-8", newline="") as file:
        df.to_csv(file, index=False, lineterminator="\n")


def monthly_equal_weight_adr(
    df: pd.DataFrame, group_cols: list[str], listing_col: str = "listing_id"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Comparação ajustada por data, com média mensal igualmente ponderada.

    Sequência:
      1) mediana por grupo x stay_date;
      2) média das medianas diárias dentro de cada grupo x mês;
      3) média dos quatro resultados mensais (2025-01 a 2025-04) com peso igual,
         calculada SOMENTE se os 4 meses esperados estiverem presentes.

    Retorna (summary, detail):
      summary: grupo, months_present, n_months, monthly_equal_weight_adr,
               insufficient_month_coverage
      detail : grupo x mês com n_anuncios e n_dates presentes.
    """
    df = df[["stay_date", "price", listing_col, *group_cols]].copy()
    df["mes"] = df["stay_date"].dt.to_period("M").astype(str)

    daily = (
        df.groupby([*group_cols, "stay_date"])["price"]
        .median()
        .reset_index()
    )
    daily["mes"] = daily["stay_date"].dt.to_period("M").astype(str)

    monthly = (
        daily.groupby([*group_cols, "mes"])["price"]
        .mean()
        .reset_index()
    )

    detail = (
        df.groupby([*group_cols, "mes"])
        .agg(
            n_anuncios=(listing_col, "nunique"),
            n_dates=("stay_date", "nunique"),
        )
        .reset_index()
    )

    rows = []
    for key, grp in monthly.groupby(group_cols, dropna=False):
        key_t = key if isinstance(key, tuple) else (key,)
        grp_ = grp.set_index("mes")
        present = sorted(grp_["price"].index.astype(str).tolist())
        has_4 = (len(present) == 4) and all(m in present for m in EXPECTED_MONTHS)
        val = float(grp_["price"].mean()) if has_4 else np.nan
        rows.append(
            {
                **dict(zip(group_cols, key_t)),
                "months_present": "|".join(present),
                "n_months": len(present),
                "monthly_equal_weight_adr": val,
                "insufficient_month_coverage": not has_4,
            }
        )
    summary = pd.DataFrame(rows)
    return summary, detail


def main() -> None:
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_QUALITY.mkdir(parents=True, exist_ok=True)

    print("[1/5] Lendo arquivos brutos...")
    details_raw = pd.read_csv(DATA_DIR / RAW_FILES["details"], low_memory=False)
    hosts_raw = pd.read_csv(DATA_DIR / RAW_FILES["hosts"], low_memory=False)
    mesh_raw = pd.read_csv(DATA_DIR / RAW_FILES["mesh"], low_memory=False)
    price_raw = pd.read_csv(DATA_DIR / RAW_FILES["price"], low_memory=False)
    vivareal_raw = pd.read_csv(DATA_DIR / RAW_FILES["vivareal"], low_memory=False)

    check(
        len(details_raw) == DETAILS_ROWS,
        f"Details deve ter {DETAILS_ROWS} linhas (tem {len(details_raw)})",
    )
    check(
        len(vivareal_raw) == VIVAREAL_RAW,
        f"VivaReal bruto deve ter {VIVAREAL_RAW} linhas (tem {len(vivareal_raw)})",
    )
    check(
        details_raw["airbnb_listing_id"].is_unique,
        "Details: airbnb_listing_id deve ser único",
    )
    check(
        mesh_raw["airbnb_listing_id"].is_unique,
        "Mesh: airbnb_listing_id deve ser único",
    )

    # ==================================================================
    #  VIVAREAL — dedupe com linha integral + conflitos NA-aware + outliers
    # ==================================================================
    print("[2/5] VivaReal: dedupe, conflitos e outliers...")
    vv = vivareal_raw.copy()
    orig_cols_v = vv.columns.tolist()
    vv.insert(0, "_ord", range(len(vv)))
    vv["_n_nulos"] = vv.isna().sum(axis=1)

    dup_ids = vv.loc[vv.duplicated("listing_id", keep=False), "listing_id"].unique()
    conflict_mapping: dict[int, dict] = {}
    for lid, sub in vv[vv["listing_id"].isin(dup_ids)].groupby("listing_id"):
        conflicted = []
        for c in orig_cols_v:
            uniq = sub[c].map(lambda x: "<NA>" if pd.isna(x) else x).nunique()
            if uniq > 1:
                conflicted.append(c)
        conflict_mapping[lid] = {
            "cols": conflicted,
            "amen": "amenities" in conflicted,
            "n_dup_rows": int(sub.shape[0]),
        }

    v_dedup = (
        vv.sort_values(["listing_id", "_n_nulos", "_ord"], ascending=[True, True, False])
        .drop_duplicates("listing_id", keep="first")
        .sort_values("_ord")
        .reset_index(drop=True)
    )

    orig_rows = vv.iloc[v_dedup["_ord"].to_numpy()][orig_cols_v].reset_index(drop=True)
    na_same = (
        orig_rows[orig_cols_v].isna().to_numpy() == v_dedup[orig_cols_v].isna().to_numpy()
    )
    eq = (orig_rows[orig_cols_v].to_numpy() == v_dedup[orig_cols_v].to_numpy()) | na_same
    integral_rows = eq.all(axis=1)
    check(
        bool(integral_rows.all()),
        "VivaReal dedupe: todas as linhas finais devem existir integralmente no CSV original "
        f"({int((~integral_rows).sum())} divergentes)",
    )

    v_dedup["is_duplicate_listing_id"] = v_dedup["listing_id"].isin(dup_ids)
    v_dedup["dup_any_conflict"] = v_dedup["listing_id"].map(
        lambda x: bool(conflict_mapping.get(x, {}).get("cols"))
    )
    v_dedup["dup_conflict_columns"] = v_dedup["listing_id"].map(
        lambda x: ",".join(conflict_mapping.get(x, {}).get("cols", [])) or ""
    )
    v_dedup["dup_amenities_conflict"] = v_dedup["listing_id"].map(
        lambda x: bool(conflict_mapping.get(x, {}).get("amen"))
    )

    v_dedup["suburb_norm"] = normalize_text(v_dedup["suburb"])

    pm2 = pd.Series(np.nan, index=v_dedup.index, dtype="float64")
    valid_pm2 = (
        v_dedup["usable_area"].notna()
        & (v_dedup["usable_area"] > 0)
        & v_dedup["sale_price"].notna()
        & (v_dedup["sale_price"] > 0)
    )
    pm2.loc[valid_pm2] = (
        v_dedup.loc[valid_pm2, "sale_price"] / v_dedup.loc[valid_pm2, "usable_area"]
    )
    v_dedup["price_per_m2"] = pm2

    # Hierarquia de outliers (sem sobreposição)
    has_pm2 = v_dedup[v_dedup["price_per_m2"].notna()].copy()
    grp_key = has_pm2.groupby(["suburb_norm", "listing_type"])["price_per_m2"]
    grp_n = grp_key.size()
    grp_q1 = has_pm2.groupby(["suburb_norm", "listing_type"])["price_per_m2"].quantile(0.25)
    grp_q3 = has_pm2.groupby(["suburb_norm", "listing_type"])["price_per_m2"].quantile(0.75)

    tip_q1 = has_pm2.groupby("listing_type")["price_per_m2"].quantile(0.25)
    tip_q3 = has_pm2.groupby("listing_type")["price_per_m2"].quantile(0.75)

    mode_map: dict[tuple[str, str], tuple[str, float | None, float | None, int]] = {}
    for key in grp_n.index:
        n = int(grp_n[key])
        suburb_n, tip = key
        if n >= 30:
            q1, q3 = grp_q1[key], grp_q3[key]
            mode_map[key] = ("own_iqr", q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1), n)
        elif 10 <= n < 30:
            q1, q3 = tip_q1[tip], tip_q3[tip]
            mode_map[key] = ("fallback_tipologia", q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1), n)
        else:
            mode_map[key] = ("report_only", None, None, n)

    outlier_groups = pd.DataFrame(
        {
            "suburb_norm": [k[0] for k in mode_map],
            "listing_type": [k[1] for k in mode_map],
            "n": [v[3] for v in mode_map.values()],
            "mode": [v[0] for v in mode_map.values()],
            "lim_inf": [v[1] for v in mode_map.values()],
            "lim_sup": [v[2] for v in mode_map.values()],
        }
    )

    subgroup_key = list(zip(v_dedup["suburb_norm"], v_dedup["listing_type"]))
    key_lookup = {i: k for i, k in zip(range(len(v_dedup)), subgroup_key)}
    v_dedup["_om"] = [mode_map.get(key_lookup[i], ("report_only", None, None, 0))[0] for i in range(len(v_dedup))]
    v_dedup["_ol_inf"] = [mode_map.get(key_lookup[i], ("", None, None, 0))[1] for i in range(len(v_dedup))]
    v_dedup["_ol_sup"] = [mode_map.get(key_lookup[i], ("", None, None, 0))[2] for i in range(len(v_dedup))]

    box = (
        v_dedup["_om"].isin(["own_iqr", "fallback_tipologia"])
        & v_dedup["price_per_m2"].notna()
        & (
            (v_dedup["price_per_m2"] < v_dedup["_ol_inf"])
            | (v_dedup["price_per_m2"] > v_dedup["_ol_sup"])
        )
    )
    flag_outlier: list[object] = []
    for i in range(len(v_dedup)):
        if v_dedup["_om"].iloc[i] in ("own_iqr", "fallback_tipologia"):
            flag_outlier.append(bool(box.iloc[i]))
        else:
            flag_outlier.append(pd.NA)
    v_dedup["is_outlier_pm2"] = pd.array(flag_outlier, dtype="boolean")
    v_dedup = v_dedup.drop(columns=["_om", "_ol_inf", "_ol_sup"])

    check(
        len(v_dedup) == IVIVAREAL_DEDUP,
        f"VivaReal dedupe deve ter {IVIVAREAL_DEDUP} linhas (tem {len(v_dedup)})",
    )
    check(
        v_dedup["listing_id"].is_unique,
        "VivaReal dedupe: listing_id deve ser único",
    )
    check(
        str(v_dedup["is_outlier_pm2"].dtype) == "boolean",
        "VivaReal: is_outlier_pm2 deve ser booleano anulável (boolean)",
    )

    # ==================================================================
    #  HOSTS — dedupe por owner (snapshot MAIS RECENTE) + auditoria
    # ==================================================================
    print("[3/5] Hosts: dedupe por owner_id...")
    hh = hosts_raw.copy()
    hh["_ord"] = range(len(hh))
    hh["host_snapshot_ts"] = pd.to_datetime(hh["host_snapshot_date"], errors="coerce")

    dup_owners = set(hh.loc[hh.duplicated("owner_id", keep=False), "owner_id"])

    new_sel = (
        hh.sort_values(["owner_id", "host_snapshot_ts", "_ord"], ascending=[True, False, False])
        .drop_duplicates("owner_id", keep="first")
        .sort_values("_ord")
        .reset_index(drop=True)
    )
    old_sel = (
        hh.sort_values(["owner_id", "host_snapshot_ts", "_ord"], ascending=[True, True, False])
        .drop_duplicates("owner_id", keep="first")
    )

    max_ts = hh.groupby("owner_id")["host_snapshot_ts"].max()
    attr_cols = [
        c for c in hh.columns if c not in ("owner_id", "host_snapshot_date", "_ord", "host_snapshot_ts")
    ]

    new_by = new_sel.set_index("owner_id")
    old_by = old_sel.set_index("owner_id")
    audit_rows = []
    n_line_changed = 0
    for oid in new_by.index:
        new_ord = new_by.loc[oid, "_ord"]
        old_ord = old_by.loc[oid, "_ord"]
        line_changed = new_ord != old_ord
        if line_changed:
            n_line_changed += 1
        attrs_changed = []
        if line_changed:
            for c in attr_cols:
                if not (pd.isna(new_by.loc[oid, c]) and pd.isna(old_by.loc[oid, c])):
                    if new_by.loc[oid, c] != old_by.loc[oid, c]:
                        attrs_changed.append(c)
        audit_rows.append(
            {
                "owner_id": oid,
                "n_rows": int(hh["owner_id"].eq(oid).sum()),
                "max_snapshot_ts": max_ts[oid],
                "selected_new_ts": new_by.loc[oid, "host_snapshot_ts"],
                "selected_old_ts": old_by.loc[oid, "host_snapshot_ts"],
                "line_changed": bool(line_changed),
                "attrs_changed_columns": ",".join(attrs_changed),
            }
        )
    hosts_audit = pd.DataFrame(audit_rows)

    h_dedup = new_sel.copy()
    h_dedup["is_duplicate_owner"] = h_dedup["owner_id"].isin(dup_owners)

    check(
        len(h_dedup) == HOSTS_DEDUP,
        f"Hosts dedupe deve ter {HOSTS_DEDUP} owners (tem {len(h_dedup)})",
    )
    check(h_dedup["owner_id"].is_unique, "Hosts dedupe: owner_id deve ser único")
    check(
        bool((hosts_audit["selected_new_ts"] == hosts_audit["max_snapshot_ts"]).all()),
        "Hosts auditoria: para cada owner, selected_new_ts deve == max(host_snapshot_ts)",
    )
    any_attrs = hosts_audit["attrs_changed_columns"].fillna("").ne("")
    check(
        len(h_dedup) == len(hosts_audit),
        "Hosts auditoria: 1 linha de auditoria por owner",
    )

    print(
        f"  [auditoria] owners com linha escolhida alterada vs regra antiga: {n_line_changed} "
        f"({100*n_line_changed/len(h_dedup):.2f}%) | com atributos além do ts alterados: {int(any_attrs.sum())}"
    )

    # ==================================================================
    #  PRICE — dedupe com elegibilidade (regra metodológica completa)
    # ==================================================================
    print("[4/5] Price: dedupe por (listing x stay_date)...")
    pp = price_raw.copy()
    pp["aq_ts"] = pd.to_datetime(pp["aquisition_date"], errors="coerce")
    pp["aq_date"] = pp["aq_ts"].dt.normalize()
    pp["stay_date"] = pd.to_datetime(pp["date"], errors="coerce").dt.normalize()

    check(pp["aq_ts"].notna().all(), "Price: todas as aquisition_date devem ser válidas")
    check(pp["stay_date"].notna().all(), "Price: todas as dates de estadia devem ser válidas")

    eleg = pp[pp["aq_date"] <= pp["stay_date"]].copy()

    price_dedup_full = (
        eleg.loc[eleg.groupby(["airbnb_listing_id", "stay_date"])["aq_ts"].idxmax()]
        .sort_values(["airbnb_listing_id", "stay_date"])
        .reset_index(drop=True)
    )
    n_capturas = eleg.groupby(["airbnb_listing_id", "stay_date"]).size().reset_index(name="n_capturas")
    price_dedup_full = price_dedup_full.merge(n_capturas, on=["airbnb_listing_id", "stay_date"], how="left")
    price_dedup_full = (
        price_dedup_full.drop_duplicates(["airbnb_listing_id", "stay_date"])
        .sort_values(["airbnb_listing_id", "stay_date"])
        .reset_index(drop=True)
    )

    check(
        len(price_dedup_full) == 59040,
        f"Price dedup full deve ter 59040 pares (tem {len(price_dedup_full)})",
    )
    check(
        (price_dedup_full["aq_date"] <= price_dedup_full["stay_date"]).all(),
        "Price dedup full: regra de elegibilidade aq_date <= stay_date deve valer para todos",
    )
    check(
        not price_dedup_full.duplicated(["airbnb_listing_id", "stay_date"]).any(),
        "Price dedup full: sem duplicatas (listing, stay_date)",
    )

    details_ids = set(details_raw["airbnb_listing_id"])
    full_ids = set(price_dedup_full["airbnb_listing_id"])
    orphans = sorted(full_ids - details_ids)
    check(len(orphans) == 6, f"Price: deve haver 6 órfãos (tem {len(orphans)})")

    orphan_lines = price_raw[price_raw["airbnb_listing_id"].isin(orphans)]
    check(
        len(orphan_lines) == 509,
        f"Órfãos devem somar 509 linhas brutas (têm {len(orphan_lines)})",
    )

    price_analytic = price_dedup_full[price_dedup_full["airbnb_listing_id"].isin(details_ids)].copy()
    price_analytic = price_analytic.sort_values(["airbnb_listing_id", "stay_date"]).reset_index(drop=True)

    check(
        price_analytic["airbnb_listing_id"].nunique() == PRICE_LEVEL_ANALYTIC,
        f"Price analítico deve ter {PRICE_LEVEL_ANALYTIC} anúncios (tem {price_analytic['airbnb_listing_id'].nunique()})",
    )
    check(
        set(price_analytic["airbnb_listing_id"]) <= details_ids,
        "Price analítico: todos os ids devem existir no Details",
    )
    check(
        not price_analytic.duplicated(["airbnb_listing_id", "stay_date"]).any(),
        "Price analítico: sem duplicatas (listing, stay_date)",
    )

    ndays_window = price_dedup_full["stay_date"].nunique()
    check(ndays_window == 105, f"Janela deve ter 105 datas únicas (tem {ndays_window})")

    # ==================================================================
    #  COBERTURA (denominador = 105)
    # ==================================================================
    cov_full = (
        price_dedup_full.groupby("airbnb_listing_id")["stay_date"]
        .nunique()
        .reset_index(name="n_dates")
    )
    cov_full["coverage"] = cov_full["n_dates"] / ndays_window

    cov_anal = (
        price_analytic.groupby("airbnb_listing_id")["stay_date"]
        .nunique()
        .reset_index(name="n_dates")
    )
    cov_anal["coverage"] = cov_anal["n_dates"] / ndays_window

    check(
        abs(cov_full["coverage"].max() - 1.0) < 1e-9,
        "Cobertura full: deve existir anúncio com 100%",
    )

    # ==================================================================
    #  LISTING MASTER (Details + Mesh + Hosts)
    # ==================================================================
    print("[5/5] Listing master (Details + Mesh + Hosts)...")
    mesh_cols = ["airbnb_listing_id", "latitude", "longitude", "suburb"]
    base = details_raw.merge(
        mesh_raw[mesh_cols], on="airbnb_listing_id", how="left", suffixes=("_details", "_mesh")
    )
    hosts_cols = [c for c in h_dedup.columns if c not in ("_ord", "host_snapshot_date")]
    base = base.merge(h_dedup[hosts_cols], on="owner_id", how="left", suffixes=("", "_host"))

    base["in_price_full"] = base["airbnb_listing_id"].isin(full_ids)
    base["in_price_analytic"] = base["airbnb_listing_id"].isin(set(price_analytic["airbnb_listing_id"]))

    check(len(base) == DETAILS_ROWS, f"Listing master deve ter {DETAILS_ROWS} linhas")
    check(base["airbnb_listing_id"].is_unique, "Listing master: id único")
    check(base["suburb"].notna().all(), "Listing master: Mesh/suburb deve cobrir todos")
    check(
        base["is_superhost"].notna().sum() == DETAILS_ROWS if "is_superhost" in base.columns else False,
        "Listing master: Hosts deve cobrir todos os owners",
    )

    # ==================================================================
    #  SMOKE TEST — monthly_equal_weight_adr
    # ==================================================================
    smoke = price_analytic.rename(columns={"airbnb_listing_id": "listing_id"}).merge(
        details_raw[["airbnb_listing_id", "listing_type"]],
        left_on="listing_id",
        right_on="airbnb_listing_id",
        how="left",
    )
    summary_smoke, detail_smoke = monthly_equal_weight_adr(smoke, ["listing_type"])

    check(
        {"listing_type", "months_present", "n_months", "monthly_equal_weight_adr",
         "insufficient_month_coverage"} <= set(summary_smoke.columns),
        "monthly_equal_weight_adr: summary com schema esperado",
    )
    check(
        set(detail_smoke.columns) == {"listing_type", "mes", "n_anuncios", "n_dates"},
        "monthly_equal_weight_adr: detail com schema esperado",
    )
    check(
        bool(summary_smoke["monthly_equal_weight_adr"].notna().any()),
        "Smoke: deve haver grupo com 4 meses gerando monthly_equal_weight_adr",
    )

    # grupo artificial com 3 meses -> NA + flag
    art = smoke[["listing_id", "stay_date", "price"]].copy()
    one = art["listing_id"].iloc[0]
    art["grp"] = np.where(art["listing_id"] == one, "g_3m", "g_real")
    art = art[~((art["grp"] == "g_3m") & (art["stay_date"].dt.month == 4))]
    summary_art, _ = monthly_equal_weight_adr(art, ["grp"])
    g3 = summary_art[summary_art["grp"] == "g_3m"].iloc[0]
    gr = summary_art[summary_art["grp"] == "g_real"].iloc[0]
    check(
        pd.isna(g3["monthly_equal_weight_adr"]) and bool(g3["insufficient_month_coverage"]),
        "Smoke: grupo com 3 meses deve retornar NA + insufficient_month_coverage=True",
    )
    check(
        pd.notna(gr["monthly_equal_weight_adr"]) and not bool(gr["insufficient_month_coverage"]),
        "Smoke: grupo com 4 meses deve retornar valor e flag False",
    )

    # ==================================================================
    #  GATE FINAL — nenhuma gravação se algo falhar
    # ==================================================================
    failed = [m for ok, m in checks if not ok]
    if failed:
        print("\n=== VERIFICAÇÕES COM FALHA — abortando SEM gravar saídas ===")
        for m in failed:
            print("  [FALHA] " + m)
        sys.exit(1)

    # ==================================================================
    #  SAÍDAS (só executadas após TODAS as verificações passarem)
    # ==================================================================
    listing_master_out = (
        base.drop(columns=["latitude_details", "longitude_details"])
        .rename(columns={"latitude_mesh": "latitude", "longitude_mesh": "longitude"})
    )
    v_dedup_out = v_dedup.drop(columns=["_ord", "_n_nulos"])

    write_csv_lf(listing_master_out, OUT_PROCESSED / "listing_master.csv")
    write_csv_lf(price_dedup_full, OUT_PROCESSED / "price_dedup_full.csv")
    write_csv_lf(price_analytic, OUT_PROCESSED / "price_analytic.csv")
    write_csv_lf(v_dedup_out, OUT_PROCESSED / "vivareal_dedup.csv")
    write_csv_lf(h_dedup.drop(columns=["_ord"]), OUT_PROCESSED / "hosts_dedup.csv")

    # ---- auditorias / qualidade ----
    orphan_report = orphan_lines.groupby("airbnb_listing_id").agg(
        n_raw_lines=("price", "size"),
        first_stay=("date", "min"),
        last_stay=("date", "max"),
    ).reset_index()
    write_csv_lf(orphan_report, OUT_QUALITY / "orphans_price.csv")

    write_csv_lf(cov_full, OUT_QUALITY / "coverage_full.csv")
    write_csv_lf(cov_anal, OUT_QUALITY / "coverage_analytic.csv")

    conflicts_report = pd.DataFrame(
        [
            {
                "listing_id": lid,
                "is_duplicate": True,
                "n_dup_rows": info.get("n_dup_rows", 0),
                "dup_any_conflict": bool(info["cols"]),
                "dup_conflict_columns": ",".join(info["cols"]),
                "dup_amenities_conflict": bool(info["amen"]),
            }
            for lid, info in conflict_mapping.items()
        ]
    )
    write_csv_lf(conflicts_report, OUT_QUALITY / "vivareal_conflicts.csv")
    write_csv_lf(outlier_groups, OUT_QUALITY / "vivareal_outlier_groups.csv")
    write_csv_lf(hosts_audit, OUT_QUALITY / "hosts_snapshot_audit.csv")

    pairs_same_day = (
        price_dedup_full[price_dedup_full["aq_date"] == price_dedup_full["stay_date"]]
        .groupby(["airbnb_listing_id", "stay_date"])
        .size()
        .reset_index()
    )
    elig_audit = pd.DataFrame(
        [
            {"metrica": "linhas brutas Price", "valor": len(price_raw)},
            {"metrica": "linhas elegíveis (aq_date <= stay_date)", "valor": len(eleg)},
            {"metrica": "linhas excluídas por elegibilidade", "valor": len(price_raw) - len(eleg)},
            {"metrica": "pares (listing, stay_date) no full", "valor": len(price_dedup_full)},
            {"metrica": "anúncios no full", "valor": len(full_ids)},
            {"metrica": "anúncios no analítico (com Details)", "valor": len(details_ids & full_ids)},
            {"metrica": "pares cuja captura eleita é no próprio dia da estadia (elegíveis por convenção)", "valor": len(pairs_same_day)},
            {"metrica": "janela (n dias únicos)", "valor": ndays_window},
            {"metrica": "órfãos (sem Details)", "valor": len(orphans)},
            {"metrica": "linhas brutas dos órfãos", "valor": len(orphan_lines)},
        ]
    )
    write_csv_lf(elig_audit, OUT_QUALITY / "eligibility_audit.csv")

    summary_counts = pd.DataFrame(
        [
            {"dataset": "details_raw", "rows": len(details_raw), "key": "airbnb_listing_id", "key_nunique": details_raw["airbnb_listing_id"].nunique()},
            {"dataset": "mesh_raw", "rows": len(mesh_raw), "key": "airbnb_listing_id", "key_nunique": mesh_raw["airbnb_listing_id"].nunique()},
            {"dataset": "hosts_raw", "rows": len(hosts_raw), "key": "owner_id", "key_nunique": hosts_raw["owner_id"].nunique()},
            {"dataset": "hosts_dedup", "rows": len(h_dedup), "key": "owner_id", "key_nunique": h_dedup["owner_id"].nunique()},
            {"dataset": "price_raw", "rows": len(price_raw), "key": "airbnb_listing_id+date", "key_nunique": price_raw.groupby(["airbnb_listing_id", "date"]).ngroups},
            {"dataset": "price_dedup_full", "rows": len(price_dedup_full), "key": "airbnb_listing_id+stay_date", "key_nunique": price_dedup_full.groupby(["airbnb_listing_id", "stay_date"]).ngroups},
            {"dataset": "price_analytic", "rows": len(price_analytic), "key": "airbnb_listing_id+stay_date", "key_nunique": price_analytic.groupby(["airbnb_listing_id", "stay_date"]).ngroups},
            {"dataset": "vivareal_raw", "rows": len(vivareal_raw), "key": "listing_id", "key_nunique": vivareal_raw["listing_id"].nunique()},
            {"dataset": "vivareal_dedup", "rows": len(v_dedup), "key": "listing_id", "key_nunique": v_dedup["listing_id"].nunique()},
            {"dataset": "listing_master", "rows": len(base), "key": "airbnb_listing_id", "key_nunique": base["airbnb_listing_id"].nunique()},
        ]
    )
    write_csv_lf(summary_counts, OUT_QUALITY / "summary_counts.csv")

    with open(OUT_QUALITY / "quality_report.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("# Resumo de qualidade e auditoria\n\n")
        f.write(f"Janela de análise: {ndays_window} datas únicas de estadia (06/jan a 20/abr/2025).\n\n")
        f.write("## Níveis do Price\n")
        f.write(f"- Price deduplicado completo: **{len(full_ids)} anúncios**, **{len(price_dedup_full)} pares**.\n")
        f.write(f"- Price analítico (associado ao Details): **{price_analytic['airbnb_listing_id'].nunique()} anúncios**, **{len(price_analytic)} pares**.\n")
        f.write(f"- Órfãos (sem Details): **{len(orphans)} ids**, **{len(orphan_lines)} linhas brutas** — registrados em `orphans_price.csv`, **excluídos** das análises.\n\n")
        f.write("## Cobertura (denominador = 105)\n")
        f.write(f"- Full (1.005): mediana {cov_full['coverage'].median():.2f}; min {cov_full['coverage'].min():.2f}; p25 {cov_full['coverage'].quantile(.25):.2f}; p75 {cov_full['coverage'].quantile(.75):.2f}; max {cov_full['coverage'].max():.2f}\n")
        f.write(f"- Analítico (999): mediana {cov_anal['coverage'].median():.2f}; min {cov_anal['coverage'].min():.2f}; p25 {cov_anal['coverage'].quantile(.25):.2f}; p75 {cov_anal['coverage'].quantile(.75):.2f}; max {cov_anal['coverage'].max():.2f}\n")
        f.write("Datas ausentes não são interpretadas como preço zero, reserva ou indisponibilidade.\n\n")
        f.write("## VivaReal\n")
        f.write(f"- Dedupe: {VIVAREAL_RAW} -> {len(v_dedup)} linhas; todos confirmados como linhas integrais do original.\n")
        n_conf = int(conflicts_report["dup_any_conflict"].sum()) if len(conflicts_report) else 0
        f.write(f"- IDs duplicados: {len(conflict_mapping)}; com qualquer conflito: {n_conf}.\n")
        g_no = outlier_groups[outlier_groups["mode"] == "report_only"]
        f.write(f"- Outlier-pm2: own_iqr em {int((outlier_groups['mode']=='own_iqr').sum())} grupos; fallback tipologia em {int((outlier_groups['mode']=='fallback_tipologia').sum())}; report_only em {int((outlier_groups['mode']=='report_only').sum())} grupos ({len(g_no)} com N<10).\n\n")
        f.write("## Hosts\n")
        f.write(f"- Dedupe por owner: {len(h_dedup)} owners, snapshot mais recente. Auditoria em `hosts_snapshot_audit.csv`; "
                f"linhas alteradas vs regra antiga (snapshot mais antigo): {n_line_changed}; "
                f"atributos (além de ts) alterados: {int(any_attrs.sum())}.\n\n")
        f.write("## Regra de elegibilidade do Price\n")
        f.write("- `aq_ts`: timestamp completo, usado para ordenar; `aq_date`: data, usada na elegibilidade.\n")
        f.write("- Elegibilidade: `aq_date <= stay_date`. Captura no mesmo dia da estadia é elegível por convenção (ver `eligibility_audit.csv`).\n")

    print("\n=== VERIFICAÇÕES ===")
    passed = sum(1 for ok, _ in checks if ok)
    for ok, msg in checks:
        print(("  [OK] " if ok else "  [FALHA] ") + msg)
    print(f"\n{passed}/{len(checks)} verificações passaram.")

    print("\n=== SMOKE TEST — ponderação mensal (resumo real por listing_type) ===")
    print(summary_smoke[["listing_type", "months_present", "n_months", "monthly_equal_weight_adr", "insufficient_month_coverage"]].to_string(index=False))
    print("\n=== SMOKE TEST — grupo artificial ===\n" + summary_art.to_string(index=False))

    print("\nConstrução concluída.")


if __name__ == "__main__":
    main()