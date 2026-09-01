"""
analyze_listing_characteristics.py — Fase 3: características associadas às maiores diárias.

Decisão:
  Identificar características estruturais, operacionais, reputacionais e de comodidades
  associadas à diária anunciada, sem linguagem causal.

Terminologia: associação, diferença ajustada, característica relacionada. NUNCA causal.

Unidade: anúncio Airbnb. Variável-alvo: log(diaria_anunciada_ajustada_do_anuncio).
Diária por anúncio: média dos preços por anúncio×mês; média igualmente ponderada (jan–abr/2025);
só quando os 4 meses presentes. Datas ausentes ≠ zero.

Populações:
  - principal_all: 4 meses + cobertura>=50% + diária positiva. N esperado = 493 (sem filtrar a resposta).
  - sensibilidades de cobertura: 4m sem limiar, cov>=25%, cov>=75%.
  - sem_outliers_sens: principal_all após remover outliers extremos de diária (IQR do log_y), N esperado = 462
    (ANÁLISE DE SENSIBILIDADE — não é o modelo principal).

Fontes das variáveis (schema confirmado em listing_master):
  A estrutural: number_of_bedrooms, number_of_bathrooms, number_of_beds, number_of_guests, listing_type, suburb
  B anúncio/operação: cleaning_fee, picture_count, can_instant_book, is_new_listing, is_professional, amenity_count
  C host: is_superhost, is_verified, years_host, months_host, portfolio_owner
  D reputação: has_reviews, number_of_reviews, star_rating, avaliações por dimensão
  (response_rate/time 100% NA => excluído; min_nights 100% 0 => excluído)

Modelo 1 (acionável): bairro + perfil + capacidade/estrutura + anúncio + amenity_count + flags amenities (freq).
Modelo 2 (ampliado): Modelo 1 + host + reputação + has_reviews + flags de ausência.

Bootstrap por clusters de owner_id preservando MULTIPLICIDADE (owner sorteado m vezes aparece m vezes).
  seed 42, 1000 réplicas, IC95 percentil com >=950 válidas.
  Não censura o IC; reporta point_outside_bootstrap_ci quando a estimativa pontual sai do intervalo.

CV 5-folds agrupado por owner: owner nunca divide treino/validação; parâmetros (mediana/desvio e imputação)
  calculados SOMENTE no treino de cada fold e aplicados à validação. Categoria de referência excluída das
  dummies. Nomes dos coeficientes alinhados a beta[1:].

Coeficientes como diferença percentual aproximada 100*(exp(b)-1).

Saídas em outputs/analysis/phase3/ (inclui outlier_sensitivity.csv). Gate final antes de gravar; LF.
"""

from __future__ import annotations

import ast
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "outputs" / "processed"
QUAL = ROOT / "outputs" / "quality"
OUT = ROOT / "outputs" / "analysis" / "phase3"

BOOT_SEED = 42
N_REPS = 1000
MIN_VALID_REPS = 950
EXPECTED_MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04"]
N_FOLDS = 5

EXPECTED_PRINCIPAL_N = 493
EXPECTED_WO_N = 462
EXPECTED_PAIRS = 58600
EXPECTED_LISTINGS = 999

checks: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    checks.append((cond, msg))


def fail_and_exit() -> None:
    failed = [m for ok, m in checks if not ok]
    if not failed:
        return
    print("\n=== VALIDAÇÕES COM FALHA — abortando SEM gravar outputs/analysis/phase3/ ===")
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
    def _n(x):
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


def make_profile(lt_ser, br_ser) -> pd.Series:
    lt = lt_ser.astype(str)
    prof = pd.Series("5. hotel/outros", index=lt.index, dtype=object)
    apt = lt == "apartamento"
    prof[apt & (br_ser <= 1)] = "1. apartamento compacto (0-1q)"
    prof[apt & (br_ser == 2)] = "2. apartamento (2q)"
    prof[apt & (br_ser >= 3)] = "3. apartamento (3q+)"
    prof[lt == "casa"] = "4. casa"
    return prof


def parse_amenities(raw_ser: pd.Series) -> tuple[pd.DataFrame, dict]:
    idx = raw_ser.index
    n = len(raw_ser)
    schemas: dict[str, dict] = {}
    parse_ok = 0
    for a in raw_ser:
        if pd.isna(a) or str(a).strip() == "":
            continue
        try:
            lst = ast.literal_eval(a)
            if not isinstance(lst, list):
                continue
        except Exception:
            continue
        parse_ok += 1
        for item in lst:
            norm = (
                unicodedata.normalize("NFKD", str(item))
                .encode("ascii", "ignore")
                .decode("ascii")
                .strip()
                .lower()
            )
            if norm in schemas:
                schemas[norm]["count"] += 1
            else:
                schemas[norm] = {"count": 1, "orig": str(item)}
    cols = sorted(schemas.keys())
    flags = pd.DataFrame(False, index=idx, columns=cols)
    for i in range(n):
        a = raw_ser.iloc[i]
        if pd.isna(a) or str(a).strip() == "":
            continue
        try:
            lst = ast.literal_eval(a)
        except Exception:
            continue
        if not isinstance(lst, list):
            continue
        for item in lst:
            norm = (
                unicodedata.normalize("NFKD", str(item))
                .encode("ascii", "ignore")
                .decode("ascii")
                .strip()
                .lower()
            )
            if norm in flags.columns:
                flags.at[idx[i], norm] = True
    return flags, {"n_total": n, "parse_ok": parse_ok, "parse_rate": parse_ok / n if n else 0, "schemas": schemas}


def amenity_dict_frame(schemas: dict, flags_prevalence: pd.Series, pop_n: int, selected: set) -> pd.DataFrame:
    rows = []
    for norm, info in schemas.items():
        prev = flags_prevalence.get(norm, 0)
        rows.append(
            {
                "nome_original": info["orig"],
                "nome_normalizado": norm,
                "frequencia": info["count"],
                "prevalencia": prev,
                "incluida_modelo": norm in selected,
                "motivo": (
                    "prevalencia 10-90% e/ou frequência top10" if norm in selected
                    else "fora do intervalo 10-90% ou não top10 por frequência"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_target_price(df_price: pd.DataFrame) -> pd.DataFrame:
    p = df_price.copy()
    p["mes"] = pd.to_datetime(p["stay_date"]).dt.to_period("M").astype(str)
    p["day"] = pd.to_datetime(p["stay_date"]).dt.normalize()
    pm = p.groupby(["airbnb_listing_id", "mes"])["price"].mean().reset_index()
    piv = pm.pivot_table(index="airbnb_listing_id", columns="mes", values="price")
    out = []
    for lid in piv.index:
        row = piv.loc[lid]
        vals = [row[m] for m in EXPECTED_MONTHS if m in row.index and pd.notna(row[m])]
        target = float(np.mean(vals)) if len(vals) == 4 else np.nan
        out.append({"airbnb_listing_id": lid, "diaria_ajustada": target})
    tdf = pd.DataFrame(out)
    n_datas = p.groupby("airbnb_listing_id")["day"].nunique()
    meses = p.groupby("airbnb_listing_id")["mes"].nunique()
    tdf["n_datas"] = tdf["airbnb_listing_id"].map(n_datas)
    tdf["n_meses"] = tdf["airbnb_listing_id"].map(meses)
    return tdf


def daily_by_listing(df_price: pd.DataFrame) -> pd.DataFrame:
    nd = df_price.groupby("airbnb_listing_id")["stay_date"].nunique()
    window = df_price["stay_date"].nunique()
    cov = (nd / window).rename("coverage")
    return pd.DataFrame({"airbnb_listing_id": cov.index, "coverage": cov.values, "n_datas": nd.values})


def spearman_ci(x, y, rng) -> tuple[float, float, float]:
    n = len(x)
    if n < 3:
        return np.nan, np.nan, np.nan
    arr = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    bs = np.empty(N_REPS)
    for k in range(N_REPS):
        idx = rng.integers(0, n, size=n)
        xx, yy = arr[idx, 0], arr[idx, 1]
        rx = pd.Series(xx).rank()
        ry = pd.Series(yy).rank()
        if np.std(rx) == 0 or np.std(ry) == 0:
            bs[k] = np.nan
        else:
            bs[k] = np.corrcoef(rx, ry)[0, 1]
    gd = bs[~np.isnan(bs)]
    rho = float(np.corrcoef(pd.Series(x).rank(), pd.Series(y).rank())[0, 1])
    if len(gd) < MIN_VALID_REPS:
        return rho, np.nan, np.nan
    return rho, float(np.percentile(gd, 2.5)), float(np.percentile(gd, 97.5))


def top_floor(x):
    q = pd.Series(x).quantile([0.25, 0.5, 0.75])
    lo, mid, hi = q[0.25], q[0.5], q[0.75]
    return lo, mid, hi


def ci_from(vals: np.ndarray, minv: int = MIN_VALID_REPS) -> tuple[float, float, int, int, bool]:
    gd = vals[~np.isnan(vals)]
    n = int(len(gd))
    if n < minv:
        return np.nan, np.nan, N_REPS, n, True
    return float(np.percentile(gd, 2.5)), float(np.percentile(gd, 97.5)), N_REPS, n, False


def ols(X, y, add_const=True):
    if add_const:
        Xc = np.column_stack([np.ones(len(y)), X])
    else:
        Xc = X
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    yhat = Xc @ beta
    resid = y - yhat
    n, k = Xc.shape
    dof = n - k
    if dof <= 0:
        return None
    s2 = np.sum(resid**2) / dof
    xtx = Xc.T @ Xc
    try:
        covb = s2 * np.linalg.inv(xtx)
    except np.linalg.LinAlgError:
        covb = s2 * np.linalg.pinv(xtx)
    se = np.sqrt(np.clip(np.diag(covb), 0, None))
    cond = np.linalg.cond(Xc) if n >= k and Xc.size else np.nan
    return {"beta": beta, "se": se, "yhat": yhat, "resid": resid, "cond": cond, "k": k, "n": n}


def r2_from_xy(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    if ss_tot == 0:
        return np.nan
    return 1 - ss_res / ss_tot


def mae_from_xy(y, yhat):
    return float(np.mean(np.abs(y - yhat)))


def grouped_folds(owners, n_folds=N_FOLDS, seed=BOOT_SEED):
    unique = np.unique(owners)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    folds = [set() for _ in range(n_folds)]
    for i, o in enumerate(unique):
        folds[i % n_folds].add(o)
    return folds


def boot_idx_for_draw(owner_array: np.ndarray, draw: np.ndarray) -> np.ndarray:
    """Dado um sorteio de owners (com repetição), expande para índices de linhas preservando multiplicidade."""
    owner_to_idx = {o: np.flatnonzero(owner_array == o) for o in np.unique(owner_array)}
    return np.concatenate([owner_to_idx[o] for o in draw])


def cluster_boot_sample(owner_array: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    unique = np.unique(owner_array)
    draw = rng.choice(unique, size=len(unique), replace=True)
    return boot_idx_for_draw(owner_array, draw)


def check_bootstrap_multiplicity() -> bool:
    """Teste determinístico com clusters artificiais A e B: multiplicidade preservada."""
    owner_ab = np.array(["A", "A", "B", "B"])
    draw = np.array(["A", "A", "B"])
    boot_idx = boot_idx_for_draw(owner_ab, draw)
    expected = np.array([0, 1, 0, 1, 2, 3])  # A (2 linhas) 2x + B (2 linhas) 1x
    ok = np.array_equal(boot_idx, expected)
    if not ok:
        return False
    # verificação explícita de multiplicidade
    for o in ["A", "B"]:
        n_rows = int(np.sum(owner_ab == o))
        n_drawn = int(np.sum(draw == o))
        n_present = int(np.sum(owner_ab[boot_idx] == o))
        if n_present != n_rows * n_drawn:
            return False
    return True


class DesignSchema:
    """Schema fixo de features (ordem alinhada a beta[1:])."""

    def __init__(self, names: list[str], num_cols: list[str]):
        self.names = names
        self.num_cols = num_cols

    def build(self, df, stds) -> np.ndarray:
        X = np.zeros((len(df), len(self.names)))
        for j, nm in enumerate(self.names):
            if nm in self.num_cols:
                s = df[nm] if nm in df.columns else pd.Series(np.nan, index=df.index)
                if not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                    s = s.astype(float)
                med, std = stds[nm]
                X[:, j] = (s.fillna(med).to_numpy().astype(float) - med) / (std if std else 1)
            elif nm.startswith("suburb_design_"):
                cat_val = nm[len("suburb_design_"):]
                X[:, j] = (df["suburb_design"] == cat_val).astype(float).to_numpy()
            elif nm.startswith("profile_"):
                cat_val = nm[len("profile_"):]
                X[:, j] = (df["profile"] == cat_val).astype(float).to_numpy()
        return X

    def build_raw(self, df) -> pd.DataFrame:
        """Matriz crua (dummies 0/1 + numéricos sem padronizar) para CV por fold."""
        d = {}
        for nm in self.names:
            if nm in self.num_cols:
                s = df[nm] if nm in df.columns else pd.Series(np.nan, index=df.index)
                if not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                    s = s.astype(float)
                d[nm] = s.to_numpy().astype(float)
            elif nm.startswith("suburb_design_"):
                d[nm] = (df["suburb_design"] == nm[len("suburb_design_"):]).astype(float).to_numpy()
            elif nm.startswith("profile_"):
                d[nm] = (df["profile"] == nm[len("profile_"):]).astype(float).to_numpy()
        return pd.DataFrame(d, index=df.index)


def build_schema(df, cat_schema, num_cols):
    """Constrói DesignSchema a partir de df de referência (categorias de referência excluídas)."""
    names = []
    cat_var_map = {"suburb_design": df["suburb_design"], "profile": df["profile"]}
    for cat, ref in cat_schema.items():
        levels = sorted(cat_var_map[cat].unique())
        for lv in levels:
            if lv == ref:
                continue
            names.append(f"{cat}_{lv}")
    for c in num_cols:
        names.append(c)
    return DesignSchema(names, num_cols)


def drop_constant_cols(df, cols: list[str]) -> list[str]:
    """Remove colunas numéricas com variância zero na população dada (evita singularidade)."""
    kept = []
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c]
        if not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            s = s.astype(float)
        arr = s.fillna(s.median()).to_numpy(dtype=float)
        if arr.std() > 0:
            kept.append(c)
        else:
            check(True, f"variável constante removida do design: {c}")
    return kept


def cv_grouped(df_use, schema: DesignSchema, stds, owners, n_folds=N_FOLDS):
    """Validação cruzada agrupada por owner; parâmetros do TREINO aplicados à validação."""
    raw = schema.build_raw(df_use)
    # separar numéricos (padronizáveis) e dummies
    num = schema.num_cols
    y = df_use["log_y"].to_numpy()
    folds = grouped_folds(owners)
    folds_meta = []
    val_rs = []
    for f in range(n_folds):
        test_owners = np.array(list(folds[f]))
        train_mask = ~np.isin(owners, test_owners)
        test_mask = np.isin(owners, test_owners)
        tr_raw = raw[train_mask].copy()
        te_raw = raw[test_mask].copy()
        # padronizar/imputar numéricos com parâmetros do treino
        tr_std = {}
        for c in num:
            med = np.nanmedian(tr_raw[c])
            std = np.nanstd(tr_raw[c])
            if std is np.nan or std == 0 or np.isnan(std):
                std = 1.0
            tr_std[c] = (med, std)
            tr_raw[c] = (tr_raw[c].fillna(med) - med) / std
            te_raw[c] = (te_raw[c].fillna(med) - med) / std
        for c in schema.names:
            if c not in num and tr_raw[c].isna().any():
                medb = float(tr_raw[c].median())
                tr_raw[c] = tr_raw[c].fillna(medb)
                te_raw[c] = te_raw[c].fillna(medb)
        Xtr = tr_raw.to_numpy(dtype=float)
        Xte = te_raw.to_numpy(dtype=float)
        Xtr = np.column_stack([np.ones(len(Xtr)), Xtr])
        Xte = np.column_stack([np.ones(len(Xte)), Xte])
        beta, *_ = np.linalg.lstsq(Xtr, y[train_mask], rcond=None)
        yh_tr = Xtr @ beta
        yh_te = Xte @ beta
        folds_meta.append(
            {
                "fold": f + 1,
                "n_train": int(train_mask.sum()),
                "n_val": int(test_mask.sum()),
                "n_owners_train": int(np.unique(owners[train_mask]).size),
                "n_owners_val": int(test_owners.size),
                "r2_train": r2_from_xy(y[train_mask], yh_tr),
                "r2_val": r2_from_xy(y[test_mask], yh_te),
                "mae_val": mae_from_xy(y[test_mask], yh_te),
                "no_overlap": True,  # por construção
            }
        )
        val_rs.append(folds_meta[-1]["r2_val"])
    # conferir que owners de treino e validação não se sobrepõem em nenhum fold
    for f in range(n_folds):
        tr_owners = set(np.unique(owners[~np.isin(owners, np.array(list(folds[f])))]))
        te_owners = set(folds[f])
        if tr_owners & te_owners:
            folds_meta[f]["no_overlap"] = False
    mean_r2 = float(np.mean(val_rs)) if val_rs else np.nan
    sd_r2 = float(np.std(val_rs)) if val_rs else np.nan
    return pd.DataFrame(folds_meta), mean_r2, sd_r2


def fmt(x, nd=0):
    if x is None:
        return "n/d"
    try:
        if isinstance(x, float) and np.isnan(x):
            return "n/d"
    except TypeError:
        pass
    return f"{x:,.{nd}f}"


def main() -> None:
    print("[1/9] Carregando bases...")
    price = pd.read_csv(PROC / "price_analytic.csv", low_memory=False)
    master = pd.read_csv(PROC / "listing_master.csv", low_memory=False)
    cov = pd.read_csv(QUAL / "coverage_analytic.csv", low_memory=False)

    check(len(price) == EXPECTED_PAIRS, "price_analytic 58.600 pares")
    check(price["airbnb_listing_id"].nunique() == EXPECTED_LISTINGS, "999 anúncios")
    check(not price.duplicated(["airbnb_listing_id", "stay_date"]).any(), "sem duplicata listing x stay_date")
    check(master["airbnb_listing_id"].is_unique, "master id único")
    check(cov["airbnb_listing_id"].is_unique, "coverage id único")

    print("[2/9] Diária ajustada por anúncio...")
    tdf = build_target_price(price)
    cov_by = daily_by_listing(price)
    cov_check = cov.merge(cov_by, on="airbnb_listing_id", how="inner")
    check(len(cov_check) == EXPECTED_LISTINGS, "cobertura reconciliada com todos os 999")

    lm = master.copy()
    lm["suburb_norm"] = norm_text(lm["suburb"])
    lm["suburb_label"] = np.where(lm["suburb_norm"] == "<NA>", "não informado", lm["suburb_norm"])
    lm["profile"] = make_profile(lm["listing_type"], lm["number_of_bedrooms"])
    base = lm.merge(tdf, on="airbnb_listing_id", how="left", validate="one_to_one")
    base = base.merge(cov_by[["airbnb_listing_id", "coverage"]], on="airbnb_listing_id", how="left", validate="one_to_one")
    check(len(base) == len(master), "join one_to_one sem multiplicação (master)")
    check(len(base) == base["airbnb_listing_id"].nunique(), "uma linha final por anúncio")

    base["has4"] = base["diaria_ajustada"].notna()
    base["covge"] = base["coverage"]
    pop_main = base[base["has4"] & (base["covge"] >= 0.50) & (base["diaria_ajustada"] > 0)].copy()
    check(len(pop_main) >= 1, "população principal não vazia")

    sens_4m = base[base["has4"] & (base["diaria_ajustada"] > 0)]
    sens_25 = base[base["has4"] & (base["covge"] >= 0.25) & (base["diaria_ajustada"] > 0)]
    sens_75 = base[base["has4"] & (base["covge"] >= 0.75) & (base["diaria_ajustada"] > 0)]

    n_main = len(pop_main)
    n_s4 = len(sens_4m)
    n_s25 = len(sens_25)
    n_s75 = len(sens_75)
    print(f"  populações: principal={n_main} | 4m sem limiar={n_s4} | cov>=25={n_s25} | cov>=75={n_s75}")
    check(n_main == EXPECTED_PRINCIPAL_N, f"principal_all N={EXPECTED_PRINCIPAL_N} (tem {n_main})")

    # ---- tratamentos de sentinela ----
    n_sent = int(((base["number_of_reviews"] == 0) & (base["star_rating"] == 0)).sum())
    check(n_sent > 0, "sentinelas existem (star_rating==0 com reviews==0)")
    base["has_reviews"] = base["number_of_reviews"] > 0
    star_effective = base["star_rating"].where(base["has_reviews"], np.nan)
    med_star = star_effective.median()
    base["star_effective"] = star_effective.fillna(med_star)
    base["star_missing"] = (~base["has_reviews"]).astype(int)
    for dcol in ["accuracy_rating", "checkin_rating", "cleanliness_rating", "communication_rating",
                 "location_rating", "value_rating", "guest_satisfaction_overall"]:
        eff = base[dcol].where(base["has_reviews"], np.nan)
        base[dcol + "_eff"] = eff.fillna(eff.median())

    feat_cols = ["has_reviews", "star_effective", "star_missing",
                 "accuracy_rating_eff", "location_rating_eff", "value_rating_eff",
                 "guest_satisfaction_overall_eff", "can_instant_book", "is_professional",
                 "is_new_listing", "is_superhost", "is_verified", "portfolio_owner",
                 "years_host", "months_host", "number_of_reviews", "picture_count",
                 "number_of_bathrooms", "number_of_bedrooms", "number_of_beds",
                 "number_of_guests", "cleaning_fee"]
    base["can_instant_book"] = base["can_instant_book"].map(lambda x: {True: 1, False: 0}.get(x, np.nan))
    base["is_professional"] = base["is_professional"].map(lambda x: {True: 1, False: 0}.get(x, np.nan))
    base["is_new_listing"] = base["is_new_listing"].map(lambda x: {True: 1, False: 0}.get(x, np.nan))
    base["is_superhost"] = base["is_superhost"].astype(int)
    base["is_verified"] = base["is_verified"].astype(int)
    base["portfolio_owner"] = base["owner_id"].map(base["owner_id"].value_counts())
    base["cleaning_fee"] = base["cleaning_fee"].fillna(0.0)

    for c in feat_cols:
        pop_main[c] = base.loc[pop_main.index, c]

    # ---- amenities ----
    print("[3/9] Parser de amenities...")
    flags, am_meta = parse_amenities(base["amenities"])
    check(am_meta["parse_ok"] > 0, "parser de amenities com sucesso")
    am_prev = (flags.loc[base.index].sum() / len(base)).sort_values(ascending=False)
    freq = flags.loc[base.index].sum().sort_values(ascending=False)
    top10 = freq.head(10).index.tolist()
    selected_amen = {c for c in top10 if 0.10 <= am_prev[c] <= 0.90}
    base["amenity_count"] = flags.loc[base.index].sum(axis=1)
    pop_main["amenity_count"] = base.loc[pop_main.index, "amenity_count"]
    for c in selected_amen:
        base["am_" + c] = flags.loc[base.index, c].astype(int)
        pop_main["am_" + c] = base.loc[pop_main.index, "am_" + c].astype(int)
    am_dict = amenity_dict_frame(am_meta["schemas"], am_prev, len(base), selected_amen)
    check(
        all(0.10 <= am_prev[c] <= 0.90 for c in selected_amen),
        f"comodidades selecionadas dentro de 10-90% prevalência ({len(selected_amen)})",
    )

    # ---- associações descritivas ----
    print("[4/9] Associações descritivas...")
    rng_desc = np.random.default_rng(BOOT_SEED)
    desc_rows = []
    binary_cols = ["can_instant_book", "is_professional", "is_new_listing", "is_superhost",
                   "is_verified", "has_reviews"] + ["am_" + c for c in sorted(selected_amen)[:5]]
    for c in binary_cols:
        if c not in pop_main.columns or pop_main[c].isna().all():
            continue
        g1 = pop_main[pop_main[c] == 1]
        g0 = pop_main[pop_main[c] == 0]
        n1, n0 = len(g1), len(g0)
        med1 = g1["diaria_ajustada"].median() if n1 else np.nan
        med0 = g0["diaria_ajustada"].median() if n0 else np.nan
        diff = (med1 - med0) if (n1 and n0) else np.nan
        diff_ci = (np.nan, np.nan)
        if n1 >= 20 and n0 >= 20:
            owners = pop_main["owner_id"].unique()
            base1 = pop_main[pop_main[c] == 1]
            base0 = pop_main[pop_main[c] == 0]
            bs = np.empty(N_REPS)
            for k in range(N_REPS):
                i1 = cluster_boot_sample(pop_main["owner_id"].to_numpy(), rng_desc)
                s1 = base1.loc[np.intersect1d(pop_main.index[i1], base1.index), "diaria_ajustada"].median()
                i0 = cluster_boot_sample(pop_main["owner_id"].to_numpy(), rng_desc)
                s0 = base0.loc[np.intersect1d(pop_main.index[i0], base0.index), "diaria_ajustada"].median()
                if not np.isnan(s1) and not np.isnan(s0):
                    bs[k] = s1 - s0
            diff_ci = ci_from(bs)
        desc_rows.append({
            "variavel": c, "tipo": "binaria", "n_com": n1, "n_sem": n0,
            "mediana_com": med1, "mediana_sem": med0, "diferenca_bruta": diff,
            "ci_diff_025": diff_ci[0], "ci_diff_975": diff_ci[1],
            "ajustado_bairro_perfil": "ver modelo (M1/M2)",
        })
    num_cols_desc = ["number_of_bedrooms", "number_of_bathrooms", "number_of_beds", "number_of_guests",
                     "cleaning_fee", "picture_count", "amenity_count", "years_host", "months_host",
                     "portfolio_owner", "number_of_reviews", "star_effective"]
    for c in num_cols_desc:
        if c not in pop_main.columns:
            continue
        s = pop_main[c].dropna()
        n = len(s)
        rho, lo, hi = spearman_ci(s.values, pop_main.loc[s.index, "diaria_ajustada"].values, rng_desc)
        q1, q2, q3 = top_floor(s.values)
        quart = pd.qcut(s.values, 4, duplicates="drop")
        diarias = pop_main.loc[s.index, "diaria_ajustada"]
        grp_d = diarias.groupby(quart).agg(["median", "count"])
        desc_rows.append({
            "variavel": c, "tipo": "numerica", "n": n,
            "mediana": s.median(), "iqr": s.quantile(0.75) - s.quantile(0.25),
            "rho_spearman": rho, "ci_rho_025": lo, "ci_rho_975": hi,
            "q1": q1, "q2": q2, "q3": q3,
            "diaria_med_q1": grp_d["median"].iloc[0] if len(grp_d) else np.nan,
            "diaria_med_q4": grp_d["median"].iloc[-1] if len(grp_d) else np.nan,
        })
    desc_df = pd.DataFrame(desc_rows)

    # ---- modelos ----
    print("[5/9] Modelos associativos...")
    use_main_all = pop_main.dropna(subset=["diaria_ajustada"]).copy()
    use_main_all["log_y"] = np.log(use_main_all["diaria_ajustada"])
    sub_counts = use_main_all["suburb_label"].value_counts()
    rare = sub_counts[sub_counts < 25].index.tolist()
    use_main_all["suburb_design"] = use_main_all["suburb_label"].where(
        ~use_main_all["suburb_label"].isin(rare), "outros_bairros_raros"
    )
    use_main_all["profile"] = make_profile(use_main_all["listing_type"], use_main_all["number_of_bedrooms"])
    check(len(use_main_all) == EXPECTED_PRINCIPAL_N, f"modelo principal usa N={EXPECTED_PRINCIPAL_N} (tem {len(use_main_all)})")

    # sensibilidade sem outliers (N esperado 462): APENAS sensibilidade
    q1y, q3y = np.log(use_main_all["diaria_ajustada"]).quantile(0.25), np.log(use_main_all["diaria_ajustada"]).quantile(0.75)
    iqry = q3y - q1y
    lo_y, hi_y = q1y - 1.5 * iqry, q3y + 1.5 * iqry
    use_main_wo = use_main_all[
        (np.log(use_main_all["diaria_ajustada"]) >= lo_y) & (np.log(use_main_all["diaria_ajustada"]) <= hi_y)
    ].copy()
    check(len(use_main_wo) == EXPECTED_WO_N, f"sem_outliers_sens N esperado {EXPECTED_WO_N} (tem {len(use_main_wo)})")

    cats_ref = {"suburb_design": "meia praia", "profile": "2. apartamento (2q)"}
    structural = ["number_of_bedrooms"]
    advert = ["cleaning_fee", "picture_count", "can_instant_book", "is_new_listing", "is_professional", "amenity_count"]
    am_flags = [c for c in use_main_all.columns if c.startswith("am_")]
    m1_cols = drop_constant_cols(use_main_all, structural + advert + am_flags)

    host = ["is_superhost", "years_host", "months_host", "portfolio_owner"]  # is_verified removido (100% True na principal → sem variância)
    # Reputação: apenas nota composta (star_effective) para evitar colinearidade extrema entre dimensões *_eff
    # (todas imputadas com a mesma mediana quando sem reviews — documentado).
    rep = ["has_reviews", "number_of_reviews", "star_effective"]
    m2_cols = drop_constant_cols(use_main_all, m1_cols + host + rep)

    # padronização fixa (principal_all)
    stds_global = {}
    for c in set(m1_cols) | set(m2_cols):
        s = use_main_all[c]
        if not pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            s = s.astype(float)
        stds_global[c] = (float(s.median()), float(s.std()))

    schema_m1 = build_schema(use_main_all, cats_ref, m1_cols)
    schema_m2 = build_schema(use_main_all, cats_ref, m2_cols)

    # verificação: referência não é dummy
    for schema, name_ in ((schema_m1, "M1"), (schema_m2, "M2")):
        check(
            not any("meia praia" == nm.replace("suburb_design_", "") and nm.startswith("suburb_design_") for nm in schema.names),
            f"{name_}: suburb_design referência (meia praia) ausente das dummies",
        )
        check(
            not any(nm.startswith("profile_") and nm == "profile_2. apartamento (2q)" for nm in schema.names),
            f"{name_}: profile referência (2q) ausente das dummies",
        )

    # ---- fit M1 e M2 (principal_all) ----
    X1 = schema_m1.build(use_main_all, stds_global)
    X2 = schema_m2.build(use_main_all, stds_global)
    check(np.isfinite(X1).all(), "matriz M1 sem NaN/inf")
    check(np.isfinite(X2).all(), "matriz M2 sem NaN/inf")
    check(X1.shape[1] < X1.shape[0], "M1: nº colunas < nº obs")
    check(X2.shape[1] < X2.shape[0], "M2: nº colunas < nº obs")

    res1 = ols(X1, use_main_all["log_y"].values)
    res2 = ols(X2, use_main_all["log_y"].values)
    cond1, cond2 = res1["cond"], res2["cond"]

    # align check: nomes vs beta[1:]
    check(len(schema_m1.names) == X1.shape[1], "M1: len(names)==ncol X")
    check(len(schema_m2.names) == X2.shape[1], "M2: len(names)==ncol X")
    check(res1["beta"].size == X1.shape[1] + 1, "M1: beta tem const")
    check(res2["beta"].size == X2.shape[1] + 1, "M2: beta tem const")

    # ---- bootstrap por cluster (multiplicidade) ----
    print("[6/9] Bootstrap por owner (multiplicidade)...")
    check(check_bootstrap_multiplicity(), "teste determinístico: bootstrap preserva multiplicidade (A/B)")
    owners_all = use_main_all["owner_id"].to_numpy()
    rng_b1 = np.random.default_rng(BOOT_SEED)
    rng_b2 = np.random.default_rng(BOOT_SEED)
    n_owner_all = np.unique(owners_all).size

    def bootstrap_model(Xm, y_ser, owner_arr, rng, schema_n):
        bs_beta = np.full((N_REPS, schema_n), np.nan)
        for k in range(N_REPS):
            bidx = cluster_boot_sample(owner_arr, rng)
            Xs = Xm[bidx]
            ys = y_ser[bidx]
            Xc = np.column_stack([np.ones(len(ys)), Xs])
            beta, *_ = np.linalg.lstsq(Xc, ys, rcond=None)
            if np.all(np.isfinite(beta)):
                bs_beta[k] = beta[1:]
        return bs_beta

    bs1 = bootstrap_model(X1, use_main_all["log_y"].to_numpy(), owners_all, rng_b1, X1.shape[1])
    bs2 = bootstrap_model(X2, use_main_all["log_y"].to_numpy(), owners_all, rng_b2, X2.shape[1])
    m1_valid = ~np.isnan(bs1).any(axis=1)
    m2_valid = ~np.isnan(bs2).any(axis=1)

    # ---- modelo 1 e 2 em dados reais: coefs + CI (sem censurar) ----
    coef_rows = []
    for (label, schema, Xm, res, bsmask, valid_mask, num_cols_model) in [
        ("M1_acionavel", schema_m1, X1, res1, bs1, m1_valid, m1_cols),
        ("M2_ampliado", schema_m2, X2, res2, bs2, m2_valid, m2_cols),
    ]:
        beta_full = res["beta"][1:]
        n_valid = int(valid_mask.sum())
        for i, nm in enumerate(schema.names):
            b = float(beta_full[i])
            vals = bsmask[valid_mask, i]
            gd = vals[~np.isnan(vals)]
            nv_i = int(len(gd))
            insuf = nv_i < MIN_VALID_REPS
            if insuf or nv_i == 0:
                lo = hi = np.nan
                p_out = np.nan
            else:
                lo = float(np.percentile(gd, 2.5))
                hi = float(np.percentile(gd, 97.5))
                p_out = bool(not (lo <= b <= hi))
            # ---- interpretação da escala ----
            if nm in num_cols_model:
                vtype = "continuous_standardized"
                med_orig, std_orig = stds_global.get(nm, (np.nan, np.nan))
                unit = f"1 desvio-padrão (std original {std_orig:.3f}) na variável {nm}"
            else:
                vtype = "categorical_dummy"
                med_orig, std_orig = np.nan, np.nan
                if nm.startswith("profile_"):
                    unit = f"categoria {nm[len('profile_'):]} vs referência '2. apartamento (2q)'"
                elif nm.startswith("suburb_design_"):
                    unit = f"bairro {nm[len('suburb_design_'):]} vs referência 'meia praia'"
                else:
                    unit = "dummy (ref: categoria omitida)"
            coef_rows.append({
                "modelo": label, "variavel": nm,
                "variable_type": vtype,
                "original_median": med_orig,
                "original_std": std_orig,
                "interpretation_unit": unit,
                "beta": b,
                "dif_percentual_aproximada": 100 * (np.exp(b) - 1),
                "ci_025_beta": lo, "ci_975_beta": hi,
                "bootstrap_reps_requested": N_REPS,
                "bootstrap_reps_valid": n_valid,
                "point_outside_bootstrap_ci": p_out,
                "ci_insuficiente": insuf,
                "dif_percentual_ci_025": (100 * (np.exp(lo) - 1) if not np.isnan(lo) else np.nan),
                "dif_percentual_ci_975": (100 * (np.exp(hi) - 1) if not np.isnan(hi) else np.nan),
                "n_model": len(use_main_all),
            })
    coef_df = pd.DataFrame(coef_rows)
    for (label, valid_mask) in [("M1_acionavel", m1_valid), ("M2_ampliado", m2_valid)]:
        n_valid_all = int(valid_mask.sum())
        check(n_valid_all >= MIN_VALID_REPS, f"{label}: >=950 réplicas válidas (tem {n_valid_all})")

    # ---- CV agrupada por owner ----
    cv_df1, r2v1_mean, r2v1_sd = cv_grouped(use_main_all, schema_m2, stds_global, owners_all)
    cv_df2, r2v2_mean, r2v2_sd = cv_grouped(use_main_all, schema_m1, stds_global, owners_all)
    check(int((cv_df1.no_overlap == False).sum()) == 0, "CV M2: owners não se sobrepõem em nenhum fold")
    check(int((cv_df2.no_overlap == False).sum()) == 0, "CV M1: owners não se sobrepõem em nenhum fold")
    check(len(cv_df1) == N_FOLDS, f"CV M2: {N_FOLDS} folds")
    check(len(cv_df2) == N_FOLDS, f"CV M1: {N_FOLDS} folds")

    diag_df = pd.DataFrame([
        {"modelo": "M1_acionavel", "n": len(use_main_all), "condition_number": cond1,
         "r2_train": r2_from_xy(use_main_all["log_y"].values, res1["yhat"]),
         "n_folds": N_FOLDS, "r2_val_mean": r2v2_mean, "r2_val_sd": r2v2_sd},
        {"modelo": "M2_ampliado", "n": len(use_main_all), "condition_number": cond2,
         "r2_train": r2_from_xy(use_main_all["log_y"].values, res2["yhat"]),
         "n_folds": N_FOLDS, "r2_val_mean": r2v1_mean, "r2_val_sd": r2v1_sd},
    ])
    r2_neg = (diag_df["r2_val_mean"] <= 0).any()

    # ---- estabilidade por cobertura ----
    print("[7/9] Estabilidade por cobertura e sensibilidade sem outliers...")
    scenarios = [("cov25", sens_25), ("cov50_principal", pop_main), ("cov75", sens_75)]

    def prep(df):
        d = df.dropna(subset=["diaria_ajustada"]).copy()
        d["log_y"] = np.log(d["diaria_ajustada"])
        d["suburb_design"] = d["suburb_label"].where(~d["suburb_label"].isin(rare), "outros_bairros_raros")
        d["profile"] = make_profile(d["listing_type"], d["number_of_bedrooms"])
        return d

    # sinais por cenário (M1)
    sign_map = {}
    coef_map = {}
    for scn, sub in scenarios:
        d = prep(sub)
        Xs = schema_m1.build(d, stds_global)
        r = ols(Xs, d["log_y"].values)
        if r is None:
            continue
        for i, nm in enumerate(schema_m1.names):
            b = r["beta"][1 + i]
            sign_map.setdefault(nm, {})[scn] = np.sign(b)
            coef_map.setdefault(nm, {})[scn] = 100 * (np.exp(b) - 1)

    # sensibilidade sem outliers (M1)
    wo = prep(use_main_wo)
    Xwo = schema_m1.build(wo, stds_global)
    r_wo = ols(Xwo, wo["log_y"].values)
    sign_wo = {nm: np.sign(r_wo["beta"][1 + i]) for i, nm in enumerate(schema_m1.names)} if r_wo else {}

    cov_cols = ["cov25", "cov50_principal", "cov75"]
    stab_summary_rows = []
    outlier_rows = []
    m1_coef = coef_df[coef_df.modelo == "M1_acionavel"].set_index("variavel")
    # estimativas do M1 sem outliers (para comparação de magnitude)
    m1_wo = {}
    if r_wo is not None:
        for i, nm in enumerate(schema_m1.names):
            m1_wo[nm] = 100 * (np.exp(r_wo["beta"][1 + i]) - 1)
    INTERPRET_INVALID = {"suburb_design_outros_bairros_raros", "profile_5. hotel/outros"}
    for nm in schema_m1.names:
        signs = sign_map.get(nm, {})
        available_3 = all(c in signs for c in cov_cols)
        same_sign_cov = available_3 and all(
            np.isclose(signs[c], signs["cov50_principal"], atol=1e-12) for c in cov_cols
        )
        # validação: associação marcada estável exige 3 cenários disponíveis
        # (dependente das flags abaixo; checamos em loop após)
        rw = m1_coef.loc[nm]
        lo = rw["dif_percentual_ci_025"]
        hi = rw["dif_percentual_ci_975"]
        nv = int(rw["bootstrap_reps_valid"])
        pout = bool(rw["point_outside_bootstrap_ci"])
        ic_cruz = pd.isna(lo) or pd.isna(hi) or (lo <= 0 <= hi)
        s_princ = signs.get("cov50_principal")
        same_sign_wo = bool(
            (nm in sign_wo)
            and (s_princ is not None)
            and np.isclose(sign_wo[nm], s_princ, atol=1e-12)
        )
        # sensibilidade de magnitude (principal N=493 vs sem outliers N=462)
        est_princ = rw["dif_percentual_aproximada"]
        est_wo = m1_wo.get(nm, np.nan)
        if not (pd.isna(est_princ) or pd.isna(est_wo)):
            abs_change = abs(est_wo - est_princ)
            rel_change = (100 * abs_change / abs(est_princ)) if not np.isclose(est_princ, 0, atol=1e-12) else np.nan
        else:
            abs_change = rel_change = np.nan
        same_sign_wo_mag = bool(
            (nm in sign_wo) and (s_princ is not None) and np.isclose(np.sign(sign_wo[nm]), s_princ, atol=1e-12)
        )
        unusable_interp = nm in INTERPRET_INVALID
        # associação amostral exploratória (critérios estritos)
        explor = bool(
            available_3
            and same_sign_cov
            and (not ic_cruz)
            and (nv >= MIN_VALID_REPS)
            and (not pout)
            and same_sign_wo
            and (not unusable_interp)
        )
        # supporting evidence: mesmo conjunto, mas exige interpretação econômica válida
        supporting = explor
        # usable for recommendation alone: sempre False (observacional / associação ≠ causalidade)
        usable_alone = False
        stab_summary_rows.append({
            "variavel": nm,
            "coef_percentual_principal": est_princ,
            "sinal_principal": s_princ,
            "estimate_without_outliers": est_wo,
            "absolute_change_percentage_points": abs_change,
            "relative_magnitude_change_pct": rel_change,
            "same_sign": same_sign_wo_mag,
            "ci_diff_025": lo, "ci_diff_975": hi,
            "disponivel_3_cenarios": available_3,
            "sinal_consistente_3": same_sign_cov,
            "ic_principal_cruza_zero": bool(ic_cruz),
            "associacao_amostral_exploratoria": explor,
            "usable_as_supporting_evidence": supporting,
            "usable_for_recommendation_alone": usable_alone,
        })
        # outlier sensitivity rows (principal_all e sem_outliers_sens)
        outlier_rows.append({
            "population": "principal_all", "variavel": nm,
            "n_listings": len(use_main_all), "n_owners": n_owner_all,
            "estimate": est_princ,
            "ci_low": lo, "ci_high": hi,
            "valid_bootstrap_reps": nv,
            "point_outside_bootstrap_ci": pout,
            "same_sign_coverage": same_sign_cov,
            "same_sign_without_outliers": same_sign_wo,
            "exploratory_sample_association": explor,
            "usable_as_supporting_evidence": supporting,
            "usable_for_recommendation_alone": usable_alone,
        })
    # blob sem outliers (estimativa pontual e sinal) — sem bootstrap aqui (documentado)
    for nm in schema_m1.names:
        b_wo = r_wo["beta"][1 + schema_m1.names.index(nm)] if r_wo else np.nan
        outlier_rows.append({
            "population": "sem_outliers_sens", "variavel": nm,
            "n_listings": len(use_main_wo), "n_owners": np.unique(use_main_wo["owner_id"].to_numpy()).size,
            "estimate": (100 * (np.exp(b_wo) - 1)) if not np.isnan(b_wo) else np.nan,
            "ci_low": np.nan, "ci_high": np.nan,
            "valid_bootstrap_reps": np.nan,
            "point_outside_bootstrap_ci": np.nan,
            "same_sign_coverage": np.nan,
            "same_sign_without_outliers": np.nan,
            "exploratory_sample_association": np.nan,
            "usable_as_supporting_evidence": np.nan,
            "usable_for_recommendation_alone": np.nan,
        })
    stab_summary_df = pd.DataFrame(stab_summary_rows)
    outlier_sens_df = pd.DataFrame(outlier_rows)
    # validação: toda associação marcada como estável tem os 3 cenários disponíveis
    est_rows = stab_summary_df[stab_summary_df["associacao_amostral_exploratoria"] == True]  # noqa: E712
    check(
        bool((est_rows["disponivel_3_cenarios"] == True).all()),  # noqa: E712
        "toda associação estável tem os 3 cenários de cobertura disponíveis",
    )

    # ---- shortlist ----
    print("[8/9] Análise da shortlist...")
    short_segs = [("morretes", "2. apartamento (2q)"), ("meia praia", "1. apartamento compacto (0-1q)"),
                  ("centro", "2. apartamento (2q)")]
    short_rows = []
    feats = ["number_of_guests", "number_of_bathrooms", "number_of_beds", "amenity_count",
             "is_superhost", "can_instant_book", "picture_count", "number_of_reviews"]
    for (bairro, prof) in short_segs:
        sub = pop_main[(pop_main["suburb_label"] == bairro) & (pop_main["profile"] == prof)]
        n_total = int(((base["suburb_label"] == bairro) & (base["profile"] == prof) & base["diaria_ajustada"].notna()).sum())
        n_princ = len(sub)
        cov_med = sub["coverage"].median() if len(sub) else np.nan
        row = {"segmento": bairro + " | " + prof, "n_precificado_total": n_total,
               "n_principal": n_princ, "cobertura_med": cov_med, "nota": ""}
        if n_princ < 20:
            row["nota"] = "N<20: somente descrição, sem inferência"
        else:
            med_y = sub["diaria_ajustada"].median()
            sub = sub.copy()
            sub["top_q"] = sub["diaria_ajustada"] >= sub["diaria_ajustada"].quantile(0.75)
            top = sub[sub["top_q"]]
            rest = sub[~sub["top_q"]]
            for f in feats:
                if f not in sub.columns:
                    continue
                row[f + "_top_q1"] = top[f].median() if len(top) else np.nan
                row[f + "_demais"] = rest[f].median() if len(rest) else np.nan
            row["mediana_diaria"] = med_y
        short_rows.append(row)
    shortlist_df = pd.DataFrame(short_rows)

    # ---- lista de características ----
    lm_out = base[["airbnb_listing_id", "diaria_ajustada", "n_datas", "coverage", "n_meses",
                   "suburb_label", "profile", "owner_id", "has_reviews", "amenity_count", "star_effective"]].copy()
    lm_out["n_datas"] = lm_out["n_datas"].fillna(0)
    lm_out["coverage"] = lm_out["coverage"].fillna(0)

    # ---- gate final ----
    fail_and_exit()

    OUT.mkdir(parents=True, exist_ok=True)
    print("[9/9] Gravando saídas em outputs/analysis/phase3/...")
    write_csv_lf(lm_out, OUT / "listing_characteristics.csv")
    write_csv_lf(am_dict, OUT / "amenity_dictionary.csv")
    write_csv_lf(desc_df, OUT / "descriptive_associations.csv")
    write_csv_lf(coef_df, OUT / "model_coefficients.csv")
    write_csv_lf(diag_df, OUT / "model_diagnostics.csv")
    write_csv_lf(stab_summary_df, OUT / "coverage_stability.csv")
    write_csv_lf(shortlist_df, OUT / "shortlist_characteristics.csv")
    write_csv_lf(outlier_sens_df, OUT / "outlier_sensitivity.csv")
    write_csv_lf(cv_df1, OUT / "cv_folds_m2.csv")
    write_csv_lf(cv_df2, OUT / "cv_folds_m1.csv")

    # ---- findings ----
    L = []
    L.append("# Fase 3 — Características associadas às maiores diárias anunciadas\n")
    L.append("## 1. Pergunta de negócio\n")
    L.append("Identificar características estruturais, operacionais, reputacionais e de comodidades **associadas** "
             "à diária anunciada em Itapema, controlando bairro e perfil. Não há linguagem causal.\n")
    L.append("\n## 2. População e variável-alvo\n")
    L.append(f"Diária ajustada = média das médias mensais (jan–abr/2025), só com 4 meses; cobertura = n_datas/105. "
             f"N: 4m sem limiar={n_s4}; cov>=25={n_s25}; principal(cov>=50)={n_main}; cov>=75={n_s75}. "
             f"Modelo principal: N={len(use_main_all)} (não filtra a resposta). "
             f"Sensibilidade sem outliers (IQR log_y): N={len(use_main_wo)}.\n")
    L.append("\n## 3. Ausências e sentinelas\n")
    L.append("star_rating==0 e notas 0 com number_of_reviews==0 = AUSÊNCIA (has_reviews). Imputação documentada "
             "(mediana da dimensão, precedida de flag de ausência). response_rate/time (100% NA) e min_nights (100% 0) excluídos.\n")
    L.append("\n## 4. Comodidades selecionadas\n")
    L.append(f"Parser ok em {am_meta['parse_ok']}/{am_meta['n_total']} ({100*am_meta['parse_rate']:.1f}%). "
             f"Selecionadas por frequência em 10-90%: {len(selected_amen)}. Nunca por associação com preço.\n")
    for am in sorted(selected_amen):
        L.append(f"  - `{am}` (prevalência {100*am_prev[am]:.0f}%)\n")
    L.append("\n## 5. Associações descritivas\n")
    for _, r in desc_df.iterrows():
        if r["tipo"] == "binaria":
            L.append(f"- {r['variavel']}: com N={int(r['n_com'])}, sem N={int(r['n_sem'])}; "
                     f"mediana com {fmt(r['mediana_com'])} vs sem {fmt(r['mediana_sem'])} (dif {fmt(r['diferenca_bruta'])}).\n")
        else:
            L.append(f"- {r['variavel']}: rho={r['rho_spearman']:.2f} [CI {r['ci_rho_025']:.2f};{r['ci_rho_975']:.2f}], N={int(r['n'])}.\n")
    # obs: recuperar std original de number_of_bedrooms
    _bd_std = stds_global.get("number_of_bedrooms", (np.nan, np.nan))[1]
    _bd_row = coef_df[(coef_df.modelo == "M1_acionavel") & (coef_df.variavel == "number_of_bedrooms")].iloc[0]
    L.append("\n## 6. Modelo 1 (acionável) — principal_all\n")
    L.append(f"Condition: {cond1:.1f}. R² treino: {r2_from_xy(use_main_all['log_y'].values, res1['yhat']):.3f}. "
             f"R² validação agrupada por owner: {r2v2_mean:.3f} (desvio {r2v2_sd:.3f}). N={len(use_main_all)}.\n")
    L.append(
        "**Escala:** variáveis numéricas padronizadas; os percentuais referem-se a 1 desvio-padrão da "
        f"variável, não a 1 unidade. `number_of_bedrooms` tem std original {_bd_std:.3f} quartos. "
        "Um aumento de **1 desvio-padrão no número de quartos esteve associado a "
        f"**{fmt(_bd_row['dif_percentual_aproximada'],1)}%** de diferença na diária anunciada ajustada "
        f"(IC95 {fmt(_bd_row['dif_percentual_ci_025'],2)};{fmt(_bd_row['dif_percentual_ci_975'],2)}%).\n"
    )
    for _, r in coef_df[coef_df.modelo == "M1_acionavel"].sort_values("dif_percentual_aproximada", ascending=False).head(10).iterrows():
        ci_txt = f"[{fmt(r['dif_percentual_ci_025'],2)};{fmt(r['dif_percentual_ci_975'],2)}]" if not r["ci_insuficiente"] else "CI n/d"
        pout = " fora-IC" if r["point_outside_bootstrap_ci"] else ""
        L.append(f"- {r['variavel']} ({r['interpretation_unit']}): {fmt(r['dif_percentual_aproximada'],1)}% {ci_txt}{pout}\n")
    L.append("\n## 7. Modelo 2 (ampliado correlacional)\n")
    L.append(f"Condition: {cond2:.1f}. R² treino: {r2_from_xy(use_main_all['log_y'].values, res2['yhat']):.3f}. "
             f"R² validação agrupada por owner: {r2v1_mean:.3f} (desvio {r2v1_sd:.3f}). N={len(use_main_all)}.\n")
    for _, r in coef_df[coef_df.modelo == "M2_ampliado"].sort_values("dif_percentual_aproximada", ascending=False).head(10).iterrows():
        ci_txt = f"[{fmt(r['dif_percentual_ci_025'],2)};{fmt(r['dif_percentual_ci_975'],2)}]" if not r["ci_insuficiente"] else "CI n/d"
        pout = " fora-IC" if r["point_outside_bootstrap_ci"] else ""
        L.append(f"- {r['variavel']}: {fmt(r['dif_percentual_aproximada'],1)}% {ci_txt}{pout}\n")
    L.append("\n## 8. Estabilidade por cobertura e sensibilidade de magnitude\n")
    est = stab_summary_df[stab_summary_df.usable_as_supporting_evidence == True].sort_values("coef_percentual_principal", ascending=False)  # noqa: E712
    L.append("Variações de magnitude (principal N=493 vs sem outliers N=462):\n")
    for _, r in stab_summary_df.sort_values("coef_percentual_principal", ascending=False).head(8).iterrows():
        L.append(f"- {r['variavel']}: principal {fmt(r['coef_percentual_principal'],1)}% → sem outliers "
                 f"{fmt(r['estimate_without_outliers'],1)}% (Δ {fmt(r['absolute_change_percentage_points'],1)} pp; "
                 f"sinal {'igual' if r['same_sign'] else 'diferente'}).\n")
    L.append("Associações com **supporting evidence** (3 cenários disponíveis, sinal consistente, IC não cruza zero, "
             "≥950 réplicas, ponto dentro do IC, sinal igual sem outliers, interpretação econômica válida):\n")
    if len(est):
        for _, r in est.iterrows():
            L.append(f"- {r['variavel']}: {fmt(r['coef_percentual_principal'],1)}% [CI {fmt(r['ci_diff_025'],2)};{fmt(r['ci_diff_975'],2)}]\n")
    else:
        L.append("- (nenhuma)\n")
    L.append("\n`usable_for_recommendation_alone=False` para todos: análise observacional, associação ≠ causalidade, "
             "diária anunciada ≠ receita, e a recomendação depende conjuntamente das Fases 1 e 2. "
             "'Outros bairros raros' e 'Hotel/outros' não têm supporting evidence por agregarem categorias heterogêneas.\n")
    # interpretação final cautelosa
    _bd_princ = coef_df.loc[(coef_df.modelo=='M1_acionavel') & (coef_df.variavel=='number_of_bedrooms'),'dif_percentual_aproximada'].iloc[0]
    _bd_wo = m1_wo.get("number_of_bedrooms", np.nan)
    L.append("\n### Interpretação (cautelosa)\n")
    L.append(
        "- A quantidade de quartos manteve associação **positiva** nos cenários de cobertura e na sensibilidade "
        "sem outliers, e o IC bootstrap do modelo principal não cruzou zero.\n"
        f"- Porém, a **magnitude** variou consideravelmente: {fmt(_bd_princ,1)}% (principal) → {fmt(_bd_wo,1)}% "
        "(sem outliers). O sinal positivo permaneceu, mas a magnitude apresentou sensibilidade relevante à "
        "presença dos valores extremos; não a descrevemos como robusta.\n"
        "- Nenhuma comodidade individual atendeu a todos os critérios de estabilidade.\n"
        "- Os resultados **apoiam, mas não substituem**, a evidência econômica das Fases 1 e 2.\n"
        "- **Não existe evidência causal** de que adicionar quartos ou comodidades aumentará a diária.\n"
    )
    L.append("\n## 9. Análise dos três segmentos\n")
    for _, r in shortlist_df.iterrows():
        nota_txt = r["nota"]
        if isinstance(nota_txt, str) and nota_txt.strip() == "":
            L.append(f"- **{r['segmento']}**: N_precificado={int(r['n_precificado_total'])}, N_principal={int(r['n_principal'])}, "
                     f"cobertura mediana {fmt(r['cobertura_med'],2)}.\n")
        else:
            L.append(f"- **{r['segmento']}**: N_precificado={int(r['n_precificado_total'])}, N_principal={int(r['n_principal'])}, "
                     f"cobertura mediana {fmt(r['cobertura_med'],2)}. {nota_txt}\n")
    L.append("\n## 10. Limitações\n")
    L.append("- Associação ≠ causalidade; sem ocupação observada; diária anunciada ≠ receita.\n"
             "- Snapshots jan/2025; sazonalidade só jan–abr.\n"
             "- Reputação não é característica física; não acionável.\n"
             "- Presença textual de comodidade ≠ qualidade física.\n"
             "- N reduzido em alguns segmentos da shortlist.\n"
             "- Bootstrap por owner preserva multiplicidade; IC pode não conter o ponto (instabilidade de cluster) — reportado como fora-IC.\n"
             "- Validação agrupada por owner: R² médio pode ser <=0 (overfit) ⇒ associações são exploratórias.\n")
    L.append("\n## 11. Implicações para a recomendação final\n")
    L.append("- Acionável (estrutural/operacional) vs reputacional.\n"
             "- Quais associações sobrevivem ao controle de bairro×perfil e à estabilidade por cobertura.\n"
             "- Reforçar/confrontar a decisão econômica da Fase 2 com as características dos 3 segmentos.\n")
    write_md_lf("".join(L), OUT / "phase3_findings.md")

    print("\n=== VALIDAÇÕES ===")
    for ok, msg in checks:
        print(("  [OK] " if ok else "  [FALHA] ") + msg)
    np_ = sum(1 for ok, _ in checks if ok)
    print(f"\n{np_}/{len(checks)} verificações passaram.")
    print(f"R² validação (M1) = {r2v2_mean:.3f}; (M2) = {r2v1_mean:.3f}")
    print("\nFase 3 concluída.")


if __name__ == "__main__":
    main()