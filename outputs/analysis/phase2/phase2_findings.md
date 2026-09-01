# Fase 2 — Preço de aquisição e eficiência econômica bruta estimada
## 1. Decisão apoiada
Quais combinações **bairro × perfil** oferecem a melhor relação entre **diária anunciada ajustada** e **preço anunciado de aquisição** no snapshot de janeiro de 2025? Não é recomendação final nem 'comprar hoje' — os dados são um retrato de jan/2025 e as características do desempenho serão analisadas posteriormente.

## 2. Fontes, snapshots e ausência de chave comum
- Airbnb: `Price_AV_Itapema.csv` (capturas 06/07/20-jan-2025; estadias 06-jan a 20-abr-2025) + `Details_Itapema.csv` + `Mesh_Ids_Data_Itapema.csv`.
- VivaReal: `VivaReal_Itapema.csv` (snapshot 11-jan-2025), deduplicado em `vivareal_dedup.csv`.
- **Não há chave comum** entre Airbnb e VivaReal. Comparação **agregada por bairro × perfil**, não um pareamento entre imóveis.
- Airbnb não possui área útil válida; não é possível parear por metragem.
- Perfil '0 quarto' pode ser studio OU informação não preenchida (cautela).

## 3. População e exclusões
- Airbnb: 999 anúncios precificados, 58.600 pares; inventário 4.441.
- VivaReal: funil cumulativo em `vivareal_funnel.csv`; auditoria por bairro×perfil em `vivareal_coverage.csv`:
  - [principal] bruto_dedup (base: —): mantidos 8293 (excluídos na etapa 0)
  - [principal] apt_ou_casa (base: bruto_dedup): mantidos 8044 (excluídos na etapa 249)
  - [principal] bairro_conhecido (base: apt_ou_casa): mantidos 7949 (excluídos na etapa 95)
  - [principal] sale_price_positivo (base: bairro_conhecido): mantidos 7949 (excluídos na etapa 0)
  - [principal] area_positiva (base: sale_price_positivo): mantidos 7949 (excluídos na etapa 0)
  - [principal] pm2_valido (base: area_positiva): mantidos 7949 (excluídos na etapa 0)
  - [principal] elegiveis_principal_is_outlier_false (base: pm2_valido): mantidos 7307 (excluídos na etapa 642)
  - [sensibilidade] todos_validos_incluindo_outlier_e_flag_na (base: pm2_valido): mantidos 7949
O cenário principal retém **7.307** registros após excluir **642** registros classificados como outliers de preço/m². A sensibilidade parte dos **7.949** registros válidos anteriores ao filtro de outliers, incluindo flags True e NA.

## 4. Definição das métricas
- **diária anunciada ajustada**: mediana por (segmento x stay_date); média das medianas diárias por mês; média igualmente ponderada (jan–abr/2025); só quando os 4 meses existem.
- **mediana de aquisição**: mediana de `sale_price` dos elegíveis (não usa mediana(price_per_m2) × mediana(area)).
- **receita bruta anualizada de cenário** = diária × 365 × ocupação (50/60/75%).
- **rendimento bruto anualizado estimado** = receita / mediana_preco.
- **payback bruto estimado (anos)** = mediana_preco / receita.
- **potencial bruto janela 105 dias a 100%** = diária × 105.
- NUNCA usados: receita realizada, lucro, ROI líquido, cap rate, retorno garantido.
- Bootstrap principal: reamostra anúncios Airbnb e anúncios VivaReal separadamente; IC95 ≥950 réplicas válidas; meses derivados de `pivot.columns` (alinhamento verificado).

## 5. Ranking principal no cenário de 60%
- **morretes | 2. apartamento (2q)**: rendimento@60% = **13.92%** (IC95 [12.87; 15.10]%) | N_airbnb=51, N_viva=1019 | diária R$ 502 | preço R$ 789,550 | payback 7.2 anos.
- **centro | 2. apartamento (2q)**: rendimento@60% = **13.54%** (IC95 [10.98; 15.78]%) | N_airbnb=65, N_viva=87 | diária R$ 711 | preço R$ 1,150,000 | payback 7.4 anos.
- **meia praia | 1. apartamento compacto (0-1q)**: rendimento@60% = **13.38%** (IC95 [11.26; 14.35]%) | N_airbnb=28, N_viva=55 | diária R$ 535 | preço R$ 875,000 | payback 7.5 anos.
- **meia praia | 2. apartamento (2q)**: rendimento@60% = **10.91%** (IC95 [10.13; 11.82]%) | N_airbnb=187, N_viva=241 | diária R$ 533 | preço R$ 1,070,000 | payback 9.2 anos.
- **meia praia | 3. apartamento (3q+)**: rendimento@60% = **7.27%** (IC95 [6.92; 7.72]%) | N_airbnb=392, N_viva=2835 | diária R$ 790 | preço R$ 2,380,000 | payback 13.8 anos.
- **centro | 3. apartamento (3q+)**: rendimento@60% = **6.68%** (IC95 [5.96; 7.55]%) | N_airbnb=50, N_viva=808 | diária R$ 822 | preço R$ 2,696,500 | payback 15.0 anos.

## 6. Cenários de 50%, 60% e 75%
- morretes | 2. apartamento (2q): 50% → **11.60%** (payback 8.6y); 60% → **13.92%** (7.2y); 75% → **17.40%** (5.7y).
- centro | 2. apartamento (2q): 50% → **11.29%** (payback 8.9y); 60% → **13.54%** (7.4y); 75% → **16.93%** (5.9y).
- meia praia | 1. apartamento compacto (0-1q): 50% → **11.15%** (payback 9.0y); 60% → **13.38%** (7.5y); 75% → **16.73%** (6.0y).
- meia praia | 2. apartamento (2q): 50% → **9.09%** (payback 11.0y); 60% → **10.91%** (9.2y); 75% → **13.64%** (7.3y).
- meia praia | 3. apartamento (3q+): 50% → **6.06%** (payback 16.5y); 60% → **7.27%** (13.8y); 75% → **9.09%** (11.0y).
- centro | 3. apartamento (3q+): 50% → **5.57%** (payback 18.0y); 60% → **6.68%** (15.0y); 75% → **8.35%** (12.0y).

## 7. Sensibilidade ao preço (P25/mediana/P75)
Ver `purchase_price_sensitivity.csv`.
- No preço P25, o maior rendimento@60% é **centro | 2. apartamento (2q)**.
- No preço mediana, o maior rendimento@60% é **morretes | 2. apartamento (2q)**.
- No preço P75, o maior rendimento@60% é **morretes | 2. apartamento (2q)**.

## 8. Sensibilidade a outliers
Estimativa pontual da sensibilidade = diária pontual × 365 × 0.60 / mediana(preço todos válidos); IC por bootstrap multiparamétrico (Airbnb + VivaReal). Ver `outlier_sensitivity.csv`.
Top 3 principal vs top 3 (todos os válidos) — composição mudou? **NÃO**.
- principal_False: morretes | 2. apartamento (2q) (13.92%); centro | 2. apartamento (2q) (13.54%); meia praia | 1. apartamento compacto (0-1q) (13.38%)
- sensibilidade_todos: morretes | 2. apartamento (2q) (13.92%); centro | 2. apartamento (2q) (13.54%); meia praia | 1. apartamento compacto (0-1q) (13.35%)

## 9. Shortlist provisória (regra multicritério)
Regra reproduzível (NÃO é simplesmente o maior ponto): universo = segmentos elegíveis; candidatos = união dos segmentos no top 3 em ao menos um de: principal@60%, sensibilidade a outliers, preço P25@60%, mediana@60%, P75@60%. Ordenação: limite inferior do IC95 do rendimento principal@60% (desc), empate usa maior N Airbnb, depois maior N VivaReal. Máximo 3 selecionados.
- **morretes | 2. apartamento (2q)** (ordem 1): rend60=13.92%; ICinf=12.87%; N_air=51; N_viva=1019; cobertura=0.59; concentração(maior owner)=14%; top3 em: principal@60,outliers,P25,mediana,P75
- **meia praia | 1. apartamento compacto (0-1q)** (ordem 2): rend60=13.38%; ICinf=11.26%; N_air=28; N_viva=55; cobertura=0.62; concentração(maior owner)=11%; top3 em: principal@60,outliers,P25,mediana,P75
- **centro | 2. apartamento (2q)** (ordem 3): rend60=13.54%; ICinf=10.98%; N_air=65; N_viva=87; cobertura=0.67; concentração(maior owner)=31%; top3 em: principal@60,outliers,P25,mediana,P75

## 10. Limitações e riscos
- Diária anunciada ≠ receita realizada; sem ocupação observada (ocupação é cenário).
- Rendimento/payback são BRUTOS: sem condomínio/IPTU/manutenção/gestão.
- Comparação agregada sem chave comum; mismatch possível no mesmo bairro×perfil.
- Sazonalidade observável apenas jan–abr/2025; anualização é extrapolação.
- Concentração por proprietário é risco de representatividade, não causa de preço.
- Cobertura de condomínio/IPTU parcial no VivaReal (~30% ausente).

## 11. Perguntas pendentes para a recomendação final
- Características que explicam o desempenho (reviews, superhost, amenities, capacidade).
- Compromisso diária × preço: N limitado em segmentos pequenos.
- Como tratar a sazonalidade na anualização para a recomendação.
