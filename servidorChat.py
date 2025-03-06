import socket
import threading
from queue import Queue
import time

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 31471

# Estruturas de dados para gerenciar transações e clientes
pending_transactions = Queue()  # Transações pendentes de validação
validated_transactions = []     # Transações validadas
clients = {}                    # Clientes conectados

# Exemplo de transação inicial (para teste)
pending_transactions.put(("Transação de exemplo", 4))  # (transação, bits zero)

def handle_client(conn, addr):
    print(f"Conexão estabelecida com {addr}")
    client_name = None

    while True:
        try:
            data = conn.recv(1024)
            if not data:
                sleep(10)
                break

            # Decodificar a mensagem do cliente
            message = data.decode('utf-8').strip()

            if message.startswith("G"):
                # Mensagem G: Cliente solicita uma transação
                client_name = message[2:12].strip()  # Extrair o nome do cliente
                clients[client_name] = conn  # Registrar o cliente

                if not pending_transactions.empty():
                    # Enviar uma transação para o cliente
                    transaction, zero_bits = pending_transactions.get()
                    num_clients = len(clients)
                    window_size = 1000000  # Tamanho da janela de validação

                    # Formatar mensagem T (transação)
                    response = f"T 1 {num_clients} {window_size} {zero_bits} {len(transaction)} {transaction}"
                    conn.send(response.encode('utf-8'))
                    print(f"Transação enviada para {client_name}")
                else:
                    # Não há transações disponíveis
                    conn.send(b"W")
                    print(f"Nenhuma transação disponível para {client_name}")

            elif message.startswith("S"):
                # Mensagem S: Cliente encontrou um nonce
                parts = message.split()
                num_transacao = int(parts[1])
                nonce = int(parts[2])

                print(f"Cliente {client_name} encontrou um nonce: {nonce}")

                # Validar o nonce (implementar lógica de validação)
                # Aqui você deve recalcular o hash e verificar se ele começa com a quantidade de bits zero esperada
                # Se for válido, notificar todos os clientes e adicionar à lista de transações validadas

                # Exemplo de resposta ao cliente (V para válido, R para inválido)
                conn.send(b"V 1")  # Supondo que o nonce é válido
                print(f"Nonce válido encontrado por {client_name}")

            else:
                # Mensagem desconhecida
                print(f"Mensagem desconhecida recebida de {client_name}: {message}")

        except Exception as e:
            print(f"Erro com {client_name}: {e}")
            break

    # Encerrar conexão
    if client_name:
        del clients[client_name]
    conn.close()
    print(f"Conexão encerrada com {addr}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Servidor escutando em {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    start_server()
