# outputs/processed/

Os arquivos `.csv` desta pasta são **dados derivados** dos cinco arquivos brutos em `data/`
(`Details_Itapema.csv`, `Hosts_ids_Itapema.csv`, `Mesh_Ids_Data_Itapema.csv`,
`Price_AV_Itapema.csv`, `VivaReal_Itapema.csv`).

**Eles não são versionados** no GitHub por ocuparem aproximadamente **24,5 MB**.

São **totalmente reproduzíveis** com o comando:

```bash
python scripts/build_base.py
```

A ausência desses CSVs no repositório **não representa ausência de dados nem de
resultados** — as saídas e as regras de construção estão documentadas em
`docs/metodologia_dados.md`, e as auditorias em `outputs/quality/`.