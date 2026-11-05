"""Vali Transfers | Dashboard analítico (Streamlit).

A base CSV é consumida SOMENTE PARA LEITURA. Nenhuma rotina grava nela.
A lógica de cálculo fica em dados.py (testada em tests/test_dados.py).
"""
import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import dados
from dados import brl, inteiro, pct

st.set_page_config(
    page_title="Vali Transfers | Inteligência Comercial",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Identidade visual ----------
BG, PANEL = "#10111A", "#191B28"
PURPLE, TEAL, AMBER, ROSE = "#9B7BFF", "#43D9C3", "#FFC857", "#FF6B8A"
TEXT, MUTED = "#F2F1F8", "#A7A5B5"
PALETA = [PURPLE, TEAL, AMBER, ROSE, "#6EA8FE", "#B5E48C"]

st.markdown(
    f"""
    <style>
    :root {{ color-scheme: dark; }}
    .stApp {{ background: linear-gradient(145deg, {BG} 0%, #171426 55%, #101923 100%); color: {TEXT}; }}
    [data-testid="stSidebar"] {{ background: #151522; border-right: 1px solid #29283A; }}
    [data-testid="stMetric"] {{ background: {PANEL}; border: 1px solid #302D46; padding: 14px 16px; border-radius: 14px; }}
    [data-testid="stMetricLabel"] {{ color: {MUTED}; }}
    [data-testid="stMetricValue"] {{ color: {TEXT}; font-size: 1.55rem; }}
    div[data-testid="stTabs"] button {{ font-weight: 600; }}
    .hero h1 {{ letter-spacing: -1px; margin-bottom: 0; }}
    .hero p {{ color: {MUTED}; margin-top: 5px; }}
    .note {{ color: {MUTED}; font-size: 0.84rem; }}
    .destaques {{ background: {PANEL}; border: 1px solid #302D46; border-left: 4px solid {PURPLE};
                  border-radius: 12px; padding: 12px 18px; margin: 8px 0 14px 0; }}
    .destaques li {{ margin: 3px 0; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Compatibilidade entre versões do Streamlit ----------
def _versao():
    try:
        return tuple(int(p) for p in st.__version__.split(".")[:2])
    except ValueError:
        return (0, 0)


# A partir da 1.50 o parâmetro use_container_width foi substituído por width="stretch".
_LARGURA = {"width": "stretch"} if _versao() >= (1, 50) else {"use_container_width": True}


def grafico(fig, altura=360):
    fig.update_layout(
        height=altura, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="Arial"), margin=dict(l=12, r=12, t=30, b=12),
        legend_title_text="", hoverlabel=dict(bgcolor=PANEL, font_color=TEXT),
    )
    st.plotly_chart(fig, **_LARGURA)


def tabela(df, formatos=None, altura=None):
    visual = df.style.format(formatos, na_rep="—") if formatos else df
    extra = {"height": altura} if altura else {}
    st.dataframe(visual, hide_index=True, **_LARGURA, **extra)


# ---------- Carga da base (somente leitura) ----------
@st.cache_data(show_spinner="Lendo e preparando a base...")
def carregar_upload(conteudo: bytes) -> pd.DataFrame:
    return dados.carregar(conteudo)


@st.cache_data(show_spinner="Lendo e preparando a base...")
def carregar_arquivo(caminho: str, modificado_em: float) -> pd.DataFrame:
    # `modificado_em` só invalida o cache se o arquivo for trocado; o arquivo é aberto apenas para leitura.
    return dados.carregar(Path(caminho).read_bytes())


st.sidebar.title("📊 Vali Transfers")
st.sidebar.caption("Painel de inteligência comercial")
caminho_padrao = Path(__file__).resolve().parent / "base_dados_Valitransfers_Ltda.csv"
upload = st.sidebar.file_uploader(
    "Carregar outra exportação CSV", type=["csv"],
    help="A leitura é temporária, em memória. O arquivo original nunca é modificado.",
)
try:
    if upload is not None:
        df = carregar_upload(upload.getvalue())
        origem = upload.name
    elif caminho_padrao.exists():
        df = carregar_arquivo(str(caminho_padrao), caminho_padrao.stat().st_mtime)
        origem = caminho_padrao.name
    else:
        st.warning("Não encontrei o CSV ao lado do dashboard. Envie a exportação no campo da barra lateral.")
        st.stop()
except Exception as erro:  # noqa: BLE001
    st.error(f"Não foi possível carregar a base: {erro}")
    st.stop()

if df.empty:
    st.warning("A base não contém registros.")
    st.stop()

# ---------- Filtros ----------
st.sidebar.divider()
st.sidebar.subheader("Filtros")
datas_validas = df["Data"].dropna()
if datas_validas.empty:
    st.error("A coluna Data não contém datas válidas.")
    st.stop()
data_min, data_max = datas_validas.min().date(), datas_validas.max().date()
selecao = st.sidebar.date_input("Período", value=(data_min, data_max), min_value=data_min, max_value=data_max,
                                format="DD/MM/YYYY")
if isinstance(selecao, (tuple, list)):
    if len(selecao) == 2:
        inicio, fim = selecao
    elif len(selecao) == 1:  # o usuário escolheu só a data inicial: usa aquele dia
        inicio = fim = selecao[0]
    else:
        inicio, fim = data_min, data_max
else:
    inicio = fim = selecao

todas_situacoes = sorted(df["Situação"].dropna().unique().tolist())
padrao_situacoes = [s for s in todas_situacoes if s.casefold() != "cancelado"] or todas_situacoes
situacoes = st.sidebar.multiselect("Situação do pedido", todas_situacoes, default=padrao_situacoes)
lojas = sorted(df["Loja virtual"].dropna().unique().tolist())
canais = st.sidebar.multiselect("Canal de venda", lojas, default=lojas)
ufs = sorted(df["Estado"].dropna().unique().tolist())
estados = st.sidebar.multiselect("Estado", ufs, default=ufs)
produtos_lista = sorted(df["Descrição"].dropna().unique().tolist())
produtos = st.sidebar.multiselect("Produto", produtos_lista, default=[], placeholder="Todos os produtos")
meta = st.sidebar.number_input("Meta de faturamento do período (R$)", min_value=0.0, value=0.0, step=10000.0,
                               help="Opcional. Se informada, aparece o acompanhamento da meta na Visão geral.")

f = dados.filtrar(df, inicio, fim, situacoes, canais, estados, produtos)
# Mesmos filtros, mas com TODAS as situações: necessário para calcular a taxa de cancelamento.
f_todas = dados.filtrar(df, inicio, fim, None, canais, estados, produtos)

st.sidebar.caption(f"{inteiro(len(f))} linhas e {inteiro(f['N° do Pedido'].nunique())} pedidos após os filtros")
if f.empty:
    st.title("📊 Vali Transfers | Inteligência Comercial")
    st.info("Nenhum registro corresponde aos filtros selecionados. Ajuste o período ou os filtros.")
    st.stop()

ind = dados.indicadores(f)
taxa_canc = dados.taxa_cancelamento(f_todas)

# ---------- Cabeçalho e indicadores ----------
st.markdown("<div class='hero'>", unsafe_allow_html=True)
st.title("Vali Transfers | Inteligência Comercial")
st.markdown(f"<p>Visão executiva de vendas, canais, produtos e rentabilidade · Fonte: {origem}</p>",
            unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
st.caption(f"Período analisado: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · Dados simulados e anonimizados")

c = st.columns(6)
c[0].metric("Faturamento", brl(ind["faturamento"]))
c[1].metric("Pedidos", inteiro(ind["pedidos"]))
c[2].metric("Itens vendidos", inteiro(ind["itens"]))
c[3].metric("Ticket médio", brl(ind["ticket_medio"]), help="Faturamento ÷ pedidos distintos.")
c[4].metric("Itens por pedido", f"{ind['itens_por_pedido']:.1f}".replace(".", ","))
c[5].metric("Margem bruta est.", brl(ind["margem_bruta"]), pct(ind["margem_pct"]) if pd.notna(ind["margem_pct"]) else None,
            help="Só considera linhas com custo informado (veja a nota abaixo).")
d = st.columns(6)
d[0].metric("Taxa de cancelamento", pct(taxa_canc), help="Pedidos cancelados ÷ pedidos totais, nos demais filtros.")
d[1].metric("Frete (por pedido)", brl(ind["frete_total"]), help="Frete é do pedido: conta uma vez por pedido, não por item.")
d[2].metric("Pedidos com frete zero", pct(ind["pct_frete_gratis"]))
d[3].metric("Descontos (por pedido)", brl(ind["desconto_total"]))
d[4].metric("NF-e pendentes", inteiro(ind["nfe_pendentes"]), help="Pedidos com nota fiscal em situação 'Pendente'.")
d[5].metric("Cobertura de custo", pct(ind["cobertura_custo"], 0), help="Parcela do faturamento com preço de custo informado.")
st.markdown(
    "<p class='note'>Faturamento = soma de Preço Total das linhas filtradas. Margem e custo são estimativas (Preço de Custo × "
    "Quantidade) calculadas apenas nas linhas com custo informado; não incluem taxas de marketplace, impostos ou despesas.</p>",
    unsafe_allow_html=True,
)

frases = dados.destaques(f, f_todas)
if frases:
    itens_html = "".join(f"<li>{html.escape(frase)}</li>" for frase in frases)
    st.markdown(f"<div class='destaques'><b>Destaques do período</b><ul>{itens_html}</ul></div>", unsafe_allow_html=True)

aba_geral, aba_produtos, aba_canais, aba_geo, aba_pedidos, aba_dados = st.tabs(
    ["Visão geral", "Produtos", "Canais", "Geografia", "Pedidos e status", "Dados e exportação"]
)

# ======================= VISÃO GERAL =======================
with aba_geral:
    diaria = dados.serie_diaria(f)
    esq, dir_ = st.columns([1.3, 1])
    with esq:
        st.subheader("Evolução diária")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=diaria["Data"], y=diaria["Faturamento"], name="Faturamento do dia",
                             marker_color=PURPLE, opacity=0.55,
                             customdata=diaria["Pedidos"], hovertemplate="%{x|%d/%m}: R$ %{y:,.2f}<br>%{customdata} pedidos<extra></extra>"))
        fig.add_trace(go.Scatter(x=diaria["Data"], y=diaria["Média móvel 7 dias"], name="Média móvel de 7 dias",
                                 mode="lines", line=dict(color=TEAL, width=3)))
        fig.update_yaxes(title="Faturamento", tickprefix="R$ ")
        fig.update_xaxes(tickformat="%d/%m")
        fig.update_layout(legend=dict(orientation="h", y=1.12))
        grafico(fig, 360)
    with dir_:
        st.subheader("Faturamento por canal")
        canal = f.groupby("Loja virtual", as_index=False).agg(Faturamento=("Preço Total", "sum"))
        fig = px.pie(canal, names="Loja virtual", values="Faturamento", hole=0.62, color_discrete_sequence=PALETA)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        grafico(fig, 360)

    esq, dir_ = st.columns([1.3, 1])
    with esq:
        st.subheader("Faturamento acumulado" + (" e meta" if meta > 0 else ""))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=diaria["Data"], y=diaria["Acumulado"], mode="lines", fill="tozeroy",
                                 name="Acumulado", line=dict(color=PURPLE, width=3)))
        if meta > 0:
            fig.add_hline(y=meta, line_dash="dash", line_color=AMBER, annotation_text=f"Meta {brl(meta)}",
                          annotation_font_color=AMBER)
        fig.update_yaxes(title="Faturamento acumulado", tickprefix="R$ ")
        fig.update_xaxes(tickformat="%d/%m")
        grafico(fig, 320)
    with dir_:
        if meta > 0:
            st.subheader("Meta do período")
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=ind["faturamento"],
                number=dict(prefix="R$ ", valueformat=",.0f"),
                gauge=dict(axis=dict(range=[0, max(meta, ind["faturamento"]) * 1.1]), bar=dict(color=PURPLE),
                           threshold=dict(line=dict(color=AMBER, width=4), value=meta)),
                title=dict(text=f"{ind['faturamento'] / meta:.0%} da meta".replace(".", ",")),
            ))
            grafico(fig, 320)
        else:
            st.subheader("Faturamento por dia da semana")
            sem = dados.por_dia_semana(f)
            fig = px.bar(sem, x="Dia da semana", y="Faturamento médio", color_discrete_sequence=[TEAL])
            fig.update_yaxes(tickprefix="R$ ")
            grafico(fig, 320)
    if meta > 0:
        st.subheader("Faturamento por dia da semana")
        sem = dados.por_dia_semana(f)
        fig = px.bar(sem, x="Dia da semana", y="Faturamento médio", color_discrete_sequence=[TEAL])
        fig.update_yaxes(tickprefix="R$ ")
        grafico(fig, 280)
    st.caption("Faturamento por dia da semana = média dos dias do período (dias sem venda contam como zero).")

# ======================= PRODUTOS =======================
with aba_produtos:
    abc = dados.curva_abc(f)
    st.subheader("Curva ABC: onde está o faturamento")
    if abc.empty:
        st.info("Sem faturamento positivo no recorte.")
    else:
        curto = abc["Descrição"].str.slice(0, 24) + abc["Descrição"].str.len().gt(24).map({True: "…", False: ""})
        abc = abc.assign(Produto=(abc.index + 1).astype(str) + ". " + curto)  # o número evita rótulos repetidos
        cores = abc["Classe"].map({"A": PURPLE, "B": TEAL, "C": MUTED})
        fig = go.Figure()
        fig.add_trace(go.Bar(x=abc["Produto"], y=abc["Faturamento"], marker_color=cores, name="Faturamento",
                             customdata=abc[["Descrição", "Classe"]],
                             hovertemplate="%{customdata[0]}<br>R$ %{y:,.2f}<br>Classe %{customdata[1]}<extra></extra>"))
        fig.add_trace(go.Scatter(x=abc["Produto"], y=abc["% acumulado"], yaxis="y2", mode="lines+markers",
                                 name="% acumulado", line=dict(color=AMBER, width=2)))
        fig.update_layout(
            yaxis=dict(title="Faturamento", tickprefix="R$ "),
            yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%", showgrid=False),
            legend=dict(orientation="h", y=1.1), xaxis=dict(tickangle=-35),
        )
        grafico(fig, 430)
        n_a = int((abc["Classe"] == "A").sum())
        st.caption(f"Classe A (roxo): {n_a} de {len(abc)} produtos somam até 80% do faturamento. "
                   "B (verde): até 95%. C (cinza): o restante.")

    st.subheader("Produtos com maior faturamento")
    n_top = st.slider("Quantidade de produtos", 5, 25, 10, key="top_produtos")
    prod = dados.desempenho_produtos(f)
    top = prod.head(n_top).sort_values("Faturamento")
    fig = px.bar(top, x="Faturamento", y="Descrição", orientation="h", color="Faturamento",
                 color_continuous_scale="Purples", text="Faturamento",
                 hover_data=["Código do produto", "Itens", "Pedidos"])
    fig.update_traces(texttemplate="R$ %{x:,.2f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(title="Faturamento", tickprefix="R$ ")
    fig.update_yaxes(title="")
    fig.update_coloraxes(showscale=False)
    grafico(fig, max(380, 34 * len(top)))

    st.subheader("Desempenho por produto")
    st.caption("Margem em branco = produto sem preço de custo informado na base (kits e acessórios).")
    tabela(prod, {"Faturamento": brl, "Custo": brl, "Margem": brl, "Margem %": "{:.1%}", "Itens": inteiro, "Pedidos": inteiro})

# ======================= CANAIS =======================
with aba_canais:
    st.subheader("Comparativo entre canais")
    ch = f.groupby("Loja virtual", as_index=False).agg(
        Faturamento=("Preço Total", "sum"), Pedidos=("N° do Pedido", "nunique"), Itens=("Quantidade", "sum"))
    ch["Ticket médio"] = ch["Faturamento"] / ch["Pedidos"].where(ch["Pedidos"] > 0)
    canc = dados.taxa_cancelamento(f_todas, "Loja virtual")[["Loja virtual", "Taxa de cancelamento"]]
    ch = ch.merge(canc, on="Loja virtual", how="left")
    a, b = st.columns(2)
    with a:
        fig = px.bar(ch.sort_values("Faturamento", ascending=False), x="Loja virtual", y="Faturamento",
                     color="Loja virtual", color_discrete_sequence=PALETA, text_auto=".3s", title="Faturamento")
        fig.update_yaxes(tickprefix="R$ ")
        fig.update_layout(showlegend=False)
        grafico(fig, 330)
    with b:
        fig = px.bar(ch, x="Loja virtual", y="Taxa de cancelamento", color="Loja virtual",
                     color_discrete_sequence=PALETA, title="Taxa de cancelamento")
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(showlegend=False)
        grafico(fig, 330)
    st.subheader("Mix de produtos por canal (10 maiores)")
    top10 = dados.desempenho_produtos(f).head(10)["Descrição"].tolist()
    mix = f[f["Descrição"].isin(top10)].groupby(["Descrição", "Loja virtual"], as_index=False)["Preço Total"].sum()
    fig = px.bar(mix, x="Preço Total", y="Descrição", color="Loja virtual", orientation="h",
                 color_discrete_sequence=PALETA, labels={"Preço Total": "Faturamento"})
    fig.update_xaxes(tickprefix="R$ ")
    fig.update_yaxes(title="", categoryorder="total ascending")
    grafico(fig, 420)
    tabela(ch, {"Faturamento": brl, "Ticket médio": brl, "Itens": inteiro, "Pedidos": inteiro, "Taxa de cancelamento": "{:.1%}"})

# ======================= GEOGRAFIA =======================
with aba_geo:
    geo = f.groupby("Estado", as_index=False).agg(
        Faturamento=("Preço Total", "sum"), Pedidos=("N° do Pedido", "nunique"), Itens=("Quantidade", "sum"))
    geo = geo.sort_values("Faturamento", ascending=False)
    geo["Latitude"] = geo["Estado"].map(lambda u: dados.CENTROS_UF.get(u, (None, None))[0])
    geo["Longitude"] = geo["Estado"].map(lambda u: dados.CENTROS_UF.get(u, (None, None))[1])
    st.subheader("Mapa de vendas por estado")
    mapa = geo.dropna(subset=["Latitude", "Longitude"])
    if not mapa.empty:
        fig = px.scatter_geo(mapa, lat="Latitude", lon="Longitude", size="Faturamento", hover_name="Estado",
                             hover_data={"Faturamento": ":,.2f", "Pedidos": True, "Latitude": False, "Longitude": False},
                             color="Faturamento", color_continuous_scale="Purples", size_max=45)
        fig.update_geos(scope="south america", fitbounds="locations", showcountries=True, countrycolor="#3A3950",
                        showland=True, landcolor="#1F2133", showocean=True, oceancolor=BG, bgcolor="rgba(0,0,0,0)")
        fig.update_coloraxes(showscale=False)
        grafico(fig, 480)
    esq, dir_ = st.columns([1.1, 1])
    with esq:
        st.subheader("Ranking de estados")
        fig = px.bar(geo.head(15).sort_values("Faturamento"), x="Faturamento", y="Estado", orientation="h",
                     color_discrete_sequence=[TEAL])
        fig.update_xaxes(tickprefix="R$ ")
        fig.update_yaxes(title="")
        grafico(fig, 460)
    with dir_:
        st.subheader("Municípios líderes")
        cidades = f.groupby(["Estado", "Município"], as_index=False).agg(
            Faturamento=("Preço Total", "sum"), Pedidos=("N° do Pedido", "nunique"))
        tabela(cidades.sort_values("Faturamento", ascending=False).head(20), {"Faturamento": brl, "Pedidos": inteiro}, 460)
    tabela(geo.drop(columns=["Latitude", "Longitude"]), {"Faturamento": brl, "Pedidos": inteiro, "Itens": inteiro})

# ======================= PEDIDOS E STATUS =======================
with aba_pedidos:
    po = dados.nivel_pedido(f)
    po_todos = dados.nivel_pedido(f_todas)
    st.subheader("Situação dos pedidos")
    s1, s2 = st.columns(2)
    with s1:
        sit = po_todos.groupby("Situação", as_index=False).agg(Pedidos=("N° do Pedido", "nunique"))
        fig = px.bar(sit, x="Situação", y="Pedidos", color="Situação", color_discrete_sequence=PALETA, text_auto=True,
                     title="Pedidos por situação (inclui cancelados)")
        fig.update_layout(showlegend=False)
        grafico(fig, 330)
    with s2:
        nfe = po.groupby("NFe", as_index=False).agg(Pedidos=("N° do Pedido", "nunique"))
        fig = px.pie(nfe, names="NFe", values="Pedidos", hole=0.55, color_discrete_sequence=PALETA,
                     title="Situação da NF-e (pedidos filtrados)")
        grafico(fig, 330)
    p1, p2 = st.columns(2)
    with p1:
        fig = px.histogram(po, x="Itens", nbins=20, color_discrete_sequence=[PURPLE], title="Itens por pedido")
        fig.update_yaxes(title="Pedidos")
        grafico(fig, 300)
    with p2:
        frete_uf = po.groupby("Estado", as_index=False).agg(Frete_médio=("Frete", "mean"), Pedidos=("N° do Pedido", "nunique"))
        frete_uf = frete_uf[frete_uf["Pedidos"] >= 5].sort_values("Frete_médio", ascending=False).head(12)
        fig = px.bar(frete_uf.sort_values("Frete_médio"), x="Frete_médio", y="Estado", orientation="h",
                     color_discrete_sequence=[AMBER], title="Frete médio por pedido (estados com 5+ pedidos)")
        fig.update_xaxes(tickprefix="R$ ", title="Frete médio")
        fig.update_yaxes(title="")
        grafico(fig, 300)
    st.subheader("Pedidos com maior valor")
    maiores = po.sort_values("Valor", ascending=False).head(100).rename(columns={"Canal": "Canal de venda"})
    tabela(maiores[["N° do Pedido", "Data", "Canal de venda", "Situação", "Itens", "Valor", "Frete", "Município", "Estado"]],
           {"Valor": brl, "Frete": brl, "Data": "{:%d/%m/%Y}", "Itens": inteiro})
    st.caption("Cada linha é um pedido. Frete e desconto são do pedido e não são repetidos por item.")

# ======================= DADOS E EXPORTAÇÃO =======================
with aba_dados:
    st.subheader("Qualidade da base")
    q = dados.qualidade(df)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Linhas na base", inteiro(q["linhas"]))
    q2.metric("Pedidos", inteiro(q["pedidos"]), help="Um pedido pode ter várias linhas (uma por produto).")
    q3.metric("Datas inválidas", inteiro(q["datas_invalidas"]))
    q4.metric("Pedidos com vários itens", inteiro(q["pedidos_multilinha"]))
    r1, r2 = st.columns(2)
    r1.metric("Linhas idênticas a outra linha", inteiro(q["linhas_identicas"]),
              help="Mesma linha repetida na exportação. Pode ser duplicidade ou o mesmo item lançado duas vezes. Não são removidas.")
    r2.metric("Linhas sem preço de custo", inteiro(q["linhas_sem_custo"]),
              help="Ficam fora do cálculo de margem para não inflar o resultado.")
    st.caption("O ID da exportação identifica o pedido e se repete em cada item dele; por isso não é sinal de erro. "
               "Linhas idênticas são apenas sinalizadas: o dashboard não remove nem altera nenhuma linha da base.")

    st.subheader("Registros filtrados")
    mostrar_nomes = st.checkbox("Incluir o nome completo dos contatos (dado pessoal)", value=False,
                                help="Por padrão os nomes ficam mascarados (iniciais), em linha com a LGPD.")
    colunas = [col for col in dados.COLUNAS_OBRIGATORIAS if col in f.columns]
    saida = f[colunas].copy()
    saida["Quantidade"] = saida["Quantidade"].round().astype("Int64")  # evita "1,0" na exportação
    if not mostrar_nomes:
        saida["Nome do contato"] = saida["Nome do contato"].map(dados.mascarar_nome)
    else:
        st.warning("Os nomes completos estarão visíveis na tabela e no arquivo exportado. Trate-os conforme a LGPD.")
    tabela(saida, None, 440)
    csv_saida = saida.to_csv(index=False, sep=";", decimal=",", date_format="%d/%m/%Y").encode("utf-8-sig")
    st.download_button("⬇️ Baixar recorte filtrado (CSV)", data=csv_saida, file_name="valitransfers_recorte_filtrado.csv",
                       mime="text/csv")

    st.subheader("Definições dos indicadores")
    st.markdown(
        """
- **Faturamento:** soma de `Preço Total` das linhas que passaram pelos filtros.
- **Pedidos:** quantidade de `N° do Pedido` distintos.
- **Ticket médio:** faturamento ÷ pedidos distintos.
- **Itens por pedido:** itens vendidos ÷ pedidos.
- **Frete e descontos:** valores do pedido; contam uma vez por pedido (a base repete o valor em cada item).
- **Taxa de cancelamento:** pedidos cancelados ÷ pedidos totais, considerando os demais filtros (período, canal, estado, produto).
- **Custo e margem bruta estimados:** `Preço de Custo × Quantidade` e `Preço Total − custo`, só nas linhas com custo informado.
  Não equivale a lucro líquido.
- **Curva ABC:** produtos ordenados por faturamento; A até 80% acumulado, B até 95%, C o restante.
- **Cancelados:** ficam fora dos indicadores por padrão; podem ser incluídos no filtro de situação.
        """
    )

st.divider()
st.markdown("<p class='note'>Vali Transfers Ltda · Dashboard analítico · Dados simulados e anonimizados · "
            "Base original utilizada somente para leitura.</p>", unsafe_allow_html=True)
