# Vali Transfers — Dashboard analítico

Painel de inteligência comercial em Streamlit, para dados de vendas exportados de ERP (Bling).
Os dados do projeto são **simulados e anonimizados**.

## Arquivos
- `dashboard.py`: interface (Streamlit).
- `dados.py`: leitura, limpeza e cálculo dos indicadores (pandas puro, sem Streamlit).
- `tests/test_dados.py`: testes automatizados da camada de dados.
- `requirements.txt`: dependências.
- `base_dados_Valitransfers_Ltda.csv`: exportação original. **Mantenha este arquivo ao lado de `dashboard.py`.**

## Como executar
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run dashboard.py
```
Se o CSV estiver em outro local, use **Carregar outra exportação CSV** na barra lateral (processado em memória).

## Como rodar os testes
```bash
python -m unittest discover -s tests -v
```
Com o CSV ao lado do `dashboard.py`, os testes também conferem os totais da base real
(17.881 linhas, 9.357 pedidos, R$ 1.358.754,83 de faturamento bruto) e que o arquivo **não foi alterado**.

## Proteção da base e privacidade
- A base é aberta apenas para leitura; nenhum código grava, sobrescreve ou atualiza o CSV.
- O botão de exportação gera um **novo** arquivo com o recorte filtrado.
- Nomes de contatos aparecem **mascarados** (iniciais) na tabela e na exportação. Só são exibidos se o usuário marcar a opção, com aviso de LGPD.

## Regras dos indicadores
- Cancelados ficam fora por padrão; podem ser incluídos no filtro de situação.
- **Faturamento** = soma de `Preço Total` das linhas selecionadas.
- **Pedidos** = `N° do Pedido` distintos. **Ticket médio** = faturamento ÷ pedidos.
- **Frete e desconto** são do pedido e a base os repete em cada item; por isso contam **uma vez por pedido** (somar por linha inflaria os valores).
- **Taxa de cancelamento** = pedidos cancelados ÷ pedidos totais, nos demais filtros.
- **Margem bruta estimada** = `Preço Total` − (`Preço de Custo` × `Quantidade`), **só nas linhas com custo informado**. Kits e acessórios sem custo na base ficam fora para não inflar a margem. Não é lucro líquido.
- **Curva ABC**: A até 80% do faturamento acumulado, B até 95%, C o restante.
- Valores são lidos no padrão brasileiro (vírgula decimal).

## Qualidade da base (apenas alertas; nada é removido)
- O `ID` da exportação identifica o pedido e se repete em cada item; não indica erro.
- Linhas totalmente idênticas são sinalizadas como possível duplicidade.
- Linhas sem preço de custo são sinalizadas e excluídas só do cálculo de margem.
