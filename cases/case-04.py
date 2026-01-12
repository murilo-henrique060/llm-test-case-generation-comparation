class Cliente:
    def __init__(self, idade, renda, score):
        self.idade = idade
        self.renda = renda
        self.score = score


class AnaliseCredito:
    def avaliar(self, cliente):
        # ERRO: usa OR ao invés de AND
        if cliente.score >= 700 or cliente.renda >= 5000 or cliente.idade >= 21:
            return "Aprovado"

        # ERRO: cria estado inexistente
        return "Em análise"
