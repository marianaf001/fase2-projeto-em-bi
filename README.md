# Análise de Risco de Estoque — Projeto em BI e Analytics

Projeto acadêmico (PUCRS Online — Business Intelligence e Analytics, Fase 2) para uma
distribuidora farmacêutica fictícia. Identifica produtos em risco de ruptura, excesso de
estoque e baixa movimentação, cruzando dados de vendas, cadastro e estoque, e complementa
o dashboard com uma previsão de demanda gerada por Machine Learning.

> **Nota sobre os dados:** todos os valores de venda (R$/unidades) e de estoque são
> **fictícios**, gerados aleatoriamente a partir da estrutura de um cadastro real de
> produtos. Não representam a operação real de nenhuma empresa.

## Arquitetura

```
Dados brutos → Python + Pandas (limpeza → padronização → tratamento → processamento)
             → Base tratada → Power BI (KPIs + Dashboard)
                            → Python/Colab (Previsão de Demanda)
             → Análise de Risco de Estoque
```

Veja o diagrama completo em [`docs/arquitetura.png`](docs/arquitetura.png).

## Estrutura do repositório

```
projeto-bi-estoque/
├── data/
│   ├── raw/                 # Vendas e Cadastro - Fase 2.xlsx, Estoque Fase 2.xlsx
│   └── processed/           # CSVs gerados pelo pipeline (ver abaixo)
├── scripts/
│   ├── tratamento_dados.py  # ETL: limpeza, padronização, tratamento, processamento
│   └── gerar_dicionario.py  # gera docs/dicionario_dados.xlsx
├── notebooks/
│   ├── analise_exploratoria.ipynb   # mesmo pipeline do script, em células comentadas
│   └── modelo_preditivo.ipynb       # previsão de demanda (Random Forest)
├── powerbi/
│   └── dashboard.pbix       # dashboard publicado
├── docs/
│   ├── dicionario_dados.xlsx
│   └── arquitetura.png
├── README.md
└── requirements.txt
```

## Como rodar

1. **Pré-requisitos:** Python 3.11+, `pip install -r requirements.txt`
2. **ETL:** `python scripts/tratamento_dados.py` (a partir da raiz do repositório) — lê os
   arquivos de `data/raw/` e gera 4 tabelas em `data/processed/`:

| Tabela | Granularidade | Linhas | Descrição |
|---|---|---|---|
| `dim_produto.csv` | 1 linha / produto | ~27,5 mil | Cadastro (marca, fornecedor, curva, categoria etc.) |
| `fato_vendas.csv` | 1 linha / produto / mês | ~301 mil | Série mensal de vendas (jan/2024–jul/2026) |
| `fato_estoque.csv` | 1 linha / produto | ~27 mil | Foto de estoque (cobertura, excesso, classificação de risco) |
| `kpi_produto.csv` | 1 linha / produto | ~9,7 mil | Agregados de venda (giro, crescimento trimestral) |

3. **Dicionário de dados:** `python scripts/gerar_dicionario.py` — gera
   `docs/dicionario_dados.xlsx` com uma aba por tabela (coluna, tipo, % nulos, exemplo,
   descrição de negócio).
4. **Previsão de demanda:** rode `notebooks/modelo_preditivo.ipynb` (Google Colab ou
   Jupyter) depois do ETL — gera `data/processed/previsao_demanda.csv`.
5. **Power BI:** importe os CSVs de `data/processed/` no Power BI Desktop. Veja o modelo
   de relacionamentos abaixo.

## Modelo de dados (Power BI)

Esquema estrela, com `dim_produto` como dimensão central:

| De (1) | Para (N) | Chave |
|---|---|---|
| `dim_produto` | `fato_vendas` | `ean` |
| `dim_produto` | `fato_estoque` | `ean` |
| `dim_produto` | `previsao_demanda` | `ean` |
| `dim_produto` | `kpi_produto` | `ean` (1:1) |
| `Calendario` | `fato_vendas` | `Date` ↔ `competencia` |
| `Calendario` | `previsao_demanda` | `Date` ↔ `competencia` |

**Importante:** ao importar os CSVs no Power BI, force o tipo da coluna `ean` como
**Texto** em todas as tabelas — se ficar como Número, o Power BI trunca ou exibe em
notação científica.

## Metodologia da previsão de demanda

- **Modelo:** Random Forest Regressor (scikit-learn), com features de vendas defasadas
  (lag 1, 2, 3 e 6 meses), médias móveis (3 e 6 meses) e sazonalidade (mês).
- **Baseline de comparação:** média móvel de 3 meses.
- **Validação:** divisão cronológica (não aleatória) — últimos 6 meses como teste.
- **Métricas:** MAE, RMSE, WAPE e sMAPE, comparando modelo vs. baseline.
- **Saída:** previsão recursiva para os 3 meses seguintes ao último mês disponível,
  em `data/processed/previsao_demanda.csv` (colunas: `ean`, `competencia`,
  `previsao_demanda`).

## Indicadores (KPIs) do dashboard

Estoque total, valor do estoque, cobertura média (dias/semanas), SKUs em risco de
ruptura, SKUs em excesso — detalhados no relatório da Fase 2 (seção 1, Métricas para o
negócio proposto) e no dicionário de dados.

## Autoria

Mariana Fonseca da Silva — Projeto em Business Intelligence e Analytics, PUCRS Online.
