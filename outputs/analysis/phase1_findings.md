# Fase 1 — Perfil do imóvel e localização (diária anunciada ajustada)
## 1. Pergunta de negócio
Quais perfis de imóvel e bairros de Itapema apresentam as maiores **diárias anunciadas ajustadas por data e mês**? A tese interna de que apartamentos compactos (0–1 quarto) no Centro teriam diária superior é testada explicitamente. Não há recomendação de compra nesta fase: eficiência do investimento depende também do preço de aquisição (VivaReal), tratado na próxima fase.

## 2. Definição das métricas
**Diária anunciada ajustada por data e mês** — NÃO é receita realizada nem ADR realizado:
1) mediana do preço por (grupo x stay_date);
2) média das medianas diárias dentro de cada mês;
3) média igualmente ponderada dos quatro meses (jan–abr/2025);
4) calculada somente quando os 4 meses estão presentes.

IC 95% por bootstrap reamostrando anúncios (seed 42, 1.000 réplicas, percentis 2,5/97,5), publicado somente com >=950 réplicas válidas. Bairros normalizados (sem acento/caixa); `none`/ausente = 'não informado', fora dos rankings.

## 3. População e cobertura
Inventário: 4.441 anúncios (Details). Precificados e analisados: 999 anúncios, 58.600 pares listing x stay_date. Cobertura por anúncio (n_datas/105): mediana 0.590, min 0.019, p25 0.395, p75 0.733, max 1.000.

## 4. Resultados
### Perfis (4 perfis elegíveis ao ranking; exige >=20 anúncios precificados)
- **3. apartamento (3q+)** (rank 1): diária ajustada **R$ 793** IC95 [R$ 757; R$ 825]; N=464/2127; pares=26621; cobertura mediana 0.581; boot reps válidas 1000/1000.
- **4. casa** (rank 2): diária ajustada **R$ 625** IC95 [R$ 502; R$ 866]; N=70/443; pares=3933; cobertura mediana 0.533; boot reps válidas 1000/1000.
- **2. apartamento (2q)** (rank 3): diária ajustada **R$ 542** IC95 [R$ 522; R$ 565]; N=333/1312; pares=19104; cobertura mediana 0.562; boot reps válidas 1000/1000.
- **1. apartamento compacto (0-1q)** (rank 4): diária ajustada **R$ 507** IC95 [R$ 457; R$ 540]; N=114/271; pares=7960; cobertura mediana 0.714; boot reps válidas 1000/1000.

> `hotel/outros` (N=18) está fora do ranking por ter <20 anúncios precificados. Portanto há **4 perfis elegíveis**.

### Bairros (ranking com >=20 anúncios precificados)
- **meia praia** (rank 1): diária ajustada **R$ 674** IC95 [R$ 651; R$ 704]; N=632/2860; pares=35637; cobertura mediana 0.562.
- **tabuleiro dos oliveiras** (rank 2): diária ajustada **R$ 663** IC95 [R$ 544; R$ 838]; N=20/129; pares=1240; cobertura mediana 0.624.
- **centro** (rank 3): diária ajustada **R$ 616** IC95 [R$ 585; R$ 653]; N=205/657; pares=13429; cobertura mediana 0.686.
- **morretes** (rank 4): diária ajustada **R$ 525** IC95 [R$ 482; R$ 582]; N=83/441; pares=4667; cobertura mediana 0.552.

## 5. Estabilidade nos cenários de cobertura
`rank_delta > 0` indica PIORA de posição (queda no ranking) em relação ao cenário 'todos'.

### todos
- perfil: 3. apartamento (3q+) (N=464 rank 1); 4. casa (N=70 rank 2); 2. apartamento (2q) (N=333 rank 3); 1. apartamento compacto (0-1q) (N=114 rank 4)
- bairro: meia praia (N=632 rank 1); tabuleiro dos oliveiras (N=20 rank 2); centro (N=205 rank 3); morretes (N=83 rank 4)

### cobertura>=25
- perfil: 3. apartamento (3q+) (N=405 rank 1); 4. casa (N=62 rank 2); 2. apartamento (2q) (N=299 rank 3); 1. apartamento compacto (0-1q) (N=108 rank 4)
- bairro: meia praia (N=554 rank 1); centro (N=192 rank 2); morretes (N=71 rank 3)

### cobertura>=50
- perfil: 3. apartamento (3q+) (N=283 rank 1); 4. casa (N=39 rank 2); 2. apartamento (2q) (N=204 rank 3); 1. apartamento compacto (0-1q) (N=96 rank 4)
- bairro: meia praia (N=375 rank 1); centro (N=148 rank 2); morretes (N=52 rank 3)

### cobertura>=75
- perfil: 3. apartamento (3q+) (N=103 rank 1); 2. apartamento (2q) (N=60 rank 2); 1. apartamento compacto (0-1q) (N=44 rank 3)
- bairro: meia praia (N=120 rank 1); centro (N=68 rank 2)

## 6. Resultado da hipótese (compactos 0–1q no Centro)
- **A: compactos Centro vs compactos fora do Centro**: compactos Centro R$ 506 (N=78) vs compactos fora do Centro R$ 502 (N=36); diferença R$ 3 (0.6%); CI95 dif [R$ -69; R$ 97]; boot valid 1000/1000. **Veredito: inconclusiva (CI cruza zero).**
- **B: compactos Centro vs apt 2q+ no Centro**: compactos Centro R$ 506 (N=78) vs apt 2q+ no Centro R$ 747 (N=115); diferença R$ -241 (-32.3%); CI95 dif [R$ -306; R$ -166]; boot valid 1000/1000. **Veredito: rejeitada.**

**Veredito consolidado:**
- Comparação A (vs compactos fora do Centro): **inconclusiva** — o IC da diferença cruza zero.
- Comparação B (vs apt 2q+ no Centro): **rejeitada** — todo o IC é negativo (compactos têm MENOR diária).
- Tese geral de diária superior dos compactos no Centro: **não sustentada**.

Nota: 0 quarto pode ser studio OU informação não preenchida; o grupo deve ser interpretado com cautela. Não há linguagem causal nem recomendação de investimento; eficiência depende também do preço de compra.

## 7. Limitações
- Diária anunciada ≠ receita: sem reservas/ocupação observada.
- Amostra precificada = 999/4.441 (22%); cobertura varia por anúncio.
- Snapshots de janeiro/2025; sazonalidade observável apenas jan–abr/2025.
- Diferenças pequenas entre grupos não são evidência conclusiva por ranking.
- Grupos com N<20 precificados fora do ranking principal.
- 0 quarto pode confundir studio x dado ausente.

## 8. Questões para a fase VivaReal
- Quais perfis/bairros de maior diária têm preço de aquisição compatível (R$/m², por bairro/tipo)?
- Condomínio/IPTU estimados (não disponíveis em ~30%) afetam o custo de carregamento?
- Como a sazonalidade jan–abr se estende ao ano antes de qualquer retorno?
- Sensibilidade da eficiência (diária x preço de compra) aos cenários de ocupação.
