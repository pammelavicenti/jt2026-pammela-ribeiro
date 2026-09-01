# Rastreabilidade dos resultados

Documento que mapeia cada número ou conclusão apresentado no projeto ao arquivo, coluna, métrica e script
que o produziu. Tudo é verificado diretamente nas saídas versionadas.

> Convenção: "F2" = `analyze_investment_efficiency.py`; "F3" = `analyze_listing_characteristics.py`;
> "F4" = `synthesize_recommendation.py`; "Dados" = `build_base.py`.
> Valores redigidos com `•` quando não são impressos por segurança.

| # | Afirmação / resultado | Valor apresentado | Arquivo de origem | Coluna / métrica | Script responsável | Observação metodológica |
|---|---|---|---|---|---|---|
| 1 | Inventário total de anúncios Airbnb | 4.441 | `outputs/quality/summary_counts.csv` / `data/Details_Itapema.csv` | `details_raw.rows` = 4.441 | `build_base.py` | Linhas brutas de `Details_Itapema.csv`; chave única `airbnb_listing_id`. |
| 2 | Base analítica de preços | 58.600 pares anúncio × data | `outputs/quality/summary_counts.csv` | `price_analytic.rows` = 58.600 | `build_base.py` | Após dedupe (1 preço por anúncio×stay_date) e elegibilidade `aq_date <= stay_date`. |
| 3 | Anúncios precificados e associados ao Details | 999 | `outputs/quality/summary_counts.csv` | `price_analytic.key_nunique` = 999 | `build_base.py` | Mesmos 999 usados nas Fases 1–3. |
| 4 | Recomendação principal | Apartamento de 2 quartos — Morretes | `outputs/analysis/final/decision_matrix.csv` | `segmento` / `role` da matriz; `final_recommendation.md` seção 5 | `synthesize_recommendation.py` | Mais defensável pelos critérios; vantagem pequena, não estatisticamente conclusiva. |
| 5 | Rendimento bruto anualizado estimado (cenário central 60%) | 13,9 % | `outputs/analysis/final/decision_matrix.csv` | `rendimento_60` = 0,13923 | `analyze_investment_efficiency.py` → `synthesize_recommendation.py` | Receita bruta anualizada (diária×365×0,60) ÷ preço mediano de aquisição. Ocupação é hipótese. |
| 6 | Intervalo bootstrap de 95% | 12,9 % a 15,1 % | `outputs/analysis/final/decision_matrix.csv` | `ic_rend60_025` = 0,1287; `ic_rend60_975` = 0,1510 | `analyze_investment_efficiency.py` | IC percentil por bootstrap de anúncios (seed 42; ≥950 réplicas válidas). |
| 7 | Payback bruto estimado | 7,2 anos | `outputs/analysis/final/decision_matrix.csv` | `payback_60` = 7,182 | `analyze_investment_efficiency.py` | Preço mediano ÷ receita bruta anualizada (cenário 60%). Não inclui despesas. |
| 8 | Alternativa | Apartamento de 2 quartos — Centro | `outputs/analysis/final/decision_matrix.csv` | `segmento` / `role` | `synthesize_recommendation.py` | Segundo mais defensável; excepcionalmente lidera no cenário conjunto P25. |
| 9 | Amostras de Morretes (F2 / F3 / VivaReal) | 51 / 24 / 1.019 | `outputs/analysis/final/decision_matrix.csv` | `n_airbnb_precificados_F2`=51; `n_airbnb_principal_F3`=24; `n_vivareal_elegiveis_F2`=1019 | F2 + F3 + `synthesize_recommendation.py` | Ns de populações diferentes (precificados F2, principal F3, VivaReal elegíveis) — não são a mesma amostra. |
| 10 | Amostras do Centro usadas na síntese | 65 / 37 / 87 | `outputs/analysis/final/decision_matrix.csv` | `n_airbnb_precificados_F2`=65; `n_airbnb_principal_F3`=37; `n_vivareal_elegiveis_F2`=87 | F2/F3/F4 | Idem observação do item 9. |
| 11 | Amostras do compacto em Meia Praia | 28 / 17 / 55 | `outputs/analysis/final/decision_matrix.csv` | `n_airbnb_precificados_F2`=28; `n_airbnb_principal_F3`=17; `n_vivareal_elegiveis_F2`=55 | F2/F3/F4 | `n_airbnb_principal_F3`=17 < 20 → somente descrição, sem inferência. |
| 12 | Associação entre nº de quartos e diária | Positiva (IC não cruza zero), por 1 desvio-padrão | `outputs/analysis/phase3/coverage_stability.csv`; `model_coefficients.csv` | `number_of_bedrooms` → `coef_percentual_principal`=42,6 % (M1) | `analyze_listing_characteristics.py` | Associação, não causalidade; por 1 desvio-padrão (std 0,985 quarto), não por quarto adicional. |
| 13 | Sensibilidade da associação sem outliers | 42,6 % → 17,0 % | `outputs/analysis/phase3/coverage_stability.csv` | `estimate_without_outliers`=16,96 (≈17,0 %) | `analyze_listing_characteristics.py` | Magnitude sensível à presença de outliers; sinal permanece positivo. |
| 14 | Cenário conjunto com preço de aquisição P25 | Morretes 16,2 % vs Centro 17,8 % | `outputs/analysis/final/condition_change_scenarios.csv` | `conjunto_preco@P25` → `rendimento_principal`=0,1617; `rendimento_alternativa`=0,1783 | `synthesize_recommendation.py` | **Somente o preço de aquisição foi colocado no P25 (de cada segmento).** A diária anunciada **não** foi submetida a um P25 — não existe coluna de "diária P25" nos arquivos da Fase 4; a diária permanece a mesma (`diaria_anunciada_ajustada` em `decision_matrix.csv`). Por isso o termo correto é "preço de aquisição P25". |
| 15 | Principais limitações da recomendação | — | `outputs/analysis/final/final_recommendation.md` seção 10; `README.md` seção 12 | Texto | `synthesize_recommendation.py` | Sem ocupação realizada; rendimento/payback brutos (sem condomínio, IPTU, manutenção, gestão, impostos); preço anunciado ≠ negociado; sazonalidade só jan–abr/sem extrapolação garantida. |

## Nota sobre valores não divulgados

Qualquer valor classificado como credencial foi substituído por `[REDACTED_CREDENTIAL]` no `ai-log/session.json`
conforme documentado em `ai-log/README.md`; os arquivos numéricos de análise não contêm credenciais.

## Divergências

Nenhuma divergência foi encontrada entre os valores acima e os arquivos de origem nesta revisão.