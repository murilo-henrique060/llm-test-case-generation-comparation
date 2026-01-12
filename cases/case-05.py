from datetime import datetime, timedelta

class Voo:
    def __init__(self, data, assentos):
        self.data = data
        self.assentos_disponiveis = assentos


class Reserva:
    def __init__(self, voo, assento):
        self.voo = voo
        self.assento = assento
        self.status = "CRIADA"
        self.pagamento_aprovado = False

    def confirmar(self):
        # ERRO: confirma sem pagamento aprovado
        self.status = "CONFIRMADA"
        self.voo.assentos_disponiveis -= 1  # ERRO: permite overbooking

    def cancelar(self):
        agora = datetime.now()

        # ERRO: sempre reembolsa
        self.status = "CANCELADA"
        self.voo.assentos_disponiveis -= 1  # ERRO: decrementa em vez de liberar

    def alterar_data_voo(self, nova_data):
        # ERRO: permite alteração após confirmação
        self.voo.data = nova_data
