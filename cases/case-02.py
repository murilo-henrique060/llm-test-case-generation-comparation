"""
# Caso de Teste 03 - Sistema de Pedidos

Sistema para realizar pedidos em um E-commerce

## Regras de Negócio

- Um pedido deve conter, ao menos, um item;
- Cada item possui a quantidade mínima de 1;
- O valor total do pedido é a soma dos itens;
- Pedidos acima de R$ 200 recebem 10% de desconto;
- O desconto não pode ser aplicado duas vezes.

## Requisitos Funcionais

- RF01: Criar pedido com múltiplos ítens;
- RF02: Deve Calcular corretamente o total;
- RF03: O sistema deve aplicar o desconto corretamente quando elegível;
- RF04: O sistema deve exibir o valor final do pedido;
- RF05: O sistema deve lançar uma exceção em caso de uma falha.

## Diagrama de Classes UML

Item
---------------
+ nome: str
+ preco: Decimal
+ quantidade: int
----------------

Pedido
----------------
----------------
+ adicionar_item(item: Item) -> None
+ calcular_total() -> Decimal

## Erros Mapeados

- Aceita quantidade 0 ou negativa de itens;
- Permite pedido sem itens válidos;
- Ignora quantidade de itens no cálculo do total;
- Pode aplicar o desconto várias vezes.
"""

from typing import List
from decimal import Decimal

class Item:
    def __init__(self, nome: str, preco: Decimal, quantidade: int):
        self.nome: str = nome
        self.preco: Decimal = preco
        self.quantidade: int = quantidade  # Aceita 0 ou negativo


class Pedido:
    def __init__(self):
        self.itens: List[Item] = []
        self.valor_total: Decimal = Decimal(0)

    def adicionar_item(self, item):
        self.itens.append(item)  # Permite pedido sem itens válidos

    def calcular_total(self):
        total = Decimal(0)
        for item in self.itens:
            total += item.preco  # Ignora quantidade

        # Pode aplicar desconto várias vezes
        if total >= 200:
            total *= Decimal('0.9')

        self.valor_total = total
        return total