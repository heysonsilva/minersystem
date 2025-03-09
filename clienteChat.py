import socket
import hashlib
import time

# Configurações do servidor
HOST = '127.0.0.1'  # Endereço do servidor
PORT = 31471        # Porta do servidor

# Nome do cliente (deve ter até 10 bytes)
CLIENT_NAME = input(">> DIGITE UM NOME PARA ESTE CLIENTE: ")

def mine_transaction(transaction, zero_bits, window_start, window_end):
    # Função para minerar uma transação dentro de uma janela de validação.
    for nonce in range(window_start, window_end):
        data = nonce.to_bytes(4, 'big') + transaction.encode('utf-8')
        hash_result = hashlib.sha256(data).hexdigest()
        if hash_result.startswith('0' * zero_bits):
            return nonce
    return None

def start_client():
    # Função principal do cliente.
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    print(f"Conectado ao servidor {HOST}:{PORT}")

    while True:
        try:
            # Solicitar uma transação ao servidor
            request = f"G {CLIENT_NAME}"
            client.send(request.encode('utf-8'))
            print("Solicitando transação ao servidor...")

            # Receber resposta do servidor
            response = client.recv(1024).decode('utf-8').strip()
            print(f"Resposta do servidor: {response}")

            if response.startswith("T"):
                # Recebeu uma transação para validar
                parts = response.split()
                num_transacao = int(parts[1])
                num_clients = int(parts[2])
                window_size = int(parts[3])
                zero_bits = int(parts[4])
                tam_transacao = int(parts[5])
                transaction = ' '.join(parts[6:])

                print(f"Transação recebida: {transaction}")
                print(f"Bits zero esperados: {zero_bits}")
                print(f"Janela de validação: {window_size}")

                # Calcular a janela de validação para este cliente
                window_start = num_clients * window_size
                window_end = window_start + window_size

                # Tentar encontrar o nonce
                nonce = mine_transaction(transaction, zero_bits, window_start, window_end)
                if nonce is not None:
                    # Nonce encontrado, notificar o servidor
                    notification = f"S {num_transacao} {nonce}"
                    client.send(notification.encode('utf-8'))
                    print(f"Nonce encontrado: {nonce}")

                    # Aguardar resposta do servidor (V ou R)
                    validation_response = client.recv(1024).decode('utf-8').strip()
                    print(f"Resposta do servidor: {validation_response}")

                    if validation_response.startswith("V"):
                        # Nonce válido, solicitar nova transação
                        print("Nonce válido. Solicitando nova transação...")
                    elif validation_response.startswith("R"):
                        # Nonce inválido, continuar minerando na mesma transação
                        print("Nonce inválido. Continuando a mineração...")
                        continue
                else:
                    # Não encontrou um nonce válido, solicitar nova transação
                    print("Nenhum nonce válido encontrado. Solicitando nova transação...")

            elif response == "W":
                # Não há transações disponíveis no momento
                print("Nenhuma transação disponível. Aguardando 10 segundos...")
                time.sleep(10)  # Aguardar 10 segundos antes de tentar novamente

            elif response.startswith("I"):
                # Mensagem I: Nonce encontrado por outro cliente
                print("Nonce encontrado por outro cliente. Parando a mineração...")
                continue  # Solicitar nova transação

            else:
                # Mensagem desconhecida
                print(f"Mensagem desconhecida recebida: {response}")
                break

        except Exception as e:
            print(f"Erro: {e}")
            break

    # Encerrar conexão
    client.close()
    print("Conexão com o servidor encerrada.")

start_client()
