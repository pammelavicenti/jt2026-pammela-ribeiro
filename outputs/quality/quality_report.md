# Resumo de qualidade e auditoria

Janela de análise: 105 datas únicas de estadia (06/jan a 20/abr/2025).

## Níveis do Price
- Price deduplicado completo: **1005 anúncios**, **59040 pares**.
- Price analítico (associado ao Details): **999 anúncios**, **58600 pares**.
- Órfãos (sem Details): **6 ids**, **509 linhas brutas** — registrados em `orphans_price.csv`, **excluídos** das análises.

## Cobertura (denominador = 105)
- Full (1.005): mediana 0.59; min 0.02; p25 0.40; p75 0.73; max 1.00
- Analítico (999): mediana 0.59; min 0.02; p25 0.40; p75 0.73; max 1.00
Datas ausentes não são interpretadas como preço zero, reserva ou indisponibilidade.

## VivaReal
- Dedupe: 8329 -> 8293 linhas; todos confirmados como linhas integrais do original.
- IDs duplicados: 36; com qualquer conflito: 1.
- Outlier-pm2: own_iqr em 14 grupos; fallback tipologia em 14; report_only em 29 grupos (29 com N<10).

## Hosts
- Dedupe por owner: 3057 owners, snapshot mais recente. Auditoria em `hosts_snapshot_audit.csv`; linhas alteradas vs regra antiga (snapshot mais antigo): 509; atributos (além de ts) alterados: 1.

## Regra de elegibilidade do Price
- `aq_ts`: timestamp completo, usado para ordenar; `aq_date`: data, usada na elegibilidade.
- Elegibilidade: `aq_date <= stay_date`. Captura no mesmo dia da estadia é elegível por convenção (ver `eligibility_audit.csv`).
