"""Vali Transfers | Dashboard analítico para e-commerce de vinhos (Streamlit).

A base padrão (base_dados_Valitransfers_Ltda.csv, na mesma pasta deste arquivo) é carregada
automaticamente. Pela barra lateral dá para analisar outro CSV; se a base padrão não existir,
a tela inicial pede o upload. Os arquivos são lidos em memória e NUNCA são gravados ou alterados.
A lógica de cálculo fica em dados.py; este arquivo cuida apenas da apresentação.

Para rodar:  streamlit run dashboard_valitransfers.py
"""
import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import dados
from dados import brl, inteiro, pct

ARQUIVO_PADRAO = Path(__file__).resolve().parent / "base_dados_Valitransfers_Ltda.csv"
NOME_EMPRESA = "Vali Transfers"
SUBTITULO = "Inteligência comercial: vendas, rótulos, canais e rentabilidade"

st.set_page_config(
    page_title=f"{NOME_EMPRESA} | Inteligência Comercial",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Identidade visual: adega, bordô, ouro de espumante e creme ----------
BG, PANEL, PANEL_HI, LINE_SOLID = "#120A0D", "#1C1015", "#28171D", "#35212A"
LINE, GRID = "rgba(255,238,225,0.08)", "rgba(255,238,225,0.06)"
BORDO, OURO, ROSE, UVA = "#C8385A", "#E2B866", "#E88CA5", "#9A78C4"
FOLHA, COBRE, CORAL = "#8DBA7C", "#E08E5A", "#FF8F7E"
TEXT, MUTED, CINZA = "#F5EBDD", "#BBA99F", "#6E5C58"
PALETA = [BORDO, OURO, UVA, ROSE, FOLHA, COBRE]
ESCALA = [[0, "#7A2338"], [0.6, BORDO], [1, OURO]]
FONTE = "Manrope, 'Segoe UI', system-ui, -apple-system, sans-serif"

# Ícone de taça (SVG embutido, herda a cor do texto).
ICONE_TACA = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.7' "
    "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<path d='M7 3h10l-.5 6a4.5 4.5 0 0 1-9 0L7 3Z'/><path d='M12 13.5V20M8.5 20.5h7'/></svg>"
)

# Pontilhado discreto do fundo (SVG embutido, sem arquivo externo).
PONTILHADO = (
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='26'%3E"
    "%3Ccircle cx='1.5' cy='1.5' r='1' fill='white' fill-opacity='0.07'/%3E%3C/svg%3E\")"
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:wght@600;700;800&display=swap');
:root { color-scheme: dark; }

/* ---- Tipografia: títulos em serifa (rótulo de vinho), números e textos em Manrope ---- */
html, body, .stApp,
.stApp :is(p, h1, h2, h3, h4, label, li, button, input, textarea, td, th),
.stApp [data-testid="stMetricValue"], .stApp [class*="vt-"] {
    font-family: 'Manrope', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.vt-title, .vt-landing-title, .vt-brand b {
    font-family: 'Playfair Display', Georgia, 'Times New Roman', serif !important;
}
.stApp { font-variant-numeric: tabular-nums; }
::selection { background: rgba(200, 56, 90, .40); }

/* ---- Fundo: adega escura, brilho de bordô, brilho de ouro e pontilhado que some para baixo ---- */
.stApp {
    isolation: isolate; color: __TEXT__; background-color: __BG__;
    background-image:
        radial-gradient(1100px 620px at 6% -8%, rgba(200, 56, 90, .17), transparent 62%),
        radial-gradient(900px 560px at 104% 2%, rgba(226, 184, 102, .08), transparent 58%),
        radial-gradient(900px 600px at 50% 120%, rgba(154, 120, 196, .07), transparent 60%);
    background-attachment: fixed;
}
.stApp::before {
    content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background-image: __PONTILHADO__;
    -webkit-mask-image: linear-gradient(180deg, rgba(0, 0, 0, .95) 0%, rgba(0, 0, 0, 0) 72%);
    mask-image: linear-gradient(180deg, rgba(0, 0, 0, .95) 0%, rgba(0, 0, 0, 0) 72%);
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main { background: transparent; }
header[data-testid="stHeader"] { background: transparent; }
footer, [data-testid="stFooter"] { visibility: hidden; }
.block-container { max-width: 1500px; padding-top: 2.2rem; padding-bottom: 3rem; }

/* ---- Barra lateral ---- */
section[data-testid="stSidebar"] {
    background: rgba(18, 10, 13, .88); -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
    border-right: 1px solid __LINE__;
}
section[data-testid="stSidebar"] > div { background: transparent; }
section[data-testid="stSidebar"] hr { border-color: __LINE__; }
.vt-brand { display: flex; align-items: center; gap: 12px; margin: 2px 0 16px; }
.vt-brand .vt-mark { width: 38px; height: 38px; border-radius: 12px; }
.vt-brand b { display: block; font-size: 1.12rem; letter-spacing: -.01em; color: __TEXT__; }
.vt-brand span { color: __MUTED__; font-size: .8rem; }
.vt-side-box {
    margin-top: 8px; padding: 10px 12px; border-radius: 12px; font-size: .8rem; color: __MUTED__;
    background: rgba(255, 238, 225, .04); border: 1px solid __LINE__; overflow-wrap: anywhere;
}
.vt-side-box b { color: __TEXT__; }

/* ---- Marca (taça) e cabeçalho ---- */
.vt-mark {
    width: 46px; height: 46px; flex: none; display: grid; place-items: center; border-radius: 14px;
    color: __BG__; background: linear-gradient(135deg, __BORDO__, __OURO__);
    box-shadow: 0 8px 24px rgba(200, 56, 90, .30);
}
.vt-mark svg { width: 58%; height: 58%; }
.vt-hero {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
    gap: 16px 28px; margin: 0 0 22px; padding-bottom: 20px; border-bottom: 1px solid __LINE__;
}
.vt-hero-id { display: flex; align-items: center; gap: 16px; }
.vt-title { font-size: 2rem; font-weight: 700; letter-spacing: -.01em; line-height: 1.1; color: __TEXT__; }
.vt-subtitle { margin-top: 4px; font-size: .95rem; color: __MUTED__; }
.vt-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.vt-chip {
    padding: 6px 12px; border-radius: 999px; font-size: .8rem; font-weight: 600; color: __TEXT__;
    background: rgba(255, 238, 225, .05); border: 1px solid __LINE__;
}
.vt-chip-soft { color: __MUTED__; font-weight: 500; }

/* ---- Tela inicial (antes do upload) ---- */
.vt-landing { max-width: 760px; margin: 5vh auto 22px; text-align: center; }
.vt-landing .vt-mark { width: 68px; height: 68px; margin: 0 auto 20px; border-radius: 20px; }
.vt-landing-title { font-size: 2.6rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.1; color: __TEXT__; }
.vt-landing-sub { margin: 10px 0 0; font-size: 1.05rem; color: __MUTED__; }
.vt-landing-note { margin: 18px auto 0; max-width: 560px; font-size: .92rem; line-height: 1.55; color: __MUTED__; }
.vt-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; max-width: 760px; margin: 26px auto 0; }
.vt-step { padding: 14px 16px; border-radius: 14px; text-align: left; background: rgba(28, 16, 21, .8); border: 1px solid __LINE__; }
.vt-step b { display: block; margin-bottom: 4px; font-size: .9rem; color: __OURO__; }
.vt-step span { font-size: .84rem; line-height: 1.45; color: __MUTED__; }

/* ---- Indicadores principais ---- */
.vt-kpis { display: grid; grid-template-columns: 1.6fr 1.2fr 1fr 1fr; gap: 14px; }
.vt-kpi {
    position: relative; display: flex; flex-direction: column; gap: 6px; overflow: hidden;
    min-height: 128px; padding: 18px 20px 16px; border-radius: 18px;
    background: linear-gradient(160deg, rgba(40, 23, 29, .92), rgba(28, 16, 21, .92));
}
.vt-kpi-hero { min-height: 150px; }
.vt-kpi-label { display: flex; align-items: center; gap: 8px; font-size: .84rem; font-weight: 600; color: __MUTED__; }
.vt-kpi-label i { flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--cor); }
.vt-kpi-value {
    font-size: clamp(1.3rem, 1.75vw, 1.7rem); font-weight: 800; letter-spacing: -.02em; line-height: 1.15;
    color: __TEXT__; overflow-wrap: anywhere;
}
.vt-kpi-hero .vt-kpi-value { font-size: clamp(1.6rem, 2.1vw, 2.2rem); }
.vt-kpi-sub { font-size: .8rem; color: __MUTED__; }
.vt-chip-ok, .vt-chip-bad, .vt-chip-neutral {
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .78rem; font-weight: 700;
}
.vt-chip-ok { background: rgba(141, 186, 124, .16); color: __FOLHA__; }
.vt-chip-bad { background: rgba(255, 143, 126, .16); color: __CORAL__; }
.vt-chip-neutral { background: rgba(255, 238, 225, .08); color: __MUTED__; }
.vt-spark { display: block; width: 100%; height: 56px; margin-top: auto; }
.has-help { text-decoration: underline dotted rgba(255, 238, 225, .35); text-underline-offset: 3px; cursor: help; }

/* ---- Faixa de indicadores secundários (uma peça só, com divisórias) ---- */
.vt-strip {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; overflow: hidden;
    margin: 14px 0 8px; border-radius: 16px; background: __LINESOLID__; border: 1px solid rgba(226, 184, 102, .20);
}
.vt-cell { padding: 14px 18px; background: __PANEL__; }
.vt-cell-label { font-size: .8rem; font-weight: 600; color: __MUTED__; }
.vt-cell-value { margin-top: 4px; font-size: 1.2rem; font-weight: 700; letter-spacing: -.01em; color: __TEXT__; }
.vt-cell-value.warn { color: __OURO__; }
.vt-note { margin: 8px 2px 0; font-size: .8rem; line-height: 1.5; color: __MUTED__; }

/* ---- Destaques ---- */
.vt-insights { margin: 18px 0 8px; padding: 16px 20px; border-radius: 16px; background: rgba(28, 16, 21, .85); }
.vt-insights-title { margin-bottom: 6px; font-size: .95rem; font-weight: 700; color: __TEXT__; }
.vt-insights ul { margin: 0; padding: 0; list-style: none; columns: 2 340px; column-gap: 36px; }
.vt-insights li {
    position: relative; padding: 5px 0 5px 18px; break-inside: avoid;
    font-size: .92rem; line-height: 1.5; color: __TEXT__;
}
.vt-insights li::before {
    content: ""; position: absolute; left: 0; top: .95em; width: 7px; height: 7px; border-radius: 50%; background: __OURO__;
}

/* ---- Abas e títulos de seção ---- */
div[data-baseweb="tab-list"] { gap: 4px; }
button[data-baseweb="tab"] { height: 46px; padding: 0 16px; color: __MUTED__; }
button[data-baseweb="tab"] p { font-weight: 600; font-size: .95rem; }
button[data-baseweb="tab"][aria-selected="true"] { color: __TEXT__; }
div[data-baseweb="tab-highlight"] { height: 3px; border-radius: 3px; background: __OURO__; }
div[data-baseweb="tab-border"] { background: __LINESOLID__; }
.stApp h3 { font-size: 1.08rem; font-weight: 700; letter-spacing: -.01em; }
[data-testid="stCaptionContainer"] { color: __MUTED__; }

/* ---- Gráficos, tabelas e métricas ---- */
[data-testid="stPlotlyChart"] {
    box-sizing: border-box; padding: 10px 12px 4px; border-radius: 16px; background: rgba(28, 16, 21, .78);
}
[data-testid="stDataFrame"] { overflow: hidden; border-radius: 14px; border: 1px solid __LINE__; }
[data-testid="stMetric"] { padding: 14px 18px; border-radius: 14px; background: __PANEL__; border: 1px solid rgba(226, 184, 102, .20); }
[data-testid="stMetricLabel"] { color: __MUTED__; }
[data-testid="stMetricLabel"] p { font-size: .84rem; font-weight: 600; }
[data-testid="stMetricValue"] { color: __TEXT__; font-size: 1.5rem; font-weight: 800; letter-spacing: -.02em; }
[data-testid="stAlert"] { border-radius: 14px; }

/* ---- Moldura com brilho de ouro: um feixe percorre o contorno sem competir com o conteúdo ---- */
@keyframes vt-brilho-orbita { 0% { background-position: 0% 50%; } 100% { background-position: 300% 50%; } }
.vt-kpi, .vt-insights, [data-testid="stPlotlyChart"] {
    position: relative; isolation: isolate; border: 1px solid rgba(226, 184, 102, .20);
}
.vt-kpi::before, .vt-insights::before, [data-testid="stPlotlyChart"]::before {
    content: ""; position: absolute; inset: -1px; padding: 1px; border-radius: inherit;
    background: linear-gradient(110deg,
        rgba(226, 184, 102, .06) 0%, rgba(226, 184, 102, .06) 34%,
        rgba(255, 233, 180, .95) 44%, rgba(226, 184, 102, .95) 50%,
        rgba(226, 184, 102, .06) 60%, rgba(226, 184, 102, .06) 100%);
    background-size: 300% 100%; animation: vt-brilho-orbita 8s linear infinite;
    pointer-events: none; z-index: 2;
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
}
.vt-kpi:hover, .vt-insights:hover, [data-testid="stPlotlyChart"]:hover {
    border-color: rgba(255, 224, 160, .50); box-shadow: 0 0 18px rgba(226, 184, 102, .10);
}
@media (prefers-reduced-motion: reduce) {
    .vt-kpi::before, .vt-insights::before, [data-testid="stPlotlyChart"]::before {
        animation: none; background: rgba(226, 184, 102, .28);
    }
}

/* ---- Campos de formulário ---- */
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"] {
    border-radius: 10px; background-color: #170D11; border-color: __LINE__;
}
/* Itens selecionados nos filtros: vinho com borda de ouro */
.stApp [data-baseweb="tag"] {
    border-radius: 8px !important; color: __TEXT__ !important;
    background: linear-gradient(135deg, #7E1A33, #A82A47) !important;
    border: 1px solid rgba(226, 184, 102, .45) !important;
}
.stApp [data-baseweb="tag"] * { color: __TEXT__ !important; }
.stApp [data-baseweb="tag"] svg { fill: __TEXT__ !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] svg { color: __OURO__; fill: __OURO__; }
section[data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div,
section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
section[data-testid="stSidebar"] [data-baseweb="base-input"]:focus-within {
    border-color: __OURO__ !important; box-shadow: 0 0 0 1px rgba(226, 184, 102, .40) !important;
}
[data-testid="stFileUploaderDropzone"] { border-radius: 14px; background: #170D11; border: 1px dashed rgba(226, 184, 102, .40); }
[data-testid="stFileUploaderDropzone"]:hover { border-color: __OURO__; background: #1C1015; }
[data-testid="stDownloadButton"] button, .stButton button {
    padding: 8px 18px; border-radius: 10px; font-weight: 700; color: __TEXT__;
    background: rgba(200, 56, 90, .18); border: 1px solid rgba(200, 56, 90, .55);
}
[data-testid="stDownloadButton"] button:hover, .stButton button:hover { background: rgba(200, 56, 90, .34); border-color: __BORDO__; color: __TEXT__; }

/* ---- Rodapé ---- */
.vt-footer {
    display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 24px;
    margin-top: 36px; padding-top: 16px; border-top: 1px solid __LINE__; font-size: .8rem; color: __MUTED__;
}

/* ---- Telas menores ---- */
@media (max-width: 1000px) {
    .vt-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .vt-kpi-hero { grid-column: span 2; }
    .vt-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .vt-steps { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 560px) {
    .vt-kpis { grid-template-columns: minmax(0, 1fr); }
    .vt-kpi-hero { grid-column: span 1; }
    .vt-title { font-size: 1.6rem; }
    .vt-landing-title { font-size: 2rem; }
}
"""

_TOKENS = {
    "__PONTILHADO__": PONTILHADO, "__BG__": BG, "__PANEL__": PANEL, "__LINESOLID__": LINE_SOLID,
    "__LINE__": LINE, "__BORDO__": BORDO, "__OURO__": OURO, "__FOLHA__": FOLHA, "__CORAL__": CORAL,
    "__TEXT__": TEXT, "__MUTED__": MUTED,
}
_css = CSS
for _chave, _valor in _TOKENS.items():
    _css = _css.replace(_chave, _valor)
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)


# ---------- Compatibilidade entre versões do Streamlit ----------
def _versao():
    try:
        return tuple(int(p) for p in st.__version__.split(".")[:2])
    except (ValueError, AttributeError):
        return (0, 0)


# A partir da 1.50 o parâmetro use_container_width foi substituído por width="stretch".
_LARGURA = {"width": "stretch"} if _versao() >= (1, 50) else {"use_container_width": True}


@st.cache_data(show_spinner="Lendo e preparando a base...")
def carregar_base_padrao(caminho: str, modificado_em: float):
    """Lê e prepara a base padrão uma única vez (cache). `modificado_em` invalida o cache
    automaticamente quando o CSV for atualizado no repositório."""
    return dados.carregar(Path(caminho).read_bytes())


# ---------- Componentes visuais ----------
def _h(texto) -> str:
    """Escapa texto para HTML. O '$' vira entidade para o Markdown nunca confundi-lo com fórmula."""
    return html.escape(str(texto)).replace("$", "&#36;")


def grafico(fig, altura=360):
    """Aplica o tema visual comum e desenha o gráfico."""
    tem_titulo = bool(fig.layout.title.text)
    fig.update_layout(
        height=altura, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONTE, size=12), separators=",.",  # vírgula decimal e ponto de milhar
        margin=dict(l=8, r=8, t=58 if tem_titulo else 24, b=8),
        legend=dict(title_text="", bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=12)),
        hoverlabel=dict(bgcolor=PANEL_HI, bordercolor="rgba(255,238,225,0.20)", font=dict(color=TEXT, family=FONTE)),
        uniformtext=dict(minsize=11, mode="hide"),
    )
    if tem_titulo:
        fig.update_layout(title=dict(font=dict(size=14, color=TEXT), x=0, xanchor="left", y=0.96))
    eixo = dict(gridcolor=GRID, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED),
                title_font=dict(color=MUTED, size=12), title_standoff=8)
    fig.update_xaxes(**eixo)
    fig.update_yaxes(**eixo)
    fig.update_traces(marker=dict(line=dict(color=BG, width=2)), selector=dict(type="pie"))
    try:  # cantos arredondados nas barras (plotly recente); versões antigas simplesmente ignoram
        fig.update_layout(barcornerradius=6)
    except ValueError:
        pass
    st.plotly_chart(fig, **_LARGURA)


def centro_rosca(fig, valor, rotulo):
    """Escreve um total no meio de um gráfico de rosca."""
    fig.add_annotation(
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, align="center",
        text=f"<b>{_h(valor)}</b><br><span style='font-size:11px;color:{MUTED}'>{_h(rotulo)}</span>",
        font=dict(size=16, color=TEXT),
    )


def tabela(df, formatos=None, altura=None):
    visual = df.style.format(formatos, na_rep="—") if formatos else df
    extra = {"height": altura} if altura else {}
    st.dataframe(visual, hide_index=True, **_LARGURA, **extra)


def marca(extra_classe=""):
    return f"<div class='vt-mark {extra_classe}'>{ICONE_TACA}</div>"


def cabecalho(inicio, fim, origem):
    st.markdown(
        "<div class='vt-hero'>"
        f"<div class='vt-hero-id'>{marca()}<div>"
        f"<div class='vt-title'>{_h(NOME_EMPRESA)}</div>"
        f"<div class='vt-subtitle'>{_h(SUBTITULO)}</div>"
        "</div></div>"
        "<div class='vt-chips'>"
        f"<span class='vt-chip'>Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}</span>"
        f"<span class='vt-chip'>Fonte: {_h(origem)}</span>"
        "<span class='vt-chip vt-chip-soft'>E-commerce de vinhos</span>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def sparkline(valores, cor):
    """Mini gráfico de linha em SVG para dentro do cartão de faturamento."""
    v = [float(x) for x in valores if pd.notna(x)]
    if len(v) < 2:
        return ""
    largura, altura = 240, 56
    menor, maior = min(v), max(v)
    faixa = (maior - menor) or 1.0
    passo = largura / (len(v) - 1)
    pontos = " ".join(f"{i * passo:.1f},{altura - 4 - (x - menor) / faixa * (altura - 8):.1f}" for i, x in enumerate(v))
    return (
        f"<svg class='vt-spark' viewBox='0 0 {largura} {altura}' preserveAspectRatio='none' aria-hidden='true'>"
        f"<polygon points='0,{altura} {pontos} {largura},{altura}' fill='{cor}' fill-opacity='0.16'/>"
        f"<polyline points='{pontos}' fill='none' stroke='{cor}' stroke-width='2' stroke-linejoin='round' "
        "stroke-linecap='round' vector-effect='non-scaling-stroke'/></svg>"
    )


def card_kpi(rotulo, valor, sub="", ajuda="", cor=BORDO, chip="", chip_classe="vt-chip-ok", extra="", destaque=False):
    classe = "vt-kpi vt-kpi-hero" if destaque else "vt-kpi"
    if ajuda:
        rot = f"<span class='has-help' title='{_h(ajuda)}'>{_h(rotulo)}</span>"
    else:
        rot = f"<span>{_h(rotulo)}</span>"
    partes = [
        f"<div class='{classe}' style='--cor:{cor}'>",
        f"<div class='vt-kpi-label'><i></i>{rot}</div>",
        f"<div class='vt-kpi-value'>{_h(valor).replace(' ', '&nbsp;')}</div>",
    ]
    if chip:
        partes.append(f"<div><span class='{chip_classe}'>{_h(chip)}</span></div>")
    if sub:
        partes.append(f"<div class='vt-kpi-sub'>{_h(sub)}</div>")
    partes += [extra, "</div>"]
    return "".join(partes)


def _sem_quebra_no_rs(texto) -> str:
    """HTML do valor com 'R$' colado ao número (não quebra linha entre os dois)."""
    return _h(texto).replace("R&#36; ", "R&#36;&nbsp;")


def faixa_kpis(itens):
    """Indicadores secundários numa única faixa. Cada item: (rótulo, valor, ajuda, tom)."""
    celulas = []
    for rotulo, valor, ajuda, tom in itens:
        if ajuda:
            rot = f"<span class='has-help' title='{_h(ajuda)}'>{_h(rotulo)}</span>"
        else:
            rot = f"<span>{_h(rotulo)}</span>"
        celulas.append(
            f"<div class='vt-cell'><div class='vt-cell-label'>{rot}</div>"
            f"<div class='vt-cell-value {tom}'>{_sem_quebra_no_rs(valor)}</div></div>"
        )
    return "<div class='vt-strip'>" + "".join(celulas) + "</div>"


# ======================================================================================
# PORTÃO DE UPLOAD: sem arquivo carregado, nada além desta tela é exibido.
# ======================================================================================
def tela_inicial():
    st.markdown(
        "<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
        "[data-testid='collapsedControl'] { display: none; }</style>"
        f"<div class='vt-landing'>{marca()}"
        f"<div class='vt-landing-title'>{_h(NOME_EMPRESA)}</div>"
        f"<div class='vt-landing-sub'>{_h(SUBTITULO)}</div>"
        "<p class='vt-landing-note'>A base padrão não foi encontrada. Envie o arquivo CSV de vendas para liberar o painel. "
        "O arquivo é lido apenas em memória "
        "durante a sessão: não é gravado em disco nem alterado.</p></div>",
        unsafe_allow_html=True,
    )
    _, meio, _ = st.columns([1, 2, 1])
    with meio:
        arquivo = st.file_uploader(
            "Arquivo CSV de vendas", type=["csv"], key="vt_upload",
            help="Exportação da loja, uma linha por item vendido. Aceita separador ';' ou ',' "
                 "e codificação UTF-8 ou Latin-1.",
        )
        if arquivo is not None:
            try:
                with st.spinner("Lendo e preparando a base..."):
                    base = dados.carregar(arquivo.getvalue())
            except Exception as erro:  # noqa: BLE001
                st.error(f"Não foi possível carregar a base. {erro}")
            else:
                if base.empty:
                    st.warning("O arquivo não tem nenhuma linha com data válida. Confira o formato das datas (dd/mm/aaaa).")
                else:
                    st.session_state["vt_df"] = base
                    st.session_state["vt_origem"] = arquivo.name
                    st.rerun()
        with st.expander("Quais colunas o CSV precisa ter?"):
            st.markdown(
                "**Obrigatórias:** " + ", ".join(f"`{c}`" for c in dados.OBRIGATORIAS) + ".\n\n"
                "**Opcionais** (melhoram a análise; se faltarem, o painel usa valores neutros): "
                + ", ".join(f"`{c}`" for c in dados.OPCIONAIS) + ".\n\n"
                "Datas no formato `dd/mm/aaaa`; valores no padrão brasileiro (`94,90`)."
            )
    st.markdown(
        "<div class='vt-steps'>"
        "<div class='vt-step'><b>Faturamento</b><span>Bruto, líquido, ticket médio e variação mês a mês.</span></div>"
        "<div class='vt-step'><b>Rótulos e categorias</b><span>Curva ABC, tintos, brancos, rosés, kits e acessórios.</span></div>"
        "<div class='vt-step'><b>Canais e regiões</b><span>Marketplaces, estados, cancelamentos e notas fiscais.</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()


if "vt_df" not in st.session_state:
    if ARQUIVO_PADRAO.exists():
        try:
            st.session_state["vt_df"] = carregar_base_padrao(str(ARQUIVO_PADRAO), ARQUIVO_PADRAO.stat().st_mtime)
            st.session_state["vt_origem"] = ARQUIVO_PADRAO.name
        except Exception as erro:  # noqa: BLE001
            st.error(f"Não foi possível carregar a base padrão ({ARQUIVO_PADRAO.name}). {erro}")
            tela_inicial()
    else:
        tela_inicial()

df = st.session_state["vt_df"]
origem = st.session_state["vt_origem"]

# ---------- Barra lateral: marca, arquivo e filtros ----------
st.sidebar.markdown(
    f"<div class='vt-brand'>{marca()}<div><b>{_h(NOME_EMPRESA)}</b>"
    "<span>Painel de inteligência comercial</span></div></div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f"<div class='vt-side-box'>Arquivo: <b>{_h(origem)}</b><br>{_h(inteiro(len(df)))} linhas na base</div>",
    unsafe_allow_html=True,
)
with st.sidebar.expander("Usar outro arquivo CSV"):
    novo = st.file_uploader(
        "CSV de vendas", type=["csv"], label_visibility="collapsed",
        key=f"vt_upload_lateral_{st.session_state.get('vt_up_n', 0)}",
        help="Substitui temporariamente a base padrão nesta sessão. O arquivo não é gravado.",
    )
    if novo is not None and st.session_state.get("vt_origem") != novo.name:
        try:
            with st.spinner("Lendo e preparando a base..."):
                nova_base = dados.carregar(novo.getvalue())
        except Exception as erro:  # noqa: BLE001
            st.error(f"Não foi possível carregar a base. {erro}")
        else:
            if nova_base.empty:
                st.warning("O arquivo não tem nenhuma linha com data válida (formato dd/mm/aaaa).")
            else:
                st.session_state["vt_df"] = nova_base
                st.session_state["vt_origem"] = novo.name
                st.rerun()
if origem != ARQUIVO_PADRAO.name and ARQUIVO_PADRAO.exists():
    if st.sidebar.button("Voltar à base padrão", **_LARGURA):
        st.session_state.pop("vt_df", None)
        st.session_state.pop("vt_origem", None)
        st.session_state["vt_up_n"] = st.session_state.get("vt_up_n", 0) + 1  # zera o campo de upload
        st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Filtros")
data_min, data_max = df["Data"].min().date(), df["Data"].max().date()
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

todas_situacoes = [g for g in dados.GRUPOS_SITUACAO if g in set(df["Grupo de situação"])]
padrao_situacoes = [s for s in todas_situacoes if s not in ("Cancelado", "Devolvido/reembolsado")] or todas_situacoes
situacoes = st.sidebar.multiselect(
    "Situação do pedido", todas_situacoes, default=padrao_situacoes,
    help="Agrupa os status da loja: Verificado e Atendido contam como Concluído. Por padrão os cancelados "
         "ficam fora; marque Cancelado para incluí-los nos indicadores.",
)
lojas = sorted(df["Loja virtual"].dropna().unique().tolist())
canais = st.sidebar.multiselect("Canal de venda", lojas, default=lojas)
ufs = sorted(df["Estado"].dropna().unique().tolist())
estados = st.sidebar.multiselect("Estado", ufs, default=ufs)
tipos_lista = [t for t in dados.TIPOS_PRODUTO if t in set(df["Tipo de produto"])]
tipos = st.sidebar.multiselect("Tipo de produto", tipos_lista, default=tipos_lista)
produtos_lista = sorted(df["Descrição"].dropna().unique().tolist())
produtos = st.sidebar.multiselect("Produto", produtos_lista, default=[], placeholder="Todos os produtos")
meta = st.sidebar.number_input(
    "Meta de faturamento do período (R$)", min_value=0.0, value=0.0, step=10000.0,
    help="Opcional. Se informada, aparece o acompanhamento da meta na Visão geral.",
)

f = dados.filtrar(df, inicio, fim, situacoes, canais, estados, produtos, tipos)
# Mesmos filtros, mas com TODAS as situações: necessário para calcular a taxa de cancelamento.
f_todas = dados.filtrar(df, inicio, fim, None, canais, estados, produtos, tipos)

st.sidebar.markdown(
    f"<div class='vt-side-box'><b>{_h(inteiro(len(f)))}</b> linhas e "
    f"<b>{_h(inteiro(f['N° do Pedido'].nunique()))}</b> pedidos após os filtros</div>",
    unsafe_allow_html=True,
)
if f.empty:
    cabecalho(inicio, fim, origem)
    st.info("Nenhum registro corresponde aos filtros selecionados. Ajuste o período ou os filtros.")
    st.stop()

ind = dados.indicadores(f)
taxa_canc = dados.taxa_cancelamento(f_todas)
# Mesma lógica do DAX (ALLEXCEPT): só canal e situação valem; período, UF, tipo e produto são ignorados.
mom = dados.metricas_mom(df, canais=canais, situacoes=situacoes)
diaria = dados.serie_diaria(f)


def _mes(aaaa_mm):
    return f"{aaaa_mm[5:7]}/{aaaa_mm[:4]}" if aaaa_mm else "—"


def _classe_mom(v):
    return "vt-chip-ok" if v > 0 else ("vt-chip-bad" if v < 0 else "vt-chip-neutral")


def _mom_cartao(rotulo_var, variacao, atual, anterior):
    """(chip, classe, subtítulo) do cartão. Sem mês anterior na base, não inventa variação."""
    if not mom["tem_anterior"]:
        return ("Sem mês anterior na base", "vt-chip-neutral",
                f"{_mes(mom['mes_atual'])}: {brl(atual)}")
    return (f"{rotulo_var} MoM", _classe_mom(variacao),
            f"Mês atual {brl(atual)} · anterior {brl(anterior)}")


chip_liq, classe_liq, sub_liq = _mom_cartao(mom["rotulo_liquido"], mom["var_liquido"],
                                           mom["liquido_atual"], mom["liquido_anterior"])
chip_bru, classe_bru, sub_bru = _mom_cartao(mom["rotulo_bruto"], mom["var_bruto"],
                                           mom["bruto_atual"], mom["bruto_anterior"])
_sub_mom = f"{_mes(mom['mes_atual'])} vs {_mes(mom['mes_anterior'])}"

# ---------- Cabeçalho e indicadores ----------
cabecalho(inicio, fim, origem)

st.markdown(
    "<div class='vt-kpis'>"
    + card_kpi(
        "Faturamento líquido", brl(ind["faturamento_liquido"]), sub_liq, cor=BORDO, destaque=True,
        chip=chip_liq, chip_classe=classe_liq,
        ajuda="Faturamento bruto menos os descontos do pedido. O frete não entra. O % MoM compara o mês da "
              f"última venda com o mês anterior ({_sub_mom}), respeitando só canal e situação.",
        extra=sparkline(diaria["Média móvel 7 dias"], BORDO) if not diaria.empty else "",
    )
    + card_kpi(
        "Faturamento bruto", brl(ind["faturamento_bruto"]), sub_bru, cor=OURO,
        chip=chip_bru, chip_classe=classe_bru,
        ajuda="Soma de Preço Total (quantidade × valor unitário), antes dos descontos.",
    )
    + card_kpi("Pedidos", inteiro(ind["pedidos"]), "Pedidos distintos no período", cor=UVA)
    + card_kpi("Ticket médio", brl(ind["ticket_medio"]), "Líquido ÷ pedidos", cor=ROSE,
               ajuda="Faturamento líquido ÷ pedidos distintos.")
    + "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    faixa_kpis([
        ("Itens vendidos", inteiro(ind["itens"]), "", ""),
        ("Itens por pedido", f"{ind['itens_por_pedido']:.1f}".replace(".", ","), "", ""),
        ("Cancelados e devolvidos", pct(taxa_canc),
         "Pedidos cancelados ou devolvidos ÷ pedidos totais, nos demais filtros.", ""),
        ("Frete (por pedido)", brl(ind["frete_total"]),
         "Frete é do pedido: conta uma vez por pedido, não por item.", ""),
    ]),
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='vt-note'>Faturamento líquido = Preço Total − descontos do pedido (rateados entre os itens). "
    "O frete não entra no faturamento.</p>",
    unsafe_allow_html=True,
)

frases = dados.destaques(f, f_todas)
if frases:
    itens_html = "".join(f"<li>{_h(frase)}</li>" for frase in frases)
    st.markdown(
        f"<div class='vt-insights'><div class='vt-insights-title'>Destaques do período</div><ul>{itens_html}</ul></div>",
        unsafe_allow_html=True,
    )

aba_geral, aba_produtos, aba_canais, aba_geo, aba_pedidos, aba_dados = st.tabs(
    ["Visão geral", "Produtos", "Canais", "Geografia", "Pedidos e status", "Dados e exportação"]
)

# ======================= VISÃO GERAL =======================
with aba_geral:
    esq, dir_ = st.columns([1.3, 1])
    with esq:
        st.subheader("Evolução diária")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=diaria["Data"], y=diaria["Faturamento"], name="Faturamento do dia", marker_color=BORDO, opacity=0.6,
            customdata=diaria["Pedidos"],
            hovertemplate="%{x|%d/%m}: R$ %{y:,.2f}<br>%{customdata} pedidos<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=diaria["Data"], y=diaria["Média móvel 7 dias"], name="Média móvel de 7 dias",
            mode="lines", line=dict(color=OURO, width=3)))
        fig.update_yaxes(title="Faturamento líquido", tickprefix="R$ ")
        fig.update_xaxes(tickformat="%d/%m")
        fig.update_layout(legend=dict(orientation="h", y=1.14, x=0), bargap=0.25)
        grafico(fig, 360)
    with dir_:
        st.subheader("Faturamento líquido por canal")
        canal = f.groupby("Loja virtual", as_index=False).agg(Faturamento=("Líquido", "sum"))
        fig = px.pie(canal, names="Loja virtual", values="Faturamento", hole=0.64, color_discrete_sequence=PALETA)
        fig.update_traces(textposition="inside", textinfo="percent", insidetextorientation="horizontal")
        fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.02))
        centro_rosca(fig, brl(ind["faturamento_liquido"]), "líquido")
        grafico(fig, 360)

    esq, dir_ = st.columns([1.3, 1])
    with esq:
        st.subheader("Faturamento acumulado" + (" e meta" if meta > 0 else ""))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=diaria["Data"], y=diaria["Acumulado"], mode="lines", fill="tozeroy",
                                 name="Acumulado", line=dict(color=BORDO, width=3),
                                 fillcolor="rgba(200,56,90,0.16)"))
        if meta > 0:
            fig.add_hline(y=meta, line_dash="dash", line_color=OURO, annotation_text=f"Meta {brl(meta)}",
                          annotation_font_color=OURO)
        fig.update_yaxes(title="Faturamento acumulado", tickprefix="R$ ")
        fig.update_xaxes(tickformat="%d/%m")
        grafico(fig, 320)
    with dir_:
        if meta > 0:
            st.subheader("Meta do período")
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=ind["faturamento_liquido"],
                number=dict(prefix="R$ ", valueformat=",.0f", font=dict(size=34, color=TEXT)),
                gauge=dict(axis=dict(range=[0, max(meta, ind["faturamento_liquido"]) * 1.1], tickcolor=MUTED,
                                     tickfont=dict(color=MUTED)),
                           bar=dict(color=BORDO, thickness=0.7), bgcolor="rgba(255,238,225,0.05)", borderwidth=0,
                           threshold=dict(line=dict(color=OURO, width=3), thickness=0.85, value=meta)),
                title=dict(text=f"{ind['faturamento_liquido'] / meta:.0%} da meta".replace(".", ","),
                           font=dict(size=14, color=MUTED)),
            ))
            grafico(fig, 320)
        else:
            st.subheader("Faturamento por dia da semana")
            sem = dados.por_dia_semana(f)
            fig = px.bar(sem, x="Dia da semana", y="Faturamento médio", color_discrete_sequence=[OURO])
            fig.update_yaxes(tickprefix="R$ ")
            grafico(fig, 320)
    if meta > 0:
        st.subheader("Faturamento por dia da semana")
        sem = dados.por_dia_semana(f)
        fig = px.bar(sem, x="Dia da semana", y="Faturamento médio", color_discrete_sequence=[OURO])
        fig.update_yaxes(tickprefix="R$ ")
        grafico(fig, 280)
    st.caption("Faturamento por dia da semana = média dos dias do período (dias sem venda contam como zero).")

    st.subheader("Mês a mês")
    mensal = dados.resumo_mensal(f)
    tabela(mensal, {"Faturamento bruto": brl, "Faturamento líquido": brl, "Pedidos": inteiro,
                    "MoM líquido": "{:+.1%}", "MoM bruto": "{:+.1%}"})
    st.caption("A tabela segue todos os filtros da barra lateral. Os cartões do topo (MoM) ignoram "
               "período, estado, tipo e produto, como a medida do Power BI. "
               "Com um único mês na base não há variação para calcular.")

# ======================= PRODUTOS =======================
with aba_produtos:
    abc = dados.curva_abc(f)
    st.subheader("Curva ABC: onde está o faturamento")
    if abc.empty:
        st.info("Sem faturamento positivo no recorte.")
    else:
        curto = abc["Descrição"].str.slice(0, 24) + abc["Descrição"].str.len().gt(24).map({True: "…", False: ""})
        abc = abc.assign(Produto=(abc.index + 1).astype(str) + ". " + curto)  # o número evita rótulos repetidos
        cores = abc["Classe"].map({"A": BORDO, "B": OURO, "C": CINZA})
        fig = go.Figure()
        fig.add_trace(go.Bar(x=abc["Produto"], y=abc["Faturamento"], marker_color=cores, name="Faturamento",
                             customdata=abc[["Descrição", "Classe"]],
                             hovertemplate="%{customdata[0]}<br>R$ %{y:,.2f}<br>Classe %{customdata[1]}<extra></extra>"))
        fig.add_trace(go.Scatter(x=abc["Produto"], y=abc["% acumulado"], yaxis="y2", mode="lines+markers",
                                 name="% acumulado", line=dict(color=ROSE, width=2), marker=dict(size=6)))
        fig.add_shape(type="line", xref="paper", x0=0, x1=1, yref="y2", y0=80, y1=80,
                      line=dict(color="rgba(232,140,165,0.45)", width=1, dash="dot"))  # marca dos 80% (classe A)
        fig.update_layout(
            yaxis=dict(title="Faturamento líquido", tickprefix="R$ "),
            yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%", showgrid=False),
            legend=dict(orientation="h", y=1.1, x=0), xaxis=dict(tickangle=-35),
        )
        grafico(fig, 430)
        n_a = int((abc["Classe"] == "A").sum())
        st.caption(f"Classe A (bordô): {n_a} de {len(abc)} produtos somam até 80% do faturamento. "
                   "B (dourado): até 95%. C (cinza): o restante.")

    st.subheader("Vendas por tipo de produto")
    tp = dados.desempenho_tipos(f)
    t1, t2 = st.columns(2)
    with t1:
        fig = px.pie(tp[tp["Faturamento"] > 0], names="Tipo de produto", values="Faturamento", hole=0.62,
                     color="Tipo de produto", color_discrete_map={
                         "Tinto": BORDO, "Branco": OURO, "Rosé": ROSE, "Espumante": UVA,
                         "Kits e presentes": FOLHA, "Acessórios": COBRE, "Outros": CINZA},
                     title="Faturamento líquido por tipo")
        fig.update_traces(textposition="inside", textinfo="percent", insidetextorientation="horizontal")
        centro_rosca(fig, brl(ind["faturamento_liquido"]), "líquido")
        grafico(fig, 340)
    with t2:
        fig = px.bar(tp.sort_values("Itens"), x="Itens", y="Tipo de produto", orientation="h",
                     color_discrete_sequence=[OURO], title="Unidades vendidas por tipo", text_auto=".3s")
        fig.update_yaxes(title="")
        fig.update_xaxes(title="Unidades")
        grafico(fig, 340)

    st.subheader("Produtos com maior faturamento")
    n_top = st.slider("Quantidade de produtos", 5, 25, 10, key="top_produtos")
    prod = dados.desempenho_produtos(f)
    top = prod.head(n_top).sort_values("Faturamento")
    fig = px.bar(top, x="Faturamento", y="Descrição", orientation="h", color="Faturamento",
                 color_continuous_scale=ESCALA, text="Faturamento",
                 hover_data=["Código do produto", "Itens", "Pedidos"])
    fig.update_traces(texttemplate="R$ %{x:,.2f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(title="Faturamento líquido", tickprefix="R$ ")
    fig.update_yaxes(title="")
    fig.update_coloraxes(showscale=False)
    grafico(fig, max(380, 34 * len(top)))

    st.subheader("Desempenho por produto")
    st.caption("Margem em branco = produto sem preço de custo informado na base (kits e acessórios).")
    tabela(prod, {"Faturamento": brl, "Custo": brl, "Margem": brl, "Margem %": "{:.1%}",
                  "Itens": inteiro, "Pedidos": inteiro})

# ======================= CANAIS =======================
with aba_canais:
    st.subheader("Comparativo entre canais")
    ch = f.groupby("Loja virtual", as_index=False).agg(
        Faturamento=("Líquido", "sum"), Pedidos=("N° do Pedido", "nunique"), Itens=("Quantidade", "sum"))
    ch["Ticket médio"] = ch["Faturamento"] / ch["Pedidos"].where(ch["Pedidos"] > 0)
    canc = dados.taxa_cancelamento(f_todas, "Loja virtual")[["Loja virtual", "Taxa de cancelamento"]]
    ch = ch.merge(canc, on="Loja virtual", how="left")
    a, b = st.columns(2)
    with a:
        fig = px.bar(ch.sort_values("Faturamento", ascending=False), x="Loja virtual", y="Faturamento",
                     color="Loja virtual", color_discrete_sequence=PALETA, text_auto=".3s",
                     title="Faturamento líquido")
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
    mix = f[f["Descrição"].isin(top10)].groupby(["Descrição", "Loja virtual"], as_index=False)["Líquido"].sum()
    fig = px.bar(mix, x="Líquido", y="Descrição", color="Loja virtual", orientation="h",
                 color_discrete_sequence=PALETA, labels={"Líquido": "Faturamento líquido"})
    fig.update_xaxes(tickprefix="R$ ")
    fig.update_yaxes(title="", categoryorder="total ascending")
    fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
    grafico(fig, 420)
    tabela(ch, {"Faturamento": brl, "Ticket médio": brl, "Itens": inteiro, "Pedidos": inteiro,
                "Taxa de cancelamento": "{:.1%}"})

# ======================= GEOGRAFIA =======================
with aba_geo:
    geo = f.groupby("Estado", as_index=False).agg(
        Faturamento=("Líquido", "sum"), Pedidos=("N° do Pedido", "nunique"), Itens=("Quantidade", "sum"))
    geo = geo.sort_values("Faturamento", ascending=False)
    geo["Latitude"] = geo["Estado"].map(lambda u: dados.CENTROS_UF.get(u, (None, None))[0])
    geo["Longitude"] = geo["Estado"].map(lambda u: dados.CENTROS_UF.get(u, (None, None))[1])
    st.subheader("Mapa de vendas por estado")
    mapa = geo.dropna(subset=["Latitude", "Longitude"])
    if not mapa.empty:
        mapa = mapa.assign(Tamanho=mapa["Faturamento"].clip(lower=0))  # bolha não aceita tamanho negativo
        fig = px.scatter_geo(mapa, lat="Latitude", lon="Longitude", size="Tamanho", hover_name="Estado",
                             hover_data={"Faturamento": ":,.2f", "Pedidos": True, "Tamanho": False,
                                         "Latitude": False, "Longitude": False},
                             color="Faturamento", color_continuous_scale=ESCALA, size_max=45)
        fig.update_geos(scope="south america", fitbounds="locations", bgcolor="rgba(0,0,0,0)",
                        showframe=False, showcoastlines=False, showocean=False,
                        showland=True, landcolor="#24151B",
                        showcountries=True, countrycolor="rgba(255,238,225,0.16)",
                        showsubunits=True, subunitcolor="rgba(255,238,225,0.08)")
        fig.update_traces(marker=dict(line=dict(color="rgba(255,238,225,0.35)", width=1)))
        fig.update_coloraxes(showscale=False)
        grafico(fig, 480)
    esq, dir_ = st.columns([1.1, 1])
    with esq:
        st.subheader("Ranking de estados")
        fig = px.bar(geo.head(15).sort_values("Faturamento"), x="Faturamento", y="Estado", orientation="h",
                     color_discrete_sequence=[OURO])
        fig.update_xaxes(tickprefix="R$ ")
        fig.update_yaxes(title="")
        grafico(fig, 460)
    with dir_:
        st.subheader("Municípios líderes")
        cidades = f.groupby(["Estado", "Município"], as_index=False).agg(
            Faturamento=("Líquido", "sum"), Pedidos=("N° do Pedido", "nunique"))
        tabela(cidades.sort_values("Faturamento", ascending=False).head(20),
               {"Faturamento": brl, "Pedidos": inteiro}, 460)
    tabela(geo.drop(columns=["Latitude", "Longitude"]), {"Faturamento": brl, "Pedidos": inteiro, "Itens": inteiro})

# ======================= PEDIDOS E STATUS =======================
with aba_pedidos:
    po = dados.nivel_pedido(f)
    po_todos = dados.nivel_pedido(f_todas)
    st.subheader("Situação dos pedidos")
    s1, s2 = st.columns(2)
    with s1:
        sit = po_todos.groupby("Situação", as_index=False).agg(Pedidos=("N° do Pedido", "nunique"))
        fig = px.bar(sit, x="Situação", y="Pedidos", color="Situação", color_discrete_sequence=PALETA,
                     text_auto=True, title="Pedidos por situação (inclui cancelados)")
        fig.update_layout(showlegend=False)
        grafico(fig, 330)
    with s2:
        nfe = po.groupby("NFe", as_index=False).agg(Pedidos=("N° do Pedido", "nunique"))
        fig = px.pie(nfe, names="NFe", values="Pedidos", hole=0.6, color_discrete_sequence=PALETA,
                     title="Situação da NF-e (pedidos filtrados)")
        fig.update_traces(textposition="inside", textinfo="percent", insidetextorientation="horizontal")
        centro_rosca(fig, inteiro(po["N° do Pedido"].nunique()), "pedidos")
        grafico(fig, 330)
    p1, p2 = st.columns(2)
    with p1:
        fig = px.histogram(po, x="Itens", nbins=20, color_discrete_sequence=[BORDO], title="Itens por pedido")
        fig.update_yaxes(title="Pedidos")
        fig.update_layout(bargap=0.08)
        grafico(fig, 300)
    with p2:
        frete_uf = po.groupby("Estado", as_index=False).agg(Frete_médio=("Frete", "mean"),
                                                            Pedidos=("N° do Pedido", "nunique"))
        frete_uf = frete_uf[frete_uf["Pedidos"] >= 5].sort_values("Frete_médio", ascending=False).head(12)
        fig = px.bar(frete_uf.sort_values("Frete_médio"), x="Frete_médio", y="Estado", orientation="h",
                     color_discrete_sequence=[COBRE], title="Frete médio por pedido (estados com 5+ pedidos)")
        fig.update_xaxes(tickprefix="R$ ", title="Frete médio")
        fig.update_yaxes(title="")
        grafico(fig, 300)
    st.subheader("Pedidos com maior valor")
    maiores = po.sort_values("Valor", ascending=False).head(100).rename(
        columns={"Canal": "Canal de venda", "Valor": "Valor bruto"})
    tabela(maiores[["N° do Pedido", "Data", "Canal de venda", "Situação", "Itens", "Valor bruto", "Líquido",
                    "Frete", "Município", "Estado"]],
           {"Valor bruto": brl, "Líquido": brl, "Frete": brl, "Data": "{:%d/%m/%Y}", "Itens": inteiro})
    st.caption("Cada linha é um pedido. Frete e desconto são do pedido e não são repetidos por item.")

# ======================= DADOS E EXPORTAÇÃO =======================
with aba_dados:
    st.subheader("Qualidade da base")
    q = dados.qualidade(df)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Linhas na base", inteiro(q["linhas"]))
    q2.metric("Pedidos", inteiro(q["pedidos"]), help="Um pedido pode ter várias linhas (uma por produto).")
    q3.metric("Datas inválidas", inteiro(q["datas_invalidas"]), help="Linhas sem data válida não entram em nenhum cálculo.")
    q4.metric("Pedidos com vários itens", inteiro(q["pedidos_multilinha"]))
    r1, r2, r3 = st.columns(3)
    r1.metric("Linhas idênticas a outra linha", inteiro(q["linhas_identicas"]),
              help="Mesma linha repetida na exportação. Pode ser duplicidade ou o mesmo item lançado duas vezes. Não são removidas.")
    r2.metric("Linhas sem preço de custo", inteiro(q["linhas_sem_custo"]),
              help="Ficam fora do cálculo de margem para não inflar o resultado.")
    r3.metric("Pedidos com desconto negativo", inteiro(q["pedidos_desconto_negativo"]),
              help="Desconto negativo funciona como acréscimo (aumenta o líquido). Vale conferir na origem.")
    if q["pedidos_desconto_maior_que_itens"]:
        st.warning(f"{inteiro(q['pedidos_desconto_maior_que_itens'])} pedidos têm desconto maior que o valor dos itens, "
                   "o que deixa o faturamento líquido deles negativo. Os valores foram mantidos como vieram na base.")
    st.caption("O ID da exportação identifica o pedido e se repete em cada item dele; por isso não é sinal de erro. "
               "Linhas idênticas são apenas sinalizadas: o dashboard não remove nem altera nenhuma linha da base.")

    st.subheader("Registros filtrados")
    mostrar_nomes = st.checkbox("Incluir o nome completo dos contatos (dado pessoal)", value=False,
                                help="Por padrão os nomes ficam mascarados (iniciais), em linha com a LGPD.")
    colunas = [col for col in dados.COLUNAS_EXPORTACAO if col in f.columns]
    saida = f[colunas].copy()
    saida["Quantidade"] = saida["Quantidade"].round().astype("Int64")  # evita "1,0" na exportação
    if not mostrar_nomes:
        saida["Nome do contato"] = saida["Nome do contato"].map(dados.mascarar_nome)
    else:
        st.warning("Os nomes completos estarão visíveis na tabela e no arquivo exportado. Trate-os conforme a LGPD.")
    tabela(saida, None, 440)
    csv_saida = saida.to_csv(index=False, sep=";", decimal=",", date_format="%d/%m/%Y").encode("utf-8-sig")
    st.download_button("Baixar recorte filtrado (CSV)", data=csv_saida,
                       file_name="valitransfers_recorte_filtrado.csv", mime="text/csv")

    st.subheader("Definições dos indicadores")
    st.markdown(
        """
- **Faturamento bruto:** soma de `Preço Total` (quantidade × valor unitário) das linhas que passaram pelos filtros.
- **Faturamento líquido:** bruto − descontos do pedido. O desconto vem uma vez por pedido e é rateado entre os itens,
  proporcional ao valor de cada um; o frete não entra.
- **% MoM:** variação do mês da última venda contra o mês anterior, respeitando só canal e situação.
  Aparece "Sem mês anterior na base" quando o arquivo cobre um único mês.
- **Pedidos:** quantidade de `N° do Pedido` distintos. **Ticket médio:** líquido ÷ pedidos.
- **Frete e descontos:** valores do pedido; contam uma vez por pedido (a base repete o valor em cada item).
- **Taxa de cancelamento:** pedidos cancelados ou devolvidos ÷ pedidos totais, nos demais filtros.
- **Custo e margem bruta estimados:** `Preço de Custo × Quantidade` e `Preço Total − custo`, só nas linhas com custo
  informado. Não equivale a lucro líquido.
- **Tipo de produto:** classificação automática pelo nome (Tinto, Branco, Rosé, Espumante, Kits e presentes, Acessórios).
- **Curva ABC:** produtos ordenados por faturamento líquido; A até 80% acumulado, B até 95%, C o restante.
- **Cancelados:** ficam fora dos indicadores por padrão; podem ser incluídos no filtro de situação.
        """
    )

st.markdown(
    f"<div class='vt-footer'><span>{_h(NOME_EMPRESA)} Ltda.</span>"
    "<span>Arquivo utilizado somente para leitura, em memória.</span></div>",
    unsafe_allow_html=True,
)
