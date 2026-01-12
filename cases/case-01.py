"""
# Caso de Teste 01 - Sistema de Cadastro de Usuário

Um sistema para permitir a criação e armazenamento de Usuários

## Regras de Negócio

- Todos os usuários devem possuir nome, email e senha;
- O email deve conter o caractere @;
- A senha deve ter, no mínimo, 6 caracteres;
- Não é permitido cadastrar dois usuário com o mesmo email.

## Requisitos Funcionais

- RF01: O sistema deve permitir cadastrar um usuário;
- RF02: O sistema deve validar se o email é válido;
- RF03: O sistema deve impedir cadastro de email duplicado;
- RF04: O sistema deve lançar uma exceção em caso de uma falha.

## Diagrama de classes UML

Usuario
----------------
+ nome: str
+ email: str
- senha: str
----------------

UsuarioService
----------------
----------------
+ cadastrar(nome: str, email: str, senha: str) -> Usuario

## Erros Mapeados

- Não valida nome vazio;
- Valida email apenas como string não vazia;
- Não valida tamanho mínimo da senha;
- Não verifica email duplicado.
"""

from typing import List

class Usuario:
    def __init__(self, nome: str, email: str, senha:str):
        self.nome = nome
        self.email = email
        self.senha = senha

class UsuarioService:
    def __init__(self):
        self._usuarios: List[Usuario] = []

    def cadastrar(self, nome: str, email: str, senha: str) -> Usuario:
        # Não valida nome vazio

        if not email: # Valida email apenas como string como não vazia
            raise "Erro: email obrigatório"

        # Não valida tamanho mínimo da senha

        usuario = Usuario(nome, email, senha)
        self._usuarios.append(usuario) # Não verifica email duplicado

        return usuario
