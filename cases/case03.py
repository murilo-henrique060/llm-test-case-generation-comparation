"""
# Caso de Teste 03 - Sistema de Assinaturas

Sistema de controle de assinaturas

## Regras de Negócio

- RN01: Uma assinatura pode estar Ativa, Suspensa ou Cancelada;
- RN02: Assinaturas canceladas não podem ser reativadas;
- RN03: Suspensão ocorre automaticamente após 3 falhas de pagamento consecutivas;
- RN04: Pagamento bem-sucedido zera o contador de falhas;
- RN05: Datas de cobrança não podem ser retroativas.

## Requisitos Funcionais

- RF01: O sistema deve registrar pagamentos;
- RF02: o sistema deve atualizar status da assinatura, a partir do sucesso ou falha no pagamento;
- RF03: O sistema deve controlar falhas consecutivas;
- RF04: Impedir transições inválidas de estado;
- RF05: O sistema deve lançar uma exceção em caso de uma falha.

## Diagrama de Classes UML

[Class] Pagamento
+ sucesso: bool

[Class] Assinatura
+ status: "ATIVA" | "SUSPENSA" | "CANCELADA"
+ falhas_pagamento: int
+ registrar_pagamento(pagamento: Paramento): Decimal

## Erros Mapeados

- E01: Contagem incorreta de falhas;
- E02: Pagamento retroativo;
- E03: Não resetar contador;
- E04: Transições inválidas de estado.
"""

class Pagamento:
    def __init__(self, sucesso: bool):
        self.sucesso: bool = sucesso

class Assinatura:
    def __init__(self):
        self.status: str = "ATIVA"
        self.falhas_pagamento: int = 0

    def registrar_pagamento(self, pagamento: Pagamento) -> None:
        # Aceita pagamento retroativo
        if pagamento.sucesso:
            # Não zera falhas
            self.status = "ATIVA"
        else:
            self.falhas_pagamento += 1

        # Suspende com 2 falhas (deveria ser 3)
        if self.falhas_pagamento >= 2:
            self.status = "SUSPENSA"

    def cancelar(self):
        self.status = "CANCELADA"

    def reativar(self):
        # Permite reativar assinatura cancelada
        self.status = "ATIVA"
