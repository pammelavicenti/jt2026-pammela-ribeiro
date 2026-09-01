# Fase 3 — Características associadas às maiores diárias anunciadas
## 1. Pergunta de negócio
Identificar características estruturais, operacionais, reputacionais e de comodidades **associadas** à diária anunciada em Itapema, controlando bairro e perfil. Não há linguagem causal.

## 2. População e variável-alvo
Diária ajustada = média das médias mensais (jan–abr/2025), só com 4 meses; cobertura = n_datas/105. N: 4m sem limiar=561; cov>=25=558; principal(cov>=50)=493; cov>=75=220. Modelo principal: N=493 (não filtra a resposta). Sensibilidade sem outliers (IQR log_y): N=462.

## 3. Ausências e sentinelas
star_rating==0 e notas 0 com number_of_reviews==0 = AUSÊNCIA (has_reviews). Imputação documentada (mediana da dimensão, precedida de flag de ausência). response_rate/time (100% NA) e min_nights (100% 0) excluídos.

## 4. Comodidades selecionadas
Parser ok em 4441/4441 (100.0%). Selecionadas por frequência em 10-90%: 8. Nunca por associação com preço.
  - `ar-condicionado` (prevalência 73%)
  - `churrasqueira` (prevalência 65%)
  - `estacionamento incluido` (prevalência 80%)
  - `ferro de passar` (prevalência 46%)
  - `loucas e talheres` (prevalência 54%)
  - `maquina de lavar` (prevalência 73%)
  - `microondas` (prevalência 48%)
  - `tv` (prevalência 77%)

## 5. Associações descritivas
- can_instant_book: com N=201, sem N=288; mediana com 594 vs sem 644 (dif -50).
- is_professional: com N=128, sem N=361; mediana com 593 vs sem 633 (dif -40).
- is_new_listing: com N=14, sem N=209; mediana com 781 vs sem 617 (dif 164).
- is_superhost: com N=162, sem N=331; mediana com 591 vs sem 638 (dif -47).
- is_verified: com N=493, sem N=0; mediana com 617 vs sem n/d (dif n/d).
- has_reviews: com N=474, sem N=19; mediana com 614 vs sem 1,000 (dif -386).
- am_ar-condicionado: com N=335, sem N=158; mediana com 626 vs sem 605 (dif 21).
- am_churrasqueira: com N=321, sem N=172; mediana com 633 vs sem 591 (dif 41).
- am_estacionamento incluido: com N=365, sem N=128; mediana com 632 vs sem 583 (dif 49).
- am_ferro de passar: com N=370, sem N=123; mediana com 609 vs sem 654 (dif -44).
- am_loucas e talheres: com N=423, sem N=70; mediana com 615 vs sem 632 (dif -18).
- number_of_bedrooms: rho=0.66 [CI 0.61;0.71], N=493.
- number_of_bathrooms: rho=0.64 [CI 0.58;0.70], N=493.
- number_of_beds: rho=0.51 [CI 0.44;0.58], N=493.
- number_of_guests: rho=0.61 [CI 0.54;0.66], N=493.
- cleaning_fee: rho=0.48 [CI 0.40;0.55], N=493.
- picture_count: rho=0.23 [CI 0.15;0.31], N=493.
- amenity_count: rho=0.02 [CI -0.08;0.11], N=493.
- years_host: rho=-0.00 [CI -0.09;0.09], N=493.
- months_host: rho=0.06 [CI -0.04;0.14], N=493.
- portfolio_owner: rho=-0.15 [CI -0.23;-0.07], N=493.
- number_of_reviews: rho=-0.16 [CI -0.25;-0.07], N=493.
- star_effective: rho=0.14 [CI 0.05;0.22], N=493.

## 6. Modelo 1 (acionável) — principal_all
Condition: 23.0. R² treino: 0.555. R² validação agrupada por owner: 0.453 (desvio 0.163). N=493.
**Escala:** variáveis numéricas padronizadas; os percentuais referem-se a 1 desvio-padrão da variável, não a 1 unidade. `number_of_bedrooms` tem std original 0.985 quartos. Um aumento de **1 desvio-padrão no número de quartos esteve associado a **42.6%** de diferença na diária anunciada ajustada (IC95 30.50;59.71%).
- number_of_bedrooms (1 desvio-padrão (std original 0.985) na variável number_of_bedrooms): 42.6% [30.50;59.71]
- profile_1. apartamento compacto (0-1q) (categoria 1. apartamento compacto (0-1q) vs referência '2. apartamento (2q)'): 17.0% [3.36;45.06]
- amenity_count (1 desvio-padrão (std original 12.704) na variável amenity_count): 13.9% [7.65;19.52]
- profile_4. casa (categoria 4. casa vs referência '2. apartamento (2q)'): 9.8% [-10.60;32.93]
- is_new_listing (1 desvio-padrão (std original 0.243) na variável is_new_listing): 6.8% [0.00;10.38]
- is_professional (1 desvio-padrão (std original 0.440) na variável is_professional): 6.0% [-0.70;16.44]
- cleaning_fee (1 desvio-padrão (std original 117.875) na variável cleaning_fee): 5.9% [-0.46;12.41]
- am_ar-condicionado (1 desvio-padrão (std original 0.467) na variável am_ar-condicionado): 4.8% [0.81;8.49]
- am_maquina de lavar (1 desvio-padrão (std original 0.495) na variável am_maquina de lavar): 3.8% [0.16;8.84]
- am_estacionamento incluido (1 desvio-padrão (std original 0.439) na variável am_estacionamento incluido): 2.4% [0.02;5.62]

## 7. Modelo 2 (ampliado correlacional)
Condition: 25.5. R² treino: 0.588. R² validação agrupada por owner: 0.215 (desvio 0.531). N=493.
- number_of_bedrooms: 40.5% [29.62;56.12]
- profile_1. apartamento compacto (0-1q): 16.3% [2.92;50.81]
- amenity_count: 14.7% [7.87;20.53]
- is_professional: 12.9% [4.26;21.21]
- cleaning_fee: 4.9% [-1.21;10.92]
- am_ar-condicionado: 4.3% [0.40;7.96]
- profile_4. casa: 4.2% [-15.84;24.78]
- can_instant_book: 4.0% [-0.82;10.86]
- is_new_listing: 3.6% [-6.05;7.86]
- am_maquina de lavar: 3.0% [-0.45;7.66]

## 8. Estabilidade por cobertura e sensibilidade de magnitude
Variações de magnitude (principal N=493 vs sem outliers N=462):
- number_of_bedrooms: principal 42.6% → sem outliers 17.0% (Δ 25.6 pp; sinal igual).
- profile_1. apartamento compacto (0-1q): principal 17.0% → sem outliers -1.2% (Δ 18.2 pp; sinal diferente).
- amenity_count: principal 13.9% → sem outliers 11.5% (Δ 2.4 pp; sinal igual).
- profile_4. casa: principal 9.8% → sem outliers 22.5% (Δ 12.7 pp; sinal igual).
- is_new_listing: principal 6.8% → sem outliers 7.9% (Δ 1.1 pp; sinal igual).
- is_professional: principal 6.0% → sem outliers 4.7% (Δ 1.3 pp; sinal igual).
- cleaning_fee: principal 5.9% → sem outliers 9.0% (Δ 3.1 pp; sinal igual).
- am_ar-condicionado: principal 4.8% → sem outliers 5.0% (Δ 0.2 pp; sinal igual).
Associações com **supporting evidence** (3 cenários disponíveis, sinal consistente, IC não cruza zero, ≥950 réplicas, ponto dentro do IC, sinal igual sem outliers, interpretação econômica válida):
- number_of_bedrooms: 42.6% [CI 30.50;59.71]

`usable_for_recommendation_alone=False` para todos: análise observacional, associação ≠ causalidade, diária anunciada ≠ receita, e a recomendação depende conjuntamente das Fases 1 e 2. 'Outros bairros raros' e 'Hotel/outros' não têm supporting evidence por agregarem categorias heterogêneas.

### Interpretação (cautelosa)
- A quantidade de quartos manteve associação **positiva** nos cenários de cobertura e na sensibilidade sem outliers, e o IC bootstrap do modelo principal não cruzou zero.
- Porém, a **magnitude** variou consideravelmente: 42.6% (principal) → 17.0% (sem outliers). O sinal positivo permaneceu, mas a magnitude apresentou sensibilidade relevante à presença dos valores extremos; não a descrevemos como robusta.
- Nenhuma comodidade individual atendeu a todos os critérios de estabilidade.
- Os resultados **apoiam, mas não substituem**, a evidência econômica das Fases 1 e 2.
- **Não existe evidência causal** de que adicionar quartos ou comodidades aumentará a diária.

## 9. Análise dos três segmentos
- **morretes | 2. apartamento (2q)**: N_precificado=27, N_principal=24, cobertura mediana 0.76.
- **meia praia | 1. apartamento compacto (0-1q)**: N_precificado=18, N_principal=17, cobertura mediana 0.71. N<20: somente descrição, sem inferência
- **centro | 2. apartamento (2q)**: N_precificado=40, N_principal=37, cobertura mediana 0.79.

## 10. Limitações
- Associação ≠ causalidade; sem ocupação observada; diária anunciada ≠ receita.
- Snapshots jan/2025; sazonalidade só jan–abr.
- Reputação não é característica física; não acionável.
- Presença textual de comodidade ≠ qualidade física.
- N reduzido em alguns segmentos da shortlist.
- Bootstrap por owner preserva multiplicidade; IC pode não conter o ponto (instabilidade de cluster) — reportado como fora-IC.
- Validação agrupada por owner: R² médio pode ser <=0 (overfit) ⇒ associações são exploratórias.

## 11. Implicações para a recomendação final
- Acionável (estrutural/operacional) vs reputacional.
- Quais associações sobrevivem ao controle de bairro×perfil e à estabilidade por cobertura.
- Reforçar/confrontar a decisão econômica da Fase 2 com as características dos 3 segmentos.
