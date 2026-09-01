# Fase 4 — Síntese da recomendação de investimento (Itapema, snapshot jan/2025)
## 1. Pergunta de negócio
Quais combinações bairro × perfil entre os 3 segmentos são a escolha mais defensável para a Seazone em short stay, dadas a diária anunciada ajustada (F1), o preço anunciado de aquisição e rendimento/payback brutos (F2), e as características associadas (F3)? Baseado em jan/2025, com hipóteses de ocupação explícitas; não é previsão de retorno garantido.

## 2. Alternativas avaliadas
- morretes | 2. apartamento (2q)
- meia praia | 1. apartamento compacto (0-1q)
- centro | 2. apartamento (2q)

## 3. Critérios de decisão (ordem)
1. Suficiência e rastreabilidade dos dados; 2. Rendimento bruto no cenário central (ocupação 60%); 3. Estabilidade ocupação 50/60/75%; 4. Sensibilidade ao preço de aquisição; 5. Sensibilidade a outliers; 6. Evidências F1/F3 como apoio (não substituição).

## 4. Matriz comparativa
- **morretes | 2. apartamento (2q)**: diária ajustada R$ 502 | preço mediano R$ 789,550 | rend. bruto 13.9% (IC 12.87%–15.10%) | payback 7.2 anos | N air(F2) 51 / N air(F3 principal) 24 / N viva(F2) 1019 | maior owner 14%.
- **centro | 2. apartamento (2q)**: diária ajustada R$ 711 | preço mediano R$ 1,150,000 | rend. bruto 13.5% (IC 10.98%–15.78%) | payback 7.4 anos | N air(F2) 65 / N air(F3 principal) 37 / N viva(F2) 87 | maior owner 31%.
- **meia praia | 1. apartamento compacto (0-1q)**: diária ajustada R$ 535 | preço mediano R$ 875,000 | rend. bruto 13.4% (IC 11.26%–14.35%) | payback 7.5 anos | N air(F2) 28 / N air(F3 principal) 17 / N viva(F2) 55 | maior owner 11% — N<20: somente descrição, sem inferência.

## 5. Recomendação principal
**morretes | 2. apartamento (2q)** — rendimento bruto@60% = 13.9% (IC 12.87%–15.10%), payback estimado 7.2 anos, diária ajustada R$ 502, preço mediano R$ 789,550.
**Principais riscos:** rendimento BRUTO (sem despesas); preço anunciado, não negociado; ocupação é hipótese; N Airbnb moderado; valorização não observada.
**Interpretação honesta:** Morretes 2q foi o segmento mais defensável pelos critérios adotados e liderou quatro dos cinco cenários avaliados, mas sua vantagem central sobre Centro e Meia Praia é pequena e não foi demonstrada como estatisticamente conclusiva (ICs de bootstrap se sobrepõem; não foi calculado IC da diferença entre segmentos).
**Nível de confiança:** moderado — Vantagem central pequena e ICs bootstrap entre os 3 segmentos se sobrepõem; não foi calculado IC da diferença entre segmentos. Ocupação é hipótese (50/60/75%), despesas não incluídas, preços são anunciados (não negociados) e N Airbnb é moderado (28 a 65).

## 6. Alternativa
**centro | 2. apartamento (2q)** — segundo mais defensável; preferível nos cenários efetivamente calculados em que supera a principal: conjunto_preco@P25, cruzado_centroP25_vs_morretesMediana.
No cenário conjunto em que ambos os segmentos são avaliados pelos respectivos preços P25, centro | 2. apartamento (2q) apresenta rendimento bruto estimado de 17.8%, contra 16.2% de morretes | 2. apartamento (2q) (ver condition_change_scenarios.csv; P25 de cada um é usado conjuntamente, não apenas o do Centro).

## 7. Estabilidade da recomendação
O principal liderou (ou empatou) em 4 de 5 cenários de sensibilidade; pior posição observada 2 entre os 3 segmentos.

## 8. Condições que poderiam mudar a decisão
Cenários efetivamente calculados (não inventados):
- conjunto_preco@P25: principal 16.17% vs alternativa 17.83% → alternativa SUPERA.
- conjunto_preco@mediana: principal 13.92% vs alternativa 13.54% → alternativa não supera.
- conjunto_preco@P75: principal 12.57% vs alternativa 10.16% → alternativa não supera.
- cruzado_centroP25_vs_morretesMediana: principal 13.92% vs alternativa 17.83% → alternativa SUPERA.
- outlier_todos: principal 13.92% vs alternativa 13.54% → alternativa não supera.
- ocupacao_50%: principal 11.60% vs alternativa 11.29% → alternativa não supera.
- ocupacao_60%: principal 13.92% vs alternativa 13.54% → alternativa não supera.
- ocupacao_75%: principal 17.40% vs alternativa 16.93% → alternativa não supera.

## 9. Contribuição das características (Fase 3)
- `number_of_bedrooms` manteve associação positiva nos cenários de cobertura e sem outliers (IC não cruza zero), mas a magnitude é por 1 desvio-padrão (std 0.985 quartos), não por quarto adicional, e caiu de ~42,6% para ~17,0% ao remover outliers.
- Usada como apoio, não isoladamente. Amenities, 'hotel/outros' e 'outros bairros raros' não entram na recomendação.

## 10. Limitações
- Sem reservas/ocupação realizadas (ocupação é hipótese 50/60/75%).
- Rendimento e payback BRUTOS: sem condomínio, IPTU, manutenção, gestão, impostos ou financiamento.
- Preço anunciado (VivaReal), não negociado.
- Comparação agregada bairro×perfil, sem chave comum Airbnb–VivaReal.
- Sazonalidade só jan–abr/2025; anualização é extrapolação.
- Concentração por proprietário é risco de representatividade.
- N principal F3 de Meia Praia compacto = 17 < 20 → evidência descritiva.

## 11. Informações adicionais necessárias antes de compra real
- Ocupação e reservas efetivamente realizadas.
- Despesas operacionais, taxa de administração, condomínio, IPTU, manutenção, limpeza, impostos.
- Custos de financiamento.
- Preço efetivamente negociado do imóvel.
- Condição e idade do imóvel.
- Distância real da praia.
- Regulamentação do condomínio para locação por temporada.
- Liquidez e valorização (não observadas).

## 12. Conclusão executiva
Com base no retrato de jan/2025, o segmento **morretes | 2. apartamento (2q)** foi o mais defensável pelos critérios adotados, com rendimento bruto anualizado estimado de 13.9% no cenário de ocupação de 60% (IC bootstrap de 95%: 12.9% a 15.1%) e payback bruto estimado de 7.2 anos. Sua vantagem sobre os demais segmentos é pequena e não foi demonstrada como estatisticamente conclusiva. A alternativa **centro | 2. apartamento (2q)** é quase tão defensável. A decisão permanece condicionada à validação de ocupação, despesas operacionais e preço efetivamente negociado.
