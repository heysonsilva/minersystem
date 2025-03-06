import socket
import threading
import time
import hashlib

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 31471

# Estruturas de dados para gerenciar transações e clientes
pending_transactions = []  # Transações pendentes de validação (agora uma lista)
validated_transactions = []  # Transações validadas
clients = {}  # Clientes conectados

# Exemplo de transação inicial (para teste)
pending_transactions.append(("Transação de exemplo", 4))  # (transação, bits zero)

def validate_nonce(transaction, nonce, zero_bits):
    """
    Valida se o nonce é válido para a transação.
    """
    data = nonce.to_bytes(4, 'big') + transaction.encode('utf-8')
    hash_result = hashlib.sha256(data).hexdigest()
    return hash_result.startswith('0' * zero_bits)

def handle_client(conn, addr):
    """
    Função para lidar com a comunicação de um cliente.
    """
    client_name = None

    while True:
        try:
            data = conn.recv(1024)
            if not data:
                time.sleep(10)
                break

            # Decodificar a mensagem do cliente
            message = data.decode('utf-8').strip()

            # Identificar o tipo de mensagem pela primeira letra
            message_type = message[0] if message else None

            if message_type == "G":
                # Mensagem G: Cliente solicita uma transação
                client_name = message[2:12].strip()  # Extrair o nome do cliente
                clients[client_name] = conn  # Registrar o cliente

                if pending_transactions:  # Verifica se há transações pendentes
                    # Pega a primeira transação da lista
                    transaction, zero_bits = pending_transactions.pop(0)
                    num_clients = len(clients)
                    window_size = 1000000  # Tamanho da janela de validação

                    # Formatar mensagem T (transação)
                    response = f"T 1 {num_clients} {window_size} {zero_bits} {len(transaction)} {transaction}"
                    conn.send(response.encode('utf-8'))
                else:
                    # Não há transações disponíveis
                    conn.send(b"W")

            elif message_type == "S":
                # Mensagem S: Cliente encontrou um nonce
                parts = message.split()
                num_transacao = int(parts[1])
                nonce = int(parts[2])

                # Validar o nonce
                transaction = "Transação de exemplo"  # Substitua pela transação correta
                zero_bits = 4  # Substitua pelo número de bits zero esperado
                if validate_nonce(transaction, nonce, zero_bits):
                    # Nonce válido
                    conn.send(b"V 1")  # Notificar o cliente que o nonce é válido
                    validated_transactions.append((transaction, nonce, client_name))
                    # Notificar outros clientes para parar a mineração
                    for other_client in clients.values():
                        if other_client != conn:
                            other_client.send(f"I {num_transacao}".encode('utf-8'))
                else:
                    # Nonce inválido
                    conn.send(b"R 1")  # Notificar o cliente que o nonce é inválido

        except Exception as e:
            break

    # Encerrar conexão
    if client_name:
        del clients[client_name]
    conn.close()

def handle_user_input():
    """
    Função para lidar com a entrada do usuário via terminal.
    """
    while True:
        command = input("Digite um comando (/newtrans, /validtrans, /pendtrans, /clients): ")
        if command == "/newtrans":
            transaction = input("Digite a transação: ")
            zero_bits = int(input("Digite o número de bits zero: "))
            pending_transactions.append((transaction, zero_bits))  # Adiciona à lista
            print("Transação adicionada com sucesso!")
        elif command == "/validtrans":
            print("Transações validadas:")
            for transacao in validated_transactions:
                print(f"Transação: {transacao[0]}, Nonce: {transacao[1]}, Validado por: {transacao[2]}")
        elif command == "/pendtrans":
            print("Transações pendentes:")
            for transacao in pending_transactions:  # Itera sobre a lista
                print(f"Transação: {transacao[0]}, Bits zero: {transacao[1]}")
        elif command == "/clients":
            print("Clientes ativos:")
            for name, conn in clients.items():
                print(f"Cliente: {name}")
        else:
            print("Comando desconhecido.")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Servidor escutando em {HOST}:{PORT}")

    # Iniciar thread para lidar com a entrada do usuário
    user_input_thread = threading.Thread(target=handle_user_input)
    user_input_thread.daemon = True
    user_input_thread.start()

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

start_server()