"""Camada de dados do dashboard Vali Transfers (e-commerce de vinhos).

Tudo aqui é pandas puro (sem Streamlit), para poder ser testado.
O CSV de origem é apenas LIDO a partir de bytes em memória: nenhuma função grava,
sobrescreve ou altera arquivos.

Definições (iguais às do modelo Chypps, adaptadas a esta base)
---------------------------------------------------------------
Faturamento bruto   = soma de "Preço Total" (quantidade x valor unitário de cada item)
Faturamento líquido = bruto - descontos do pedido
                      O desconto vem uma vez por pedido na base; aqui ele é RATEADO entre os
                      itens do pedido, proporcionalmente ao valor de cada item. Assim o líquido
                      continua somando certo em qualquer recorte (produto, canal, estado, mês).
                      O frete NÃO entra no faturamento.
Mês atual / anterior e % MoM -> ``metricas_mom`` (só canal e situação restringem o cálculo;
período, UF e produto são ignorados, como no ALLEXCEPT do Power BI).
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, datetime
from typing import Iterable, Optional

import numpy as np
import pandas as pd

NAO_INFORMADO = "Não informado"

# Colunas sem as quais nenhuma medida pode ser calculada.
OBRIGATORIAS = [
    "N° do Pedido", "Data", "Estado", "Situação", "Descrição",
    "Quantidade", "Preço Total", "Loja virtual",
]
# Colunas que enriquecem a análise. Se faltarem, o painel funciona com valores neutros.
OPCIONAIS = [
    "ID", "N° do Pedido na Loja Virtual", "Nome do contato", "Bairro", "Município",
    "Desconto pedido", "Frete", "Valor unitário", "Preço de Custo",
    "Código do produto", "Situação da NFe",
]
# Ordem das colunas na exportação original.
COLUNAS_ORIGINAIS = [
    "ID", "N° do Pedido", "N° do Pedido na Loja Virtual", "Data", "Nome do contato", "Bairro",
    "Município", "Estado", "Desconto pedido", "Frete", "Situação", "Descrição", "Quantidade",
    "Valor unitário", "Preço de Custo", "Preço Total", "Código do produto", "Situação da NFe",
    "Loja virtual",
]
COLUNAS_EXPORTACAO = COLUNAS_ORIGINAIS + ["Tipo de produto", "Grupo de situação", "Líquido"]
NUMERICAS = ["Desconto pedido", "Frete", "Quantidade", "Valor unitário", "Preço de Custo", "Preço Total"]

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
GRUPOS_SITUACAO = ["Concluído", "Em andamento", "Cancelado", "Devolvido/reembolsado"]
TIPOS_PRODUTO = ["Tinto", "Branco", "Rosé", "Espumante", "Kits e presentes", "Acessórios", "Outros"]

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

_NOMES_UF = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
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


def rotulo_mom(variacao) -> str:
    """Texto da variação mensal: 📈 / 📉 / ⚪ + percentual com sinal."""
    try:
        v = float(variacao)
    except (TypeError, ValueError):
        v = 0.0
    if np.isnan(v) or round(v * 100, 2) == 0:
        return "⚪ 0,00%"
    numero = f"{abs(v) * 100:.2f}".replace(".", ",")
    return f"📈 +{numero}%" if v > 0 else f"📉 −{numero}%"


# ----------------------------------------------------------------------------
# Utilidades de limpeza
# ----------------------------------------------------------------------------
def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _chave(nome: str) -> str:
    """Nome de coluna comparável: sem acento, minúsculo, só letras e números ('Nº' e 'N°' viram 'n')."""
    t = unicodedata.normalize("NFKD", str(nome))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").casefold()
    return re.sub(r"[^a-z0-9]", "", t)


_CHAVES_COLUNAS = {_chave(c): c for c in OBRIGATORIAS + OPCIONAIS}
# 'Nº do Pedido' (ordinal) vira 'nodopedido' após a normalização; aceitamos as duas grafias.
_CHAVES_COLUNAS.update({"nodopedido": "N° do Pedido", "numerodopedido": "N° do Pedido",
                        "pedido": "N° do Pedido"})


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
    return pd.to_numeric(s, errors="coerce").astype("float64")


def _texto(serie: pd.Series, padrao: Optional[str] = None) -> pd.Series:
    """Texto limpo (object). Vazio, 'null', 'nan' e 'none' viram ausente (ou `padrao`)."""
    def limpo(x):
        if x is None or (isinstance(x, float) and np.isnan(x)) or x is pd.NaT or x is pd.NA:
            return np.nan if padrao is None else padrao
        t = str(x).strip()
        if t.casefold() in ("", "null", "nan", "none", "nat"):
            return np.nan if padrao is None else padrao
        return t
    return pd.Series([limpo(x) for x in serie], index=serie.index, dtype="object")


def normalizar_uf(serie: pd.Series) -> pd.Series:
    """'São Paulo', 'sao paulo' e 'SP' viram 'SP'. Ausente vira 'Não informado'."""
    def um(valor):
        if valor is None or (isinstance(valor, float) and np.isnan(valor)):
            return NAO_INFORMADO
        t = str(valor).strip()
        if t.casefold() in ("", "null", "nan", "none"):
            return NAO_INFORMADO
        if len(t) == 2 and t.upper() in CENTROS_UF:
            return t.upper()
        return _NOMES_UF.get(_sem_acento(t).casefold(), t)
    return serie.map(um).astype("object")


def grupo_situacao(valor) -> str:
    """Agrupa os textos de status da loja em quatro grupos.

    Verificado e Atendido contam como Concluído; Em andamento e Em aberto seguem em andamento.
    Textos desconhecidos ficam em 'Em andamento' (nunca somem do painel).
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "Em andamento"
    t = _sem_acento(str(valor)).casefold()
    if any(p in t for p in ("reembols", "devolu", "estorn", "chargeback")):
        return "Devolvido/reembolsado"
    if any(p in t for p in ("cancel", "recusad", "nao entregue")):
        return "Cancelado"
    if any(p in t for p in ("atendid", "verificad", "conclu", "entregue", "finalizad", "faturad")):
        return "Concluído"
    return "Em andamento"


def tipo_produto(descricao) -> str:
    """Classifica o produto pelo nome: Tinto, Branco, Rosé, Espumante, Kits e presentes, Acessórios."""
    if descricao is None or (isinstance(descricao, float) and np.isnan(descricao)):
        return "Outros"
    t = _sem_acento(str(descricao)).casefold()
    if re.search(r"\b(kit|combo|box|cesta)\b", t):
        return "Kits e presentes"
    if re.search(r"saca-?rolha|abridor|decanter|aerador|\btacas?\b|suporte|adega|cooler|balde|rolha", t):
        return "Acessórios"
    if re.search(r"espumante|champagne|prosecco|\bbrut\b|\bcava\b|frisante", t):
        return "Espumante"
    if re.search(r"\brose\b", t):
        return "Rosé"
    if re.search(r"\bbranco\b|\bblanc\b", t):
        return "Branco"
    if re.search(r"\btinto\b", t):
        return "Tinto"
    return "Outros"


def parse_datas(serie: pd.Series) -> pd.Series:
    """Datas reais ou texto. Inválidas viram NaT.

    Texto 'aaaa-mm-dd ...' é lido como ISO; qualquer outro texto como 'dd/mm/aaaa [hh:mm:ss]'
    (dia primeiro). Ler ISO com dayfirst trocaria dia e mês, por isso os dois casos são separados.
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    texto = pd.Series(
        [np.nan if (x is None or (isinstance(x, float) and np.isnan(x)) or x is pd.NA)
         else (x.isoformat() if isinstance(x, (pd.Timestamp, datetime, date)) else str(x).strip())
         for x in serie],
        index=serie.index, dtype="object",
    )
    iso = texto.str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    como_iso = pd.to_datetime(texto.where(iso), errors="coerce", format="ISO8601")
    resto = texto.where(~iso & texto.notna())
    como_br = pd.to_datetime(resto, dayfirst=True, errors="coerce", format="mixed")
    return como_iso.fillna(como_br)


# ----------------------------------------------------------------------------
# Leitura do CSV e preparação
# ----------------------------------------------------------------------------
_NULOS = ["null", "NULL", "Null"]


def _padronizar_colunas(bruto: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas conhecidas para o nome padrão (tolera acento, caixa e 'Nº'/'N°')."""
    bruto = bruto.copy()
    bruto.columns = [_CHAVES_COLUNAS.get(_chave(c), str(c).strip()) for c in bruto.columns]
    return bruto.loc[:, ~bruto.columns.duplicated()]


def ler_csv(conteudo: bytes) -> pd.DataFrame:
    """Lê o CSV a partir de bytes. Aceita ';', ',' ou tabulação e UTF-8 ou Latin-1."""
    melhor_faltas: Optional[list[str]] = None
    ultimo: Optional[Exception] = None
    for codificacao in ("utf-8-sig", "latin-1"):
        for sep in (";", ",", "\t"):
            try:
                bruto = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=codificacao,
                                    dtype=str, na_values=_NULOS)
            except Exception as erro:  # noqa: BLE001
                ultimo = erro
                continue
            bruto = _padronizar_colunas(bruto)
            faltas = [c for c in OBRIGATORIAS if c not in bruto.columns]
            if not faltas:
                return bruto
            if melhor_faltas is None or len(faltas) < len(melhor_faltas):
                melhor_faltas = faltas
    if melhor_faltas is not None:
        raise ValueError("O CSV não tem as colunas obrigatórias: " + ", ".join(melhor_faltas) + ".")
    raise ValueError(f"Não foi possível ler o arquivo como CSV. Detalhe: {ultimo}")


def _col(bruto: pd.DataFrame, nome: str) -> pd.Series:
    """Coluna da origem, ou série vazia se a exportação não a traz."""
    if nome in bruto.columns:
        return bruto[nome]
    return pd.Series(np.nan, index=bruto.index, dtype="object")


def preparar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Esquema interno + conversões + colunas derivadas. Devolve uma cópia."""
    bruto = _padronizar_colunas(bruto)
    faltando = [c for c in OBRIGATORIAS if c not in bruto.columns]
    if faltando:
        raise ValueError("O CSV não tem as colunas obrigatórias: " + ", ".join(faltando) + ".")

    bruto = bruto.dropna(how="all").copy()
    posicao = pd.Series(np.arange(1, len(bruto) + 1), index=bruto.index)

    pedido = _texto(bruto["N° do Pedido"])
    pedido = pedido.map(lambda x: x[:-2] if isinstance(x, str) and x.endswith(".0") else x)
    pedido = pedido.where(pedido.notna(), "SEM-" + posicao.astype(str))
    ids = _texto(_col(bruto, "ID"))
    ids = ids.map(lambda x: x[:-2] if isinstance(x, str) and x.endswith(".0") else x)
    ids = ids.where(ids.notna(), posicao.map(lambda i: f"L{i:05d}"))

    df = pd.DataFrame(index=bruto.index)
    df["ID"] = ids
    df["N° do Pedido"] = pedido
    df["N° do Pedido na Loja Virtual"] = _texto(_col(bruto, "N° do Pedido na Loja Virtual"), "")
    df["Data"] = parse_datas(bruto["Data"]).dt.normalize()
    df["Nome do contato"] = _texto(_col(bruto, "Nome do contato"), "")
    df["Bairro"] = _texto(_col(bruto, "Bairro"), NAO_INFORMADO)
    df["Município"] = _texto(_col(bruto, "Município"), NAO_INFORMADO)
    df["Estado"] = normalizar_uf(bruto["Estado"])
    df["Situação"] = _texto(bruto["Situação"], "Sem situação")
    df["Descrição"] = _texto(bruto["Descrição"], "(sem descrição)")
    df["Código do produto"] = _texto(_col(bruto, "Código do produto"), "(sem código)")
    df["Situação da NFe"] = _texto(_col(bruto, "Situação da NFe"), "Sem informação").replace(
        {"Cancelado": "Cancelada"})
    df["Loja virtual"] = _texto(bruto["Loja virtual"], "Sem canal")
    for col in NUMERICAS:
        df[col] = numero_br(_col(bruto, col))

    # Linha sem data válida não entra em nenhuma medida (a contagem fica registrada em attrs).
    validas = df["Data"].notna()
    descartadas = int((~validas).sum())
    df = df[validas].copy()

    df["Preço Total"] = df["Preço Total"].fillna(df["Quantidade"] * df["Valor unitário"])
    # Linha idêntica a outra anterior: possível duplicidade (apenas sinalizada, nunca removida).
    df["Linha idêntica"] = df[COLUNAS_ORIGINAIS].duplicated(keep="first").to_numpy()

    df["Mês"] = df["Data"].dt.strftime("%Y-%m")
    df["Dia da semana"] = df["Data"].dt.dayofweek.map(dict(enumerate(DIAS_SEMANA)))
    df["Grupo de situação"] = df["Situação"].map(grupo_situacao)
    df["Cancelado"] = df["Grupo de situação"].isin(["Cancelado", "Devolvido/reembolsado"])
    df["Tipo de produto"] = df["Descrição"].map(tipo_produto)

    # Desconto do pedido rateado entre os itens, proporcional ao valor de cada item.
    grupo = df.groupby("N° do Pedido")
    total_pedido = grupo["Preço Total"].transform("sum")
    n_itens = grupo["Preço Total"].transform("size")
    peso = np.where(total_pedido != 0, df["Preço Total"] / total_pedido.replace(0, np.nan), 1.0 / n_itens)
    desconto_pedido = grupo["Desconto pedido"].transform("first").fillna(0.0)
    df["Desconto rateado"] = desconto_pedido * pd.Series(peso, index=df.index).fillna(0.0)
    df["Líquido"] = df["Preço Total"].fillna(0.0) - df["Desconto rateado"]

    df["Custo informado"] = df["Preço de Custo"].fillna(0) > 0
    df["Custo total estimado"] = df["Preço de Custo"].fillna(0) * df["Quantidade"].fillna(0)
    # Margem sobre o Preço Total (antes dos descontos): só faz sentido onde há custo informado.
    df["Margem bruta estimada"] = df["Preço Total"].fillna(0) - df["Custo total estimado"]

    df = df.reset_index(drop=True)
    df.attrs["linhas_sem_data"] = descartadas
    return df


def carregar(conteudo: bytes) -> pd.DataFrame:
    """CSV (bytes) -> base pronta para o painel."""
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
    tipos: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Aplica filtros. `None` (ou lista vazia, no caso de produtos) significa 'sem filtro'.

    `situacoes` refere-se ao "Grupo de situação" (Concluído, Em andamento, Cancelado, ...).
    """
    mascara = pd.Series(True, index=df.index)
    if inicio is not None and fim is not None:
        mascara &= df["Data"].dt.date.between(inicio, fim)
    if situacoes is not None:
        mascara &= df["Grupo de situação"].isin(list(situacoes))
    if canais is not None:
        mascara &= df["Loja virtual"].isin(list(canais))
    if estados is not None:
        mascara &= df["Estado"].isin(list(estados))
    if tipos is not None:
        mascara &= df["Tipo de produto"].isin(list(tipos))
    if produtos:
        mascara &= df["Descrição"].isin(list(produtos))
    return df[mascara].copy()


# ----------------------------------------------------------------------------
# Faturamento, mês atual / anterior e % MoM
# ----------------------------------------------------------------------------
def faturamento_bruto(df: pd.DataFrame) -> float:
    """Faturamento bruto = soma de Preço Total."""
    return float(df["Preço Total"].sum())


def faturamento_liquido(df: pd.DataFrame) -> float:
    """Faturamento líquido = bruto - descontos do pedido (rateados nos itens)."""
    return float(df["Líquido"].sum())


def _variacao(atual: float, anterior: float) -> float:
    """DIVIDE((atual - anterior), anterior, 0)."""
    return (atual - anterior) / anterior if anterior else 0.0


def metricas_mom(df: pd.DataFrame, canais: Optional[Iterable[str]] = None,
                 situacoes: Optional[Iterable[str]] = None) -> dict:
    """Mês atual, mês anterior e % MoM (mesma lógica do ALLEXCEPT do Power BI).

    Só o canal e a situação restringem o cálculo; período, UF e produto são ignorados.
    O mês atual é o mês da última venda nesse recorte e o anterior é o mês imediatamente antes.
    Se a base não tiver o mês anterior, `tem_anterior` é False e a variação não deve ser exibida.
    """
    base = filtrar(df, situacoes=situacoes, canais=canais)
    zero = {"mes_atual": None, "mes_anterior": None, "liquido_atual": 0.0, "liquido_anterior": 0.0,
            "bruto_atual": 0.0, "bruto_anterior": 0.0, "var_liquido": 0.0, "var_bruto": 0.0,
            "rotulo_liquido": rotulo_mom(0), "rotulo_bruto": rotulo_mom(0), "tem_anterior": False}
    if base.empty:
        return zero
    maxima = base["Data"].max()
    ant = maxima - pd.DateOffset(months=1)
    cur = base[(base["Data"].dt.year == maxima.year) & (base["Data"].dt.month == maxima.month)]
    pre = base[(base["Data"].dt.year == ant.year) & (base["Data"].dt.month == ant.month)]
    liq_a, liq_p = faturamento_liquido(cur), faturamento_liquido(pre)
    bru_a, bru_p = faturamento_bruto(cur), faturamento_bruto(pre)
    v_liq, v_bru = _variacao(liq_a, liq_p), _variacao(bru_a, bru_p)
    return {
        "mes_atual": f"{maxima:%Y-%m}", "mes_anterior": f"{ant:%Y-%m}",
        "liquido_atual": liq_a, "liquido_anterior": liq_p,
        "bruto_atual": bru_a, "bruto_anterior": bru_p,
        "var_liquido": v_liq, "var_bruto": v_bru,
        "rotulo_liquido": rotulo_mom(v_liq), "rotulo_bruto": rotulo_mom(v_bru),
        "tem_anterior": not pre.empty,
    }


def resumo_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """Bruto, líquido e pedidos por mês, com variação mensal (% MoM)."""
    cols = ["Mês", "Faturamento bruto", "Faturamento líquido", "Pedidos", "MoM líquido", "MoM bruto"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    m = df.groupby("Mês", as_index=False).agg(**{
        "Faturamento bruto": ("Preço Total", "sum"),
        "Faturamento líquido": ("Líquido", "sum"),
        "Pedidos": ("N° do Pedido", "nunique"),
    }).sort_values("Mês").reset_index(drop=True)
    liq, bru = m["Faturamento líquido"].tolist(), m["Faturamento bruto"].tolist()
    m["MoM líquido"] = [np.nan] + [_variacao(a, p) for p, a in zip(liq[:-1], liq[1:])]
    m["MoM bruto"] = [np.nan] + [_variacao(a, p) for p, a in zip(bru[:-1], bru[1:])]
    return m


# ----------------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------------
def nivel_pedido(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por pedido. Frete é do PEDIDO (repetido em cada item na base), por isso entra
    uma única vez por pedido. O desconto é a soma do desconto rateado dos itens do recorte."""
    cols = ["N° do Pedido", "Data", "Canal", "Situação", "Grupo", "NFe", "Município", "Estado",
            "Linhas", "Itens", "Valor", "Líquido", "Frete", "Desconto"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df.groupby("N° do Pedido", as_index=False).agg(
        Data=("Data", "min"), Canal=("Loja virtual", "first"), Situação=("Situação", "first"),
        Grupo=("Grupo de situação", "first"), NFe=("Situação da NFe", "first"),
        Município=("Município", "first"), Estado=("Estado", "first"),
        Linhas=("ID", "size"), Itens=("Quantidade", "sum"), Valor=("Preço Total", "sum"),
        Líquido=("Líquido", "sum"), Frete=("Frete", "first"), Desconto=("Desconto rateado", "sum"),
    )


def indicadores(df: pd.DataFrame) -> dict:
    liquido = faturamento_liquido(df)
    bruto = faturamento_bruto(df)
    pedidos = int(df["N° do Pedido"].nunique())
    itens = float(df["Quantidade"].fillna(0).sum())
    po = nivel_pedido(df)
    com_custo = df[df["Custo informado"]]
    receita_com_custo = float(com_custo["Preço Total"].fillna(0).sum())
    margem = float(com_custo["Margem bruta estimada"].sum())
    frete_informado = po["Frete"].dropna() if pedidos else pd.Series(dtype=float)
    return {
        "faturamento": liquido,
        "faturamento_liquido": liquido,
        "faturamento_bruto": bruto,
        "pedidos": pedidos,
        "itens": itens,
        "ticket_medio": liquido / pedidos if pedidos else 0.0,
        "ticket_medio_bruto": bruto / pedidos if pedidos else 0.0,
        "itens_por_pedido": itens / pedidos if pedidos else 0.0,
        "frete_total": float(po["Frete"].fillna(0).sum()) if pedidos else 0.0,
        "desconto_total": float(po["Desconto"].fillna(0).sum()) if pedidos else 0.0,
        # só entre pedidos com frete informado
        "pct_frete_gratis": float((frete_informado == 0).mean()) if len(frete_informado) else np.nan,
        "custo_estimado": float(com_custo["Custo total estimado"].sum()),
        "margem_bruta": margem,
        "margem_pct": margem / receita_com_custo if receita_com_custo else np.nan,
        "cobertura_custo": receita_com_custo / bruto if bruto else np.nan,
        "nfe_pendentes": int((po["NFe"] == "Pendente").sum()) if pedidos else 0,
    }


def taxa_cancelamento(df: pd.DataFrame, por: Optional[str] = None):
    """Pedidos cancelados ou devolvidos / pedidos totais. `df` deve conter TODAS as situações."""
    if df.empty:
        return float("nan") if por is None else pd.DataFrame(
            columns=[por, "Pedidos", "Cancelados", "Taxa de cancelamento"])
    po = df.groupby("N° do Pedido", as_index=False).agg(
        cancelado=("Cancelado", "max"), grupo=(por, "first") if por else ("Cancelado", "size"))
    if por is None:
        return float(po["cancelado"].mean())
    saida = po.groupby("grupo", as_index=False).agg(Pedidos=("cancelado", "size"), Cancelados=("cancelado", "sum"))
    saida["Taxa de cancelamento"] = saida["Cancelados"] / saida["Pedidos"]
    return saida.rename(columns={"grupo": por})


def serie_diaria(df: pd.DataFrame) -> pd.DataFrame:
    """Faturamento líquido e pedidos por dia, incluindo dias sem venda (zero), com média móvel e acumulado."""
    cols = ["Data", "Faturamento", "Faturamento bruto", "Pedidos", "Média móvel 7 dias", "Acumulado"]
    if df.empty or df["Data"].dropna().empty:
        return pd.DataFrame(columns=cols)
    d = df.groupby("Data").agg(Faturamento=("Líquido", "sum"),
                               **{"Faturamento bruto": ("Preço Total", "sum")},
                               Pedidos=("N° do Pedido", "nunique"))
    d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"), fill_value=0)
    d.index.name = "Data"
    d["Média móvel 7 dias"] = d["Faturamento"].rolling(7, min_periods=1).mean()
    d["Acumulado"] = d["Faturamento"].cumsum()
    return d.reset_index()[cols]


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
    cols = ["Código do produto", "Descrição", "Tipo de produto", "Faturamento", "Itens", "Pedidos",
            "Custo", "Margem", "Margem %"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    p = df.groupby(["Código do produto", "Descrição", "Tipo de produto"], as_index=False).agg(
        Faturamento=("Líquido", "sum"), Itens=("Quantidade", "sum"), Pedidos=("N° do Pedido", "nunique"),
        Receita=("Preço Total", "sum"),
        Custo=("Custo total estimado", "sum"), Margem=("Margem bruta estimada", "sum"),
        Custo_informado=("Custo informado", "all"),
    )
    # Sem custo informado a margem seria 100% (falsa): fica em branco.
    p["Margem"] = p["Margem"].where(p["Custo_informado"])
    p["Margem %"] = np.where((p["Receita"] != 0) & p["Custo_informado"],
                             p["Margem"] / p["Receita"].replace(0, np.nan), np.nan)
    p["Custo"] = p["Custo"].where(p["Custo_informado"])
    return p.drop(columns=["Custo_informado", "Receita"]).sort_values("Faturamento", ascending=False)[cols]


def desempenho_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Faturamento líquido, itens e pedidos por tipo de produto (Tinto, Branco, Rosé, ...)."""
    cols = ["Tipo de produto", "Faturamento", "Itens", "Pedidos"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    t = df.groupby("Tipo de produto", as_index=False).agg(
        Faturamento=("Líquido", "sum"), Itens=("Quantidade", "sum"), Pedidos=("N° do Pedido", "nunique"))
    return t.sort_values("Faturamento", ascending=False)[cols]


def curva_abc(df: pd.DataFrame) -> pd.DataFrame:
    """Curva ABC (Pareto) por produto: A até 80% do faturamento acumulado, B até 95%, C o restante."""
    p = df.groupby("Descrição", as_index=False).agg(Faturamento=("Líquido", "sum"))
    p = p[p["Faturamento"] > 0].sort_values("Faturamento", ascending=False).reset_index(drop=True)
    total = p["Faturamento"].sum()
    if p.empty or total == 0:
        p["% do total"] = pd.Series(dtype=float)
        p["% acumulado"] = pd.Series(dtype=float)
        p["Classe"] = pd.Series(dtype=object)
        return p
    p["% do total"] = p["Faturamento"] / total * 100
    p["% acumulado"] = p["% do total"].cumsum()
    anterior = p["% acumulado"] - p["% do total"]
    p["Classe"] = np.where(anterior < 80, "A", np.where(anterior < 95, "B", "C"))
    return p


def mascarar_nome(nome) -> str:
    """'Ana Júlia Lopes' -> 'A. J. L.' (privacidade por padrão, em linha com a LGPD)."""
    if nome is None or pd.isna(nome):
        return ""
    return " ".join(f"{p[0].upper()}." for p in str(nome).split() if p)


# ----------------------------------------------------------------------------
# Destaques em linguagem simples
# ----------------------------------------------------------------------------
def destaques(df: pd.DataFrame, df_todas_situacoes: Optional[pd.DataFrame] = None) -> list[str]:
    if df.empty:
        return []
    frases: list[str] = []

    diaria = serie_diaria(df)
    if not diaria.empty and diaria["Faturamento"].max() > 0:
        melhor = diaria.loc[diaria["Faturamento"].idxmax()]
        frases.append(f"Melhor dia: {melhor['Data']:%d/%m} ({brl(melhor['Faturamento'])}, "
                      f"{inteiro(melhor['Pedidos'])} pedidos).")

    abc = curva_abc(df)
    if not abc.empty:
        lider = abc.iloc[0]
        n_a = int((abc["Classe"] == "A").sum())
        frases.append(f"Produto líder: {lider['Descrição']} ({pct(lider['% do total'] / 100)} do faturamento). "
                      f"{n_a} de {len(abc)} produtos concentram 80% das vendas (classe A).")

    tipos = desempenho_tipos(df)
    tipos = tipos[tipos["Faturamento"] > 0]
    if not tipos.empty and tipos["Faturamento"].sum() > 0:
        topo = tipos.iloc[0]
        frases.append(f"Categoria que mais vende: {topo['Tipo de produto']} "
                      f"({pct(topo['Faturamento'] / tipos['Faturamento'].sum())} do faturamento).")

    canal = df.groupby("Loja virtual")["Líquido"].sum().sort_values(ascending=False)
    if not canal.empty and canal.sum() > 0:
        frases.append(f"Canal principal: {canal.index[0]} ({pct(canal.iloc[0] / canal.sum())} do faturamento líquido).")

    uf = df.groupby("Estado")["Líquido"].sum().sort_values(ascending=False)
    uf = uf[uf.index != NAO_INFORMADO]
    if not uf.empty and uf.sum() > 0:
        top3 = ", ".join(f"{u} ({pct(v / uf.sum(), 0)})" for u, v in uf.head(3).items())
        frases.append(f"Estados que mais compram: {top3}.")

    if df_todas_situacoes is not None and not df_todas_situacoes.empty:
        t = taxa_cancelamento(df_todas_situacoes)
        frases.append(f"Cancelamentos e devoluções no recorte: {pct(t)} dos pedidos.")
    return frases


def qualidade(df_completo: pd.DataFrame) -> dict:
    """Sinais de qualidade da base. Servem para ALERTAR; nenhuma linha é removida."""
    po = df_completo.groupby("N° do Pedido").agg(
        n=("ID", "size"), valor=("Preço Total", "sum"), desconto=("Desconto rateado", "sum"))
    return {
        "linhas": int(len(df_completo)),
        "pedidos": int(len(po)),
        "datas_invalidas": int(df_completo.attrs.get("linhas_sem_data", 0)),
        "linhas_identicas": int(df_completo["Linha idêntica"].sum()),
        "linhas_sem_custo": int((~df_completo["Custo informado"]).sum()),
        "pedidos_multilinha": int((po["n"] > 1).sum()),
        "uf_nao_informada": int((df_completo["Estado"] == NAO_INFORMADO).sum()),
        # descontos negativos funcionam como acréscimo; desconto maior que os itens zera/negativa o líquido
        "pedidos_desconto_negativo": int((po["desconto"] < 0).sum()),
        "pedidos_desconto_maior_que_itens": int(((po["desconto"] > po["valor"]) & (po["valor"] > 0)).sum()),
    }
