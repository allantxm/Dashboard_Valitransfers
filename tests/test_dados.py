"""Testes da camada de dados. Execute na pasta do projeto:

    python -m unittest discover -s tests -v

Os testes com a base real só rodam se o CSV estiver ao lado do dashboard.py
(ou se a variável de ambiente BASE_CSV apontar para ele). A base é aberta somente
para leitura e os testes conferem que o arquivo não foi alterado.
"""
import hashlib
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import dados  # noqa: E402

CABECALHO = ("ID;N° do Pedido;N° do Pedido na Loja Virtual;Data;Nome do contato;Bairro;Município;Estado;"
             "Desconto pedido;Frete;Situação;Descrição;Quantidade;Valor unitário;Preço de Custo;Preço Total;"
             "Código do produto;Situação da NFe;Loja virtual\n")
LINHAS = [
    # Pedido 1: dois itens (frete 10 e desconto 2 repetidos nas duas linhas)
    "1;100;x;01/03/2026;Ana Júlia Lopes;Centro;Santo André;SP;2;10;Verificado;Vinho A;1;100;20;100;A1;Emitida;Bagy",
    "1;100;x;01/03/2026;Ana Júlia Lopes;Centro;Santo André;SP;2;10;Verificado;Suporte B;2;50;0;100;B1;Emitida;Bagy",
    # Pedido 2: cancelado
    "2;101;x;02/03/2026;Bruno Alves;Centro;Curitiba;PR;0;0;Cancelado;Vinho A;1;100;20;100;A1;Cancelado;Shopee",
    # Pedido 3: valores no padrão brasileiro com milhar
    "3;102;x;04/03/2026;Carla Dias;Centro;Recife;PE;0;0;Verificado;Vinho A;10;1.000,50;20;10.005,00;A1;Pendente;Mercado Livre",
    # Linha idêntica à anterior (possível duplicidade)
    "3;102;x;04/03/2026;Carla Dias;Centro;Recife;PE;0;0;Verificado;Vinho A;10;1.000,50;20;10.005,00;A1;Pendente;Mercado Livre",
]
CSV = (CABECALHO + "\n".join(LINHAS) + "\n").encode("utf-8-sig")


class TestFormatacao(unittest.TestCase):
    def test_numero_br(self):
        s = pd.Series(["1.234,56", "R$ 94,9", "7", "x"], dtype="string")
        r = dados.numero_br(s)
        self.assertAlmostEqual(r[0], 1234.56)
        self.assertAlmostEqual(r[1], 94.9)
        self.assertAlmostEqual(r[2], 7)
        self.assertTrue(np.isnan(r[3]))

    def test_numero_ja_numerico(self):
        r = dados.numero_br(pd.Series([1.5, 2.0]))
        self.assertEqual(list(r), [1.5, 2.0])

    def test_formatos(self):
        self.assertEqual(dados.brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(dados.inteiro(20341), "20.341")
        self.assertEqual(dados.pct(0.0705), "7,0%")

    def test_mascara_nome(self):
        self.assertEqual(dados.mascarar_nome("Ana Júlia Lopes"), "A. J. L.")
        self.assertEqual(dados.mascarar_nome(None), "")


class TestSintetico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = dados.carregar(CSV)

    def test_leitura(self):
        self.assertEqual(len(self.df), 5)
        self.assertEqual(self.df["Data"].min(), pd.Timestamp("2026-03-01"))
        self.assertAlmostEqual(self.df["Preço Total"].iloc[3], 10005.0)

    def test_coluna_obrigatoria_ausente(self):
        bruto = dados.ler_csv(CSV).drop(columns=["Frete"])
        with self.assertRaises(ValueError):
            dados.preparar(bruto)

    def test_ticket_e_frete_por_pedido(self):
        ind = dados.indicadores(self.df[~self.df["Cancelado"]])
        self.assertEqual(ind["pedidos"], 2)
        self.assertAlmostEqual(ind["faturamento"], 100 + 100 + 10005 + 10005)
        self.assertAlmostEqual(ind["ticket_medio"], ind["faturamento"] / 2)
        # frete 10 e desconto 2 do pedido 100 contam uma vez só
        self.assertAlmostEqual(ind["frete_total"], 10.0)
        self.assertAlmostEqual(ind["desconto_total"], 2.0)
        self.assertEqual(ind["nfe_pendentes"], 1)

    def test_margem_ignora_linhas_sem_custo(self):
        ind = dados.indicadores(self.df[~self.df["Cancelado"]])
        # linha 'Suporte B' tem custo 0 e não pode inflar a margem
        com_custo = 100 + 10005 + 10005
        custo = 20 * 1 + 20 * 10 + 20 * 10
        self.assertAlmostEqual(ind["margem_bruta"], com_custo - custo)
        self.assertLess(ind["cobertura_custo"], 1.0)

    def test_duplicidade_apenas_sinalizada(self):
        self.assertEqual(int(self.df["Linha idêntica"].sum()), 1)
        self.assertEqual(len(self.df), 5)  # nada removido
        self.assertEqual(dados.qualidade(self.df)["linhas_identicas"], 1)

    def test_cancelamento(self):
        self.assertAlmostEqual(dados.taxa_cancelamento(self.df), 1 / 3)
        por_canal = dados.taxa_cancelamento(self.df, "Loja virtual").set_index("Loja virtual")
        self.assertAlmostEqual(por_canal.loc["Shopee", "Taxa de cancelamento"], 1.0)

    def test_filtros(self):
        f = dados.filtrar(self.df, situacoes=["Verificado"], canais=["Bagy"])
        self.assertEqual(len(f), 2)
        f = dados.filtrar(self.df, inicio=pd.Timestamp("2026-03-02").date(), fim=pd.Timestamp("2026-03-02").date())
        self.assertEqual(len(f), 1)
        self.assertEqual(len(dados.filtrar(self.df, produtos=[])), 5)  # lista vazia = todos

    def test_serie_diaria_preenche_dias_sem_venda(self):
        d = dados.serie_diaria(self.df)
        self.assertEqual(len(d), 4)  # 01, 02, 03, 04
        self.assertEqual(d.loc[d["Data"] == "2026-03-03", "Faturamento"].iloc[0], 0)
        self.assertAlmostEqual(d["Acumulado"].iloc[-1], self.df["Preço Total"].sum())

    def test_curva_abc(self):
        abc = dados.curva_abc(self.df)
        self.assertAlmostEqual(abc["% acumulado"].iloc[-1], 100.0)
        self.assertEqual(abc["Classe"].iloc[0], "A")

    def test_produtos_sem_custo_nao_tem_margem(self):
        p = dados.desempenho_produtos(self.df).set_index("Descrição")
        self.assertTrue(np.isnan(p.loc["Suporte B", "Margem"]))
        self.assertFalse(np.isnan(p.loc["Vinho A", "Margem"]))

    def test_filtro_vazio_nao_quebra(self):
        vazio = dados.filtrar(self.df, canais=["Inexistente"])
        self.assertTrue(vazio.empty)
        self.assertEqual(dados.indicadores(vazio)["pedidos"], 0)
        self.assertEqual(dados.destaques(vazio), [])
        self.assertTrue(dados.serie_diaria(vazio).empty)
        self.assertTrue(dados.curva_abc(vazio).empty)


def _achar_csv():
    candidatos = [os.environ.get("BASE_CSV"), RAIZ / "base_dados_Valitransfers_Ltda.csv"]
    for c in candidatos:
        if c and Path(c).exists():
            return Path(c)
    return None


@unittest.skipIf(_achar_csv() is None, "CSV da base não encontrado ao lado do dashboard.py")
class TestBaseReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = _achar_csv()
        cls.hash_antes = hashlib.sha256(cls.caminho.read_bytes()).hexdigest()
        cls.df = dados.carregar(cls.caminho.read_bytes())

    def test_totais_da_base(self):
        self.assertEqual(len(self.df), 17881)
        self.assertEqual(self.df["N° do Pedido"].nunique(), 9357)
        self.assertAlmostEqual(self.df["Preço Total"].sum(), 1358754.83, places=2)
        self.assertEqual(int(self.df["Quantidade"].sum()), 20341)
        self.assertEqual(self.df["Data"].isna().sum(), 0)

    def test_indicadores_sem_cancelados(self):
        ind = dados.indicadores(self.df[~self.df["Cancelado"]])
        self.assertEqual(ind["pedidos"], 8723)
        self.assertAlmostEqual(ind["faturamento"], 1256417.62, places=2)
        self.assertAlmostEqual(ind["ticket_medio"], 1256417.62 / 8723, places=2)

    def test_frete_e_desconto_nao_sao_somados_por_linha(self):
        ind = dados.indicadores(self.df)
        self.assertAlmostEqual(ind["frete_total"], 125736.05, places=2)
        self.assertAlmostEqual(ind["desconto_total"], 26464.78, places=2)
        # somar por linha daria um valor bem maior (erro que o dashboard evita)
        self.assertGreater(self.df["Frete"].sum(), ind["frete_total"] * 1.5)

    def test_linhas_sem_custo(self):
        self.assertEqual(dados.qualidade(self.df)["linhas_sem_custo"], 868)

    def test_base_nao_foi_alterada(self):
        dados.filtrar(self.df, canais=["Bagy"])
        dados.indicadores(self.df)
        self.assertEqual(hashlib.sha256(self.caminho.read_bytes()).hexdigest(), self.hash_antes)


if __name__ == "__main__":
    unittest.main()
