"""
tratamento_dados.py
--------------------
Pipeline de preparação de dados do projeto de BI e Analytics — Distribuidora Farmacêutica.
Limpeza -> Padronização -> Tratamento -> Processamento

Entrada:  data/raw/Vendas e Cadastro - Fase 2.xlsx (abas "Cadastro" e "Vendas")
          data/raw/Estoque Fase 2.xlsx (aba "Export")
Saída:    data/processed/dim_produto.csv
          data/processed/fato_vendas.csv
          data/processed/fato_estoque.csv
          data/processed/kpi_produto.csv

Uso: python scripts/tratamento_dados.py   (rode a partir da raiz do repositório)
"""

import pandas as pd
import numpy as np
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def limpar_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(how="all") # remove linhas totalmente vazias
    df = df.drop_duplicates() # remove duplicidade de linha
    df = df.replace({"N/D": np.nan, "-": np.nan, "": np.nan}) # placeholders comuns de sistema legado -> NaN

    text_cols = df.select_dtypes(include="object").columns
    for col in text_cols:
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v) # espaços em branco nas colunas de texto

    if "EAN" in df.columns:
        df["EAN"] = df["EAN"].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "", 1).isdigit() else pd.NA
        ) # EAN deve ser tratado como texto
        df = df.dropna(subset=["EAN"])  # Remove linhas sem EAN válido antes do merge

        if "Data Cadastro Produto" in df.columns:
            df = df.sort_values("Data Cadastro Produto")
        df = df.drop_duplicates(subset="EAN", keep="last")

    return df

def limpar_vendas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(how="all")
    df = df.drop_duplicates()

    if "EAN" in df.columns:
        df["EAN"] = df["EAN"].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "", 1).isdigit() else pd.NA
        )
        df = df.dropna(subset=["EAN"])

    return df

def limpar_estoque(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(how="all")
    df = df.drop_duplicates()

    if "EAN" in df.columns:
        df["EAN"] = df["EAN"].apply(
            lambda x: str(int(x)) if pd.notna(x) and str(x).replace(".", "", 1).isdigit() else pd.NA
        )
    return df

def padronizar_categoricos(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in colunas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper().replace("NAN", pd.NA) # Uppercase + strip em colunas categóricas

    return df

def vendas_wide_para_longo(df_vendas: pd.DataFrame) -> pd.DataFrame:
    id_cols = ["EAN", "Classe terapêutica", "Marca", "Categoria", "Seção", "Produto"]
    id_cols = [c for c in id_cols if c in df_vendas.columns]

    value_cols = [c for c in df_vendas.columns if c not in id_cols]
    # os pares (Unidades, Valor) estão sempre em sequência
    n_meses = len(value_cols) // 2
    datas = pd.date_range("2024-01-01", periods=n_meses, freq="MS")
  # uma linha por (produto, competência)

    registros = []
    for i, competencia in enumerate(datas):
        col_und = value_cols[2 * i]
        col_val = value_cols[2 * i + 1]
        bloco = df_vendas[id_cols + [col_und, col_val]].copy()
        bloco = bloco.rename(columns={col_und: "unidades", col_val: "valor"})
        bloco["competencia"] = competencia
        registros.append(bloco)

    df_longo = pd.concat(registros, ignore_index=True)

    df_longo["unidades"] = pd.to_numeric(df_longo["unidades"], errors="coerce")
    df_longo["valor"] = pd.to_numeric(df_longo["valor"], errors="coerce")

    df_longo = df_longo.rename(columns={
        "EAN": "ean", "Classe terapêutica": "classe_terapeutica", "Marca": "marca",
        "Categoria": "categoria", "Seção": "secao", "Produto": "produto",
    })
    return df_longo


def tratar_outliers_vendas(df_longo: pd.DataFrame) -> pd.DataFrame:
    df = df_longo.copy()
    df["flag_devolucao"] = df["unidades"] < 0
    limite_superior = df["valor"].quantile(0.99)
    df["flag_outlier_valor"] = df["valor"] > limite_superior
    # Tratando outliers como valores muito acima do percentil e marcas fora do padrão

    return df


def unir_vendas_cadastro(df_longo: pd.DataFrame, df_cadastro: pd.DataFrame) -> pd.DataFrame:
    cols_dim = ["EAN", "Fornecedor", "Departamento", "Princípio Ativo", "Molécula"]
    cols_dim = [c for c in cols_dim if c in df_cadastro.columns]
    dim = df_cadastro[cols_dim].rename(columns={"EAN": "ean"})
    # join pela chave EAN

    return df_longo.merge(dim, on="ean", how="left", validate="many_to_one")


def calcular_kpis_produto(df_longo: pd.DataFrame) -> pd.DataFrame:
    g = df_longo.groupby("ean")
    kpi = g.agg(
        unidades_totais=("unidades", "sum"),
        valor_total=("valor", "sum"),
        media_mensal_unidades=("unidades", "mean"),
        media_mensal_valor=("valor", "mean"),
        meses_com_venda=("unidades", lambda s: (s.fillna(0) > 0).sum()),
    ).reset_index()
    # Agrega a série mensal em indicadores por produto

    def crescimento(serie: pd.DataFrame) -> float:
        serie = serie.sort_values("competencia")
        ultimos3 = serie["valor"].tail(3).mean()
        anteriores3 = serie["valor"].tail(6).head(3).mean()
        if anteriores3 in (0, None) or pd.isna(anteriores3):
            return np.nan
        return (ultimos3 - anteriores3) / anteriores3
      # Tendência M3

    crescimento_df = df_longo.groupby("ean").apply(crescimento).reset_index(name="crescimento_trimestral")
    kpi = kpi.merge(crescimento_df, on="ean", how="left")
    return kpi


def montar_fato_estoque(df_estoque: pd.DataFrame) -> pd.DataFrame:
    mapa = {
        "EAN": "ean",
        "Produto": "produto",
        "Filial": "filial",
        "Fornecedor": "fornecedor",
        "Cobertura (semanas)": "cobertura_semanas",
        "Classificação de Estoque": "classificacao_estoque",
        "Nivel Serv Un": "nivel_servico",
        "Estoque Disponível (und)": "estoque_disponivel_und",
        "Total Estoque (R$)": "total_estoque_rs",
        "Excesso (R$)": "excesso_rs",
        "Média de Venda 3M (und)": "media_venda_3m_und",
        "Mkt Share Un": "market_share",
    }
    cols = [c for c in mapa if c in df_estoque.columns]
    return df_estoque[cols].rename(columns=mapa)


def tratar_estoque(df_estoque: pd.DataFrame) -> pd.DataFrame:
    """Garante tipos numéricos nas colunas de estoque antes de montar o fato final."""
    df = df_estoque.copy()
    colunas_numericas = [
        "Estoque Disponível (und)", "Estoque Disponível (R$)",
        "Excesso (R$)", "Excesso (und)", "Cobertura (semanas)",
        "Média de Venda 3M (und)", "Média de Venda 3M (R$)",
    ]
    for c in colunas_numericas:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main_etl():
    # --- carga ---
    cadastro_raw = pd.read_excel("data/raw/Vendas e Cadastro - Fase 2.xlsx", sheet_name="Cadastro")
    vendas_raw = pd.read_excel("data/raw/Vendas e Cadastro - Fase 2.xlsx", sheet_name="Vendas", header=1)
    estoque_raw = pd.read_excel("data/raw/Estoque Fase 2.xlsx", sheet_name="Export")

    # --- 1) limpeza ---
    cadastro = limpar_cadastro(cadastro_raw)
    vendas = limpar_vendas(vendas_raw)
    estoque = limpar_estoque(estoque_raw)

    # --- 2) padronização ---
    cadastro = padronizar_categoricos(cadastro, ["Categoria"])
    vendas = padronizar_categoricos(vendas, ["Categoria"])
    vendas_longo = vendas_wide_para_longo(vendas)

    # --- 3) tratamento ---
    vendas_longo = tratar_outliers_vendas(vendas_longo)
    vendas_longo = unir_vendas_cadastro(vendas_longo, cadastro)
    estoque = tratar_estoque(estoque)

    # --- 4) processamento ---
    kpi_produto = calcular_kpis_produto(vendas_longo)
    fato_estoque = montar_fato_estoque(estoque)

    dim_produto = cadastro.rename(columns={"EAN": "ean"})
    dim_produto.to_csv(PROCESSED_DIR / "dim_produto.csv", index=False)
    vendas_longo.to_csv(PROCESSED_DIR / "fato_vendas.csv", index=False)
    fato_estoque.to_csv(PROCESSED_DIR / "fato_estoque.csv", index=False)
    kpi_produto.to_csv(PROCESSED_DIR / "kpi_produto.csv", index=False)

    return dim_produto, vendas_longo, fato_estoque, kpi_produto


dim_produto, vendas_longo, fato_estoque, kpi_produto = main_etl()

print("dim_produto:", dim_produto.shape)
print("fato_vendas (formato longo):", vendas_longo.shape)
print("fato_estoque:", fato_estoque.shape)
print("kpi_produto:", kpi_produto.shape)

