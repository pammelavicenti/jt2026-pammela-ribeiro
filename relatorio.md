# Relatório Técnico — Recomendação de investimento em Itapema (SC)

> Documento consolidado das Fases 1–4.
> Autora: Pâmmela Vicenti Ribeiro — Hackathon Jovens Talentos AI Builder 2026 (Seazone).
> Base: snapshot de janeiro de 2025 (Airbnb + VivaReal). Sem receita realizada, lucro, retorno líquido ou garantia.

---

## 1. Contexto e pergunta de negócio

A Seazone gere imóveis de short stay e precisa decidir onde e no que investir. Este relatório responde,
para Itapema (SC), com base no snapshot de jan/2025:

1. Qual o melhor perfil de imóvel (tipologia, nº de quartos, tipo)?
2. Qual a melhor localização em termos de receita potencial?
3. Quais características estão associadas às melhores diárias anunciadas?
4. Se a Seazone fosse investir, o que compraria e por quê (com estimativa de retorno bruto)?

Também toma posição sobre a **tese interna** de que apartamentos compactos (0–1 quarto) no **Centro** seriam
a aposta mais eficiente.

Terminologia obrigatória: **diária anunciada ajustada**, **receita bruta anualizada estimada**,
**rendimento bruto anualizado estimado**, **payback bruto estimado**, **cenário hipotético de ocupação**,
**preço anunciado de aquisição**. Associação ≠ causalidade.

---

## 2. Fase 1 — Perfil e localização (diária anunciada ajustada)

- **População:** 999 anúncios precificados / 58.600 pares; inventário 4.441. Janela 105 datas (jan–abr/2025).
- **Diária anunciada ajustada:** mediana por grupo×data → média mensal → média igual ponderada dos 4 meses.

### Perfis (ranking, N≥20)
| Perfil | Diária ajustada | IC95 | N prec. |
|---|---|---|---|
| Apt 3q+ | R$ 793 | [757; 825] | 464 |
| Casa | R$ 625 | [502; 866] | 70 |
| Apt 2q | R$ 542 | [522; 565] | 333 |
| Apt compacto 0–1q | R$ 507 | [457; 540] | 114 |

### Bairros
Meia Praia R$ 674 [651; 704] (N 632) · Tabuleiro dos Oliveiras R$ 663 (N 20) · Centro R$ 616 [585; 653]
(N 205) · Morretes R$ 525 [482; 582] (N 83).

### Tese dos compactos no Centro — **não sustentada**
- Compactos Centro R$ 506 vs compactos fora do Centro R$ 502: diferença +R$ 3 (IC [−69; 97]) → **inconclusiva**.
- Compactos Centro R$ 506 vs aptos 2q+ no Centro R$ 747: diferença −R$ 241 (IC [−306; −166]) → **rejeitada**
  (compactos têm menor diária que aptos maiores no Centro).

---

## 3. Fase 2 — Preço de aquisição e eficiência econômica bruta

- Preço representativo = **mediana de `sale_price`** dos elegíveis VivaReal (não usa preço/m² × área).
- Receita bruta anualizada = diária × 365 × ocupação (50/60/75% — **hipóteses**).
- Rendimento bruto = receita / preço; Payback bruto = preço / receita.
- Bootstrap multiparamétrico (anúncios Airbnb + VivaReal), seed 42, IC95 ≥950 réplicas.

### Ranking central @60%
| Segmento | rend@60% | IC95 | N air | N viva | payback@60% |
|---|---|---|---|---|---|
| Morretes · 2q | 13,92% | [12,9; 15,1] | 51 | 1.019 | 7,2 anos |
| Centro · 2q | 13,54% | [11,0; 15,8] | 65 | 87 | 7,4 anos |
| Meia Praia · compacto | 13,38% | [11,3; 14,4] | 28 | 55 | 7,5 anos |

- Cenários 50/60/75% e sensibilidades de preço (P25/mediana/P75) e de outliers mantêm o **top 3** (as
  sensibilidades preservaram a composição → estabilidade).
- Shortlist (regra multicritério reproduzível, não só o maior ponto): Morretes·2q → Meia Praia·compacto →
  Centro·2q.

---

## 4. Fase 3 — Características associadas (associação ≠ causalidade)

- **Modelo 1 (acionável):** condition ~23; R² treino 0,55; **R² validação agrupada por owner 0,45** (positivo).
- **Modelo 2 (ampliado):** condition ~25,5; R² validação 0,21.
- Bootstrap por **clusters de owner** preservando multiplicidade (seed 42, 1.000 réplicas).
- `number_of_bedrooms`: associação **positiva** à diária (IC não cruza zero), por **1 desvio-padrão**
  (std 0,985 quartos), não por quarto adicional; magnitude sensível: **42,6% → 17,0%** sem outliers.
- Nenhuma comodidade individual atendeu a todos os critérios de estabilidade. Sem evidência causal.

---

## 5. Fase 4 — Síntese e recomendação

### Matriz de decisão (importa de `outputs/analysis/final/decision_matrix.csv`)
| Segmento | N air F2 | N air F3 princ. | N viva F2 | rend@60% | IC95 | payback |
|---|---|---|---|---|---|---|
| Morretes · 2q | 51 | 24 | 1.019 | 13,9% | [12,9; 15,1] | 7,2 anos |
| Centro · 2q | 65 | 37 | 87 | 13,5% | [11,0; 15,8] | 7,4 anos |
| Meia Praia · compacto | 28 | 17 | 55 | 13,4% | [11,3; 14,4] | 7,5 anos |

### Recomendação principal
**Morretes — apartamento de 2 quartos.** Rendimento bruto anualizado estimado de **13,9%** no cenário
hipotético de ocupação de 60% (IC bootstrap 95%: **12,9% a 15,1%**), payback bruto estimado de **7,2 anos**,
diária ajustada R$ 502 e preço mediano de aquisição R$ 789.550. É o mais defensável: liderou quatro dos cinco
cenários de sensibilidade, tem a maior amostra VivaReal (N=1.019) e menor concentração de proprietário
(maior owner ≈ 14%).

**Nível de confiança: moderado.** A vantagem central sobre Centro e Meia Praia é pequena e **não demonstrada
como estatisticamente conclusiva** (ICs de bootstrap se sobrepõem; não foi computado IC da diferença).
Condicionantes: ocupação é hipótese, despesas não incluídas, preço é anunciado (não negociado) e N Airbnb é
moderado (28–65).

### Alternativa
**Centro — apartamento de 2 quartos.** Segundo mais defensável. Preferível nos cenários conjuntos em que o
preço assumido é o P25 de cada segmento (Centro 17,8% vs Morretes 16,2%) e no cruzado Centro@P25 vs
Morretes@mediana (ver `condition_change_scenarios.csv`). Não lidera o cenário central nem os demais
sensíveis ao preço mediano/P75, outliers ou ocupação.

### Condições que mudariam a decisão
Cenários efetivamente calculados (não inventados): a alternativa supera a principal **apenas** em
`conjunto_preco@P25` e `cruzado_centroP25_vs_morretesMediana`. Em preço mediano/P75, outliers e
ocupação 50/60/75% a principal mantém a liderança.

---

## 6. Qualidade dos dados e limitações

- Preparação reproduzível (`build_base.py`, 33 verificações antes de gravar). Auditorias em `outputs/quality/`.
- Diária anunciada ≠ receita; sem ocupação observada.
- Rendimento/payback brutos (sem condomínio, IPTU, manutenção, gestão, impostos, financiamento).
- Preço VivaReal é anunciado, não negociado; ~30% sem condomínio/IPTU.
- Comparação agregada sem chave comum Airbnb–VivaReal.
- Sazonalidade só jan–abr/2025; anualização é extrapolação.
- Concentração por proprietário = risco de representatividade.
- Meia Praia compacto: N principal F3 = 17 < 20 → evidência descritiva.

---

## 7. Reprodução

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts\build_base.py
python scripts\analyze_profile_location.py
python scripts\analyze_investment_efficiency.py
python scripts\analyze_listing_characteristics.py
python scripts\synthesize_recommendation.py
```
Dependências: Python 3.13.5 · pandas 3.0.5 · numpy 2.4.4 (+ `matplotlib` e `Pillow` para a Fase 4).
Cada script aborta sem gravar se uma verificação falhar.

## 8. Conclusão

Morretes·2q é a escolha mais defensável no retrato de jan/2025, mas com vantagem pequena e não
estatisticamente conclusiva; a decisão depende de validação de ocupação, despesas e preço negociado. A tese
dos compactos no Centro não foi sustentada pelos dados.
