# Metodologia de preparação dos dados

> Documento objetivo de como as bases derivadas foram construídas.
> Python 3.13.5 · pandas 3.0.5 · numpy 2.4.4 (ver `requirements.txt`).
> Não contém recomendação de investimento.

## 1. Fontes e unidade de cada CSV

| Arquivo bruto | Unidade da linha | Chave | Observações |
|---|---|---|---|
| `data/Details_Itapema.csv` | 1 anúncio Airbnb | `airbnb_listing_id` (única, 4.441) | Base principal dos listings |
| `data/Hosts_ids_Itapema.csv` | host × snapshot | `owner_id` (não única) | 1 a 112 snapshots por owner |
| `data/Mesh_Ids_Data_Itapema.csv` | 1 anúncio + geografia | `airbnb_listing_id` (única, 4.441) | Fonte de `suburb`/coordenadas |
| `data/Price_AV_Itapema.csv` | preço anunciado de um anúncio para uma data de estadia em uma captura | grão bruto `airbnb_listing_id` × `date` × `aquisition_date`; `airbnb_listing_id` + `date` **não é único** antes da deduplicação | 3 ondas de captura (06/07/20-jan-2025) |
| `data/VivaReal_Itapema.csv` | 1 anúncio de venda | `listing_id` (8.293 após dedupe) | Snapshot único de 11-jan-2025 |

## 2. Relacionamentos entre as bases

- `Details × Mesh`: **1:1** por `airbnb_listing_id` (cobertura 100%). Usar Mesh para `suburb` e coordenadas — os `latitude`/`longitude` de Details são todos (0,0).
- `Details × Price`: **1:N**. Para cada `airbnb_listing_id` há um preço por `stay_date`.
- `Details × Hosts`: no bruto, um join direto por `owner_id` pode **multiplicar linhas** (vários snapshots por owner). Após deduplicar Hosts para **1 linha por owner**, o relacionamento vindo de Details é **N:1**; visto do host, é **1:N** (um host pode possuir vários anúncios).
- `VivaReal`: sem chave comum com o Airbnb; relaciona-se **por características** (bairro, tipologia, medidas) para estimar mercado de venda.

## 3. Deduplicação

### Price
- `aq_ts`: timestamp completo de `aquisition_date` (usado para **ordenar**).
- `aq_date`: apenas a data (usada na **elegibilidade**).
- Regra de elegibilidade: **`aq_date <= stay_date`** — capturas feitas no próprio dia da estadia são elegíveis por convenção (documentado em `outputs/quality/eligibility_audit.csv`).
- Para cada `airbnb_listing_id × stay_date` (no **Price derivado**, após a deduplicação), seleciona-se o maior `aq_ts` elegível → **1 preço por par** (isso não vale para o CSV bruto, que guarda o grão `airbnb_listing_id × date × aquisition_date`). Ausência de preço é **ausência de observação**, não preço zero nem indisponibilidade.
- Aplicado a 59.040 pares = **1.005 anúncios** (`price_dedup_full.csv`).

### Hosts
- Para cada `owner_id`, mantém-se o **snapshot mais recente** (`host_snapshot_ts` decrescente; desempate pela última aparição no arquivo).
- Resultado: **3.057 owners** (`hosts_dedup.csv`).
- Auditoria em `outputs/quality/hosts_snapshot_audit.csv`: para 100% dos owners o snapshot selecionado é igual ao máximo; **509 owners** tiveram a linha escolhida alterada em relação à regra antiga (snapshot mais antigo).
- Para o owner **227777128** foi observada variação em `number_of_reviews_host` entre capturas do mesmo dia. **A causa não pode ser determinada pela base.**

### VivaReal
- Dedupe por `listing_id`: ordena-se por `(listing_id, n_nulos, ordem_original)` com `ascending=[True, True, False]` e `keep='first'` → em caso de empate fica a **última aparição** no arquivo; linha sempre **integral** do original (0 híbridas).
- Conflitos detectados de forma NA-aware (NA conta como categoria) em **todas** as colunas: 36 ids duplicados; **1** com conflito (somente `amenities`) — flags `is_duplicate_listing_id`, `dup_any_conflict`, `dup_conflict_columns`, `dup_amenities_conflict`.
- Resultado: **8.293** linhas de 8.329.

## 4. Price: 1.005 × 999 anúncios

- `price_dedup_full.csv`: os **1.005** anúncios com preço elegível.
- `price_analytic.csv`: os **999** que possuem correspondência em `Details` — **é esta a população usada nas análises** de perfil, localização e características.
- **6 órfãos** (anúncios sem correspondência), totalizando 509 linhas brutas, ficam **registrados** em `outputs/quality/orphans_price.csv` e **excluídos** das comparações.

## 5. Cobertura (denominador = 105 datas)

- Janela = **105 datas únicas** de estadia (06/jan a 20/abr/2025).
- **Cobertura de um anúncio = nº de datas em que aparece ÷ 105**.
- Stats global (full e analítico): mediana 0,59; min 0,02; p25 0,40; p75 0,73; máx 1,00.
- Datas ausentes **não** são interpretadas como disponibilidade, ocupação ou preço zero.

## 6. Outliers de preço/m² (VivaReal)

- `price_per_m2 = sale_price / usable_area` (somente `usable_area > 0` e `sale_price > 0`).
- Hierarquia **sem sobreposição**:
  - bairro × tipologia com **N ≥ 30**: limites do próprio grupo (Q1−1,5·IQR / Q3+1,5·IQR);
  - **10 ≤ N < 30**: fallback para IQR da **tipologia em toda Itapema**;
  - **N < 10**: grupo apenas **reportado**, sem classificação automática.
- Flag `is_outlier_pm2` (booleano anulável: True/False/NA) marca outliers; **registros são mantidos** — análises mostram sensibilidade com e sem eles. Detalhe por grupo em `outputs/quality/vivareal_outlier_groups.csv`.

## 7. Comparação ajustada por data

Função `monthly_equal_weight_adr` (em `scripts/build_base.py`):

1. mediana por **grupo × stay_date**;
2. média das medianas diárias por **grupo × mês**;
3. média dos **quatro resultados mensais** (2025-01 a 2025-04), **somente** se os 4 meses esperados existirem; caso contrário retorna `NA` com `insufficient_month_coverage=True`.

Sempre reportando `n_anuncios` e `n_dates` por grupo × mês. Evita dar peso indevido a meses com mais observações.

## 8. Limitações metodológicas

- **Preço anunciado ≠ receita.** A base contém a diária anunciada na captura; não há receita realizada.
- **Sem ocupação observada.** Não existem reservas/calendário. Qualquer receita depende de cenários de ocupação (hipóteses explícitas).
- **Viés de cobertura.** Apenas ~999 de 4.441 anúncios têm preço; a cobertura varia por anúncio (ver seção 5).
- **Snapshots de janeiro de 2025.** Detalhes/Hosts (13-jan), VivaReal (11-jan), Price (06/07/20-jan); janela de estadias 06/jan–20/abr/2025. Não são um painel temporal contínuo.
- **Sem despesas operacionais** (condomínio, IPTU, manutenção, gestão) no cálculo de retorno → métricas são estimativas brutas.

## 9. Reprodução

```bash
pip install -r requirements.txt   # pandas 3.0.5, numpy 2.4.4 (Python 3.13.5)
python scripts/build_base.py      # regenera outputs/processed/ e outputs/quality/
```

O script executa **33 verificações essenciais antes de gravar**; se qualquer uma falhar, aborta sem escrever saídas. Saídas: 5 bases em `outputs/processed/`, auditorias e `quality_report.md` em `outputs/quality/`.