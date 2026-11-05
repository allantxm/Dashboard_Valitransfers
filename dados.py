"""Camada de dados do dashboard Vali Transfers.

Tudo aqui é pandas puro (sem Streamlit), para poder ser testado.
A base CSV é apenas LIDA: nenhuma função grava, sobrescreve ou altera o arquivo de origem.
"""
from __future__ import annotations

import io
from typing import Iterable, Optional

import numpy as np
import pandas as pd

COLUNAS_OBRIGATORIAS = [
    "ID", "N° do Pedido", "Data", "Município", "Estado", "Situação",
    "Descrição", "Quantidade", "Valor unitário", "Preço de Custo",
    "Preço Total", "Loja virtual", "Código do produto", "Frete",
    "Desconto pedido", "Situação da NFe", "Nome do contato", "Bairro",
]
NUMERICAS = ["Desconto pedido", "Frete", "Quantidade", "Valor unitário", "Preço de Custo", "Preço Total"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Centro aproximado de cada UF (latitude, longitude), usado só para o mapa de bolhas.
CENTROS_UF = {
    "AC": (-9.0, -70.5), "AL": (-9.6, -36.8), "AP": (1.4, -51.8), "AM": (-3.9, -63.9),
    "BA": (-12.5, -41.7), "CE": (-5.2, -39.3), "DF": (-15.8, -47.9), "ES": (-19.6, -40.6),
    "GO": (-15.9, -49.8), "MA": (-5.0, -45.3), "MT": (-12.9, -55.9), "MS": (-20.5, -54.5),
    "MG": (-18.5, -44.6), "PA": (-3.8, -52.5), "PB": (-7.1, -36.8), "PR": (-24.6, -51.5),
    "PE": (-8.4, -37.9), "PI": (-7.7, -42.7), "RJ": (-22.2, -42.6), "RN": (-5.8, -36.6),
    "RS": (-29.7, -53.3), "RO": (-10.9, -62.8), "RR": (2.1, -61.4), "SC": (-27.2, -50.4),
    "SP": (-22.2, -48.8), "SE": (-10.6, -37.4), "TO": (-10.2, -48.3),
}


# ----------------------------------------------------------------------------
# Formatação (padrão brasileiro)
# ----------------------------------------------------------------------------
def brl(valor) -> str:
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0
    if np.isnan(valor):
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def inteiro(valor) -> str:
    try:
        return f"{int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def pct(valor, casas: int = 1) -> str:
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(valor):
        return "—"
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


# ----------------------------------------------------------------------------
# Leitura e preparação
# ----------------------------------------------------------------------------
def numero_br(serie: pd.Series) -> pd.Series:
    """Converte texto no padrão brasileiro ('1.234,56', 'R$ 94,9') em número.

    Séries que já são numéricas passam direto.
    """
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").astype("float64")
    s = serie.astype("string").str.strip()
    s = s.str.replace(r"R\$\s*", "", regex=True).str.replace(" ", "", regex=False)
    tem_virgula = s.str.contains(",", na=False)
    s = s.where(~tem_virgula, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    # float64 comum (NaN), e não o tipo anulável do pandas (pd.NA), que não funciona em np.where/np.isnan
    return pd.to_numeric(s, errors="coerce").astype("float64")


def ler_csv(conteudo: bytes) -> pd.DataFrame:
    """Lê o CSV a partir de bytes (somente leitura). Aceita ';' ou ',' e UTF-8 ou Latin-1."""
    ultimo_erro: Optional[Exception] = None
    for codificacao in ("utf-8-sig", "latin-1"):
        for sep in (";", ","):
            try:
                bruto = pd.read_csv(io.BytesIO(conteudo), sep=sep, dtype="string", encoding=codificacao)
            except Exception as erro:  # noqa: BLE001 - tenta a próxima combinação
                ultimo_erro = erro
                continue
            bruto.columns = bruto.columns.astype(str).str.strip()
            if "N° do Pedido" in bruto.columns:
                return bruto
    raise ValueError(f"Não foi possível ler o CSV (esperado separador ';'). Detalhe: {ultimo_erro}")


def preparar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Valida colunas, converte tipos e cria colunas derivadas. Devolve uma cópia."""
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in bruto.columns]
    if faltando:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(faltando))

    df = bruto.copy()
    for col in NUMERICAS:
        df[col] = numero_br(df[col])
    texto = df["Data"].astype("string").str.strip()
    datas = pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce")
    resto = datas.isna() & texto.notna()
    if resto.any():
        datas = datas.where(~resto, pd.to_datetime(texto, dayfirst=True, errors="coerce"))
    df["Data"] = datas
    for col in df.columns:
        if col not in NUMERICAS and col != "Data":
            df[col] = df[col].astype("string").str.strip()

    df["Mês"] = df["Data"].dt.to_period("M").astype("string")
    df["Dia"] = df["Data"].dt.day
    df["Dia da semana"] = df["Data"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
    df["Custo informado"] = df["Preço de Custo"].fillna(0) > 0
    df["Custo total estimado"] = df["Preço de Custo"].fillna(0) * df["Quantidade"].fillna(0)
    df["Margem bruta estimada"] = df["Preço Total"].fillna(0) - df["Custo total estimado"]
    # Linha idêntica a outra anterior: possível duplicidade na exportação (apenas sinalizada, nunca removida).
    df["Linha idêntica"] = bruto.duplicated(keep="first").to_numpy()
    df["Cancelado"] = df["Situação"].fillna("").str.casefold().eq("cancelado")
    return df


def carregar(conteudo: bytes) -> pd.DataFrame:
    return preparar(ler_csv(conteudo))


# ----------------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------------
def filtrar(
    df: pd.DataFrame,
    inicio=None,
    fim=None,
    situacoes: Optional[Iterable[str]] = None,
    canais: Optional[Iterable[str]] = None,
    estados: Optional[Iterable[str]] = None,
    produtos: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Aplica filtros. `None` (ou lista vazia, no caso de produtos) significa 'sem filtro'."""
    mascara = pd.Series(True, index=df.index)
    if inicio is not None and fim is not None:
        datas = df["Data"].dt.date
        mascara &= datas.between(inicio, fim)
    if situacoes is not None:
        mascara &= df["Situação"].isin(list(situacoes))
    if canais is not None:
        mascara &= df["Loja virtual"].isin(list(canais))
    if estados is not None:
        mascara &= df["Estado"].isin(list(estados))
    if produtos:
        mascara &= df["Descrição"].isin(list(produtos))
    return df[mascara].copy()


# ----------------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------------
def nivel_pedido(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por pedido. Frete e desconto são do PEDIDO (repetidos em cada item na base),
    por isso entram uma única vez por pedido e nunca são somados linha a linha."""
    if df.empty:
        return pd.DataFrame(columns=["N° do Pedido", "Data", "Canal", "Situação", "NFe", "Município", "Estado",
                                     "Linhas", "Itens", "Valor", "Frete", "Desconto"])
    return df.groupby("N° do Pedido", as_index=False).agg(
        Data=("Data", "min"), Canal=("Loja virtual", "first"), Situação=("Situação", "first"),
        NFe=("Situação da NFe", "first"), Município=("Município", "first"), Estado=("Estado", "first"),
        Linhas=("ID", "size"), Itens=("Quantidade", "sum"), Valor=("Preço Total", "sum"),
        Frete=("Frete", "first"), Desconto=("Desconto pedido", "first"),
    )


def indicadores(df: pd.DataFrame) -> dict:
    faturamento = float(df["Preço Total"].fillna(0).sum())
    pedidos = int(df["N° do Pedido"].nunique())
    itens = float(df["Quantidade"].fillna(0).sum())
    po = nivel_pedido(df)
    com_custo = df[df["Custo informado"]]
    fat_com_custo = float(com_custo["Preço Total"].fillna(0).sum())
    margem = float(com_custo["Margem bruta estimada"].sum())
    return {
        "faturamento": faturamento,
        "pedidos": pedidos,
        "itens": itens,
        "ticket_medio": faturamento / pedidos if pedidos else 0.0,
        "itens_por_pedido": itens / pedidos if pedidos else 0.0,
        "frete_total": float(po["Frete"].fillna(0).sum()) if pedidos else 0.0,
        "desconto_total": float(po["Desconto"].fillna(0).sum()) if pedidos else 0.0,
        "pct_frete_gratis": float((po["Frete"].fillna(0) == 0).mean()) if pedidos else np.nan,
        "custo_estimado": float(com_custo["Custo total estimado"].sum()),
        "margem_bruta": margem,
        "margem_pct": margem / fat_com_custo if fat_com_custo else np.nan,
        "cobertura_custo": fat_com_custo / faturamento if faturamento else np.nan,
        "nfe_pendentes": int((po["NFe"] == "Pendente").sum()) if pedidos else 0,
    }


def taxa_cancelamento(df: pd.DataFrame, por: Optional[str] = None):
    """Pedidos cancelados / pedidos totais. `df` deve conter TODAS as situações."""
    po = df.groupby("N° do Pedido", as_index=False).agg(
        cancelado=("Cancelado", "max"), grupo=(por, "first") if por else ("Cancelado", "size"))
    if por is None:
        return float(po["cancelado"].mean()) if len(po) else np.nan
    saida = po.groupby("grupo", as_index=False).agg(Pedidos=("cancelado", "size"), Cancelados=("cancelado", "sum"))
    saida["Taxa de cancelamento"] = saida["Cancelados"] / saida["Pedidos"]
    return saida.rename(columns={"grupo": por})


def serie_diaria(df: pd.DataFrame) -> pd.DataFrame:
    """Faturamento e pedidos por dia, incluindo dias sem venda (zero), com média móvel e acumulado."""
    if df.empty or df["Data"].dropna().empty:
        return pd.DataFrame(columns=["Data", "Faturamento", "Pedidos", "Média móvel 7 dias", "Acumulado"])
    d = df.groupby("Data").agg(Faturamento=("Preço Total", "sum"), Pedidos=("N° do Pedido", "nunique"))
    intervalo = pd.date_range(d.index.min(), d.index.max(), freq="D")
    d = d.reindex(intervalo, fill_value=0)
    d.index.name = "Data"
    d["Média móvel 7 dias"] = d["Faturamento"].rolling(7, min_periods=1).mean()
    d["Acumulado"] = d["Faturamento"].cumsum()
    return d.reset_index()


def por_dia_semana(df: pd.DataFrame) -> pd.DataFrame:
    """Faturamento MÉDIO por dia da semana (média dos dias, para não favorecer dias que aparecem mais vezes)."""
    d = serie_diaria(df)
    if d.empty:
        return pd.DataFrame(columns=["Dia da semana", "Faturamento médio"])
    d["Dia da semana"] = d["Data"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
    saida = d.groupby("Dia da semana", as_index=False).agg(**{"Faturamento médio": ("Faturamento", "mean")})
    saida["ordem"] = saida["Dia da semana"].map({n: i for i, n in enumerate(DIAS_SEMANA)})
    return saida.sort_values("ordem").drop(columns="ordem")


def desempenho_produtos(df: pd.DataFrame) -> pd.DataFrame:
    p = df.groupby(["Código do produto", "Descrição"], dropna=False, as_index=False).agg(
        Faturamento=("Preço Total", "sum"), Itens=("Quantidade", "sum"), Pedidos=("N° do Pedido", "nunique"),
        Custo=("Custo total estimado", "sum"), Margem=("Margem bruta estimada", "sum"),
        Custo_informado=("Custo informado", "all"),
    )
    # Sem custo informado a margem seria 100% (falsa): fica em branco.
    p["Margem"] = p["Margem"].where(p["Custo_informado"])
    p["Margem %"] = np.where((p["Faturamento"] != 0) & p["Custo_informado"], p["Margem"] / p["Faturamento"], np.nan)
    p["Custo"] = p["Custo"].where(p["Custo_informado"])
    return p.drop(columns="Custo_informado").sort_values("Faturamento", ascending=False)


def curva_abc(df: pd.DataFrame) -> pd.DataFrame:
    """Curva ABC (Pareto) por produto: A até 80% do faturamento acumulado, B até 95%, C o restante."""
    p = df.groupby("Descrição", as_index=False).agg(Faturamento=("Preço Total", "sum"))
    p = p[p["Faturamento"] > 0].sort_values("Faturamento", ascending=False).reset_index(drop=True)
    total = p["Faturamento"].sum()
    if p.empty or total == 0:
        p["% do total"] = []
        p["% acumulado"] = []
        p["Classe"] = []
        return p
    p["% do total"] = p["Faturamento"] / total * 100
    p["% acumulado"] = p["% do total"].cumsum()
    anterior = p["% acumulado"] - p["% do total"]
    p["Classe"] = np.where(anterior < 80, "A", np.where(anterior < 95, "B", "C"))
    return p


def mascarar_nome(nome) -> str:
    """'Ana Júlia Lopes' -> 'A. J. L.' (privacidade por padrão, em linha com a LGPD)."""
    if nome is None or (isinstance(nome, float) and np.isnan(nome)) or pd.isna(nome):
        return ""
    partes = [p for p in str(nome).split() if p]
    return " ".join(f"{p[0].upper()}." for p in partes)


# ----------------------------------------------------------------------------
# Destaques em linguagem simples (para quem não é da área de dados)
# ----------------------------------------------------------------------------
def destaques(df: pd.DataFrame, df_todas_situacoes: Optional[pd.DataFrame] = None) -> list[str]:
    if df.empty:
        return []
    ind = indicadores(df)
    frases: list[str] = []

    diaria = serie_diaria(df)
    if not diaria.empty and diaria["Faturamento"].max() > 0:
        melhor = diaria.loc[diaria["Faturamento"].idxmax()]
        frases.append(f"Melhor dia: {melhor['Data']:%d/%m} ({brl(melhor['Faturamento'])}, {inteiro(melhor['Pedidos'])} pedidos).")

    abc = curva_abc(df)
    if not abc.empty:
        lider = abc.iloc[0]
        n_a = int((abc["Classe"] == "A").sum())
        frases.append(f"Produto líder: {lider['Descrição']} ({pct(lider['% do total'] / 100)} do faturamento). "
                      f"{n_a} de {len(abc)} produtos concentram 80% das vendas (classe A).")

    canal = df.groupby("Loja virtual")["Preço Total"].sum().sort_values(ascending=False)
    if not canal.empty and canal.sum() > 0:
        frases.append(f"Canal principal: {canal.index[0]} ({pct(canal.iloc[0] / canal.sum())} do faturamento).")

    uf = df.groupby("Estado")["Preço Total"].sum().sort_values(ascending=False)
    if not uf.empty and uf.sum() > 0:
        top3 = ", ".join(f"{u} ({pct(v / uf.sum(), 0)})" for u, v in uf.head(3).items())
        frases.append(f"Estados que mais compram: {top3}.")

    if df_todas_situacoes is not None and not df_todas_situacoes.empty:
        t = taxa_cancelamento(df_todas_situacoes)
        frases.append(f"Taxa de cancelamento no recorte: {pct(t)} dos pedidos.")

    if not np.isnan(ind["pct_frete_gratis"]):
        frases.append(f"{pct(ind['pct_frete_gratis'])} dos pedidos têm frete zero.")
    if ind["nfe_pendentes"]:
        n = ind["nfe_pendentes"]
        frases.append(f"{inteiro(n)} {'pedido está' if n == 1 else 'pedidos estão'} com a nota fiscal pendente.")
    return frases


def qualidade(df_completo: pd.DataFrame) -> dict:
    """Sinais de qualidade da base. Servem para ALERTAR; nenhuma linha é removida."""
    return {
        "linhas": int(len(df_completo)),
        "pedidos": int(df_completo["N° do Pedido"].nunique()),
        "datas_invalidas": int(df_completo["Data"].isna().sum()),
        "linhas_identicas": int(df_completo["Linha idêntica"].sum()),
        "linhas_sem_custo": int((~df_completo["Custo informado"]).sum()),
        "pedidos_multilinha": int((df_completo.groupby("N° do Pedido").size() > 1).sum()),
    }
