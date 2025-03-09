import socket
import threading
import time
import hashlib
import requests

# Configurações do servidor
HOST = '0.0.0.0'  # Escuta em todas as interfaces de rede
PORT = 31471

# Configurações do bot do Telegram
TELEGRAM_API_URL = "https://api.telegram.org/bot6083297671:AAEx6pVBTfsLZ0-Kqq048eVqaLQKgi8sVW4"
CHAT_ID = "5021057327"

# Estruturas de dados para gerenciar transações e clientes
pending_transactions = []  # Transações pendentes de validação
validated_transactions = []  # Transações validadas
clients = {}  # Clientes conectados {nome: conexão}
client_windows = {}  # Janelas de validação dos clientes {nome: (transação, janela_inicio, janela_fim)}
last_activity = {}  # Última atividade dos clientes
validation_lock = threading.Lock()  # Lock para evitar condições de corrida

def send_telegram_message(text):
    # Envia uma mensagem para o grupo do Telegram.
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }
    response = requests.post(url, json=payload)
    return response.json()

def get_telegram_updates():
    # Obtém as últimas mensagens do Telegram.
    url = f"{TELEGRAM_API_URL}/getUpdates"
    response = requests.get(url)
    return response.json()

def process_telegram_commands():
    # Processa os comandos recebidos do Telegram.
    last_update_id = None
    while True:
        try:
            updates = get_telegram_updates()
            if updates.get("ok"):
                for update in updates["result"]:
                    update_id = update["update_id"]
                    if last_update_id is None or update_id > last_update_id:
                        last_update_id = update_id
                        message = update.get("message", {}).get("text", "")
                        chat_id = update["message"]["chat"]["id"]

                        if message.startswith("/newtrans"):
                            try:
                                parts = message.split(maxsplit=2)
                                if len(parts) == 3:
                                    transaction = parts[1]
                                    zero_bits = int(parts[2])
                                    pending_transactions.append((transaction, zero_bits))
                                    send_telegram_message(f"Transação adicionada com sucesso: {transaction}, Bits zero: {zero_bits}")
                                else:
                                    send_telegram_message("Formato inválido. Use: /newtrans <transação> <bits zero>")
                            except Exception as e:
                                send_telegram_message(f"Erro ao adicionar transação: {e}")

                        elif message == "/validtrans":
                            if validated_transactions:
                                response = "Transações validadas:\n"
                                for transacao in validated_transactions:
                                    response += f"Transação: {transacao[0]}, Nonce: {transacao[1]}, Validado por: {transacao[2]}\n"
                            else:
                                response = "Nenhuma transação validada ainda."
                            send_telegram_message(response)

                        elif message == "/pendtrans":
                            if pending_transactions:
                                response = "Transações pendentes:\n"
                                for transacao in pending_transactions:
                                    response += f"Transação: {transacao[0]}, Bits zero: {transacao[1]}\n"
                            else:
                                response = "Nenhuma transação pendente."
                            send_telegram_message(response)

                        elif message == "/clients":
                            if clients:
                                response = "Clientes ativos:\n"
                                for name in clients.keys():
                                    response += f"Cliente: {name}\n"
                            else:
                                response = "Nenhum cliente ativo no momento."
                            send_telegram_message(response)

        except Exception as e:
            print(f"Erro ao processar comandos do Telegram: {e}")

        time.sleep(5)  # Verifica a cada 5 segundos

def validate_nonce(transaction, nonce, zero_bits):
    # Valida se o nonce é válido para a transação.
    data = nonce.to_bytes(4, 'big') + transaction.encode('utf-8')
    hash_result = hashlib.sha256(data).hexdigest()
    return hash_result.startswith('0' * zero_bits)

def handle_client(conn, addr):
    # Função para lidar com a comunicação de um cliente.
    client_name = None

    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break  # Se não receber dados, encerra a conexão

            message = data.decode('utf-8').strip()
            message_type = message[0] if message else None

            if message_type == "G":
                # Mensagem G: Cliente solicita uma transação
                client_name = message[2:12].strip()  # Extrair o nome do cliente
                clients[client_name] = conn  # Registrar o cliente
                last_activity[client_name] = time.time()  # Atualizar tempo de atividade

                if pending_transactions:
                    transaction, zero_bits = pending_transactions[0]
                    window_size = 1000000  # Tamanho da janela de validação

                    # Calcular a próxima janela disponível
                    if transaction not in client_windows:
                        client_windows[transaction] = []  # Inicializa a lista de janelas para a transação

                    # Encontra a próxima janela disponível
                    window_start = 0
                    if client_windows[transaction]:
                        last_window_end = client_windows[transaction][-1][1]
                        window_start = last_window_end + 1

                    window_end = window_start + window_size

                    # Armazenar a janela de validação do cliente
                    client_windows[transaction].append((window_start, window_end, client_name))

                    # Formatar mensagem T (transação)
                    response = f"T 1 {len(client_windows[transaction])} {window_size} {zero_bits} {len(transaction)} {transaction} {window_start} {window_end}"
                    conn.send(response.encode('utf-8'))
                else:
                    # Não há transações disponíveis
                    conn.send(b"W")

            elif message_type == "S":
                # Mensagem S: Cliente encontrou um nonce
                parts = message.split()
                num_transacao = int(parts[1])
                nonce = int(parts[2])

                # Validar o nonce com Lock para evitar condições de corrida
                with validation_lock:
                    if client_name in client_windows:
                        transaction, window_start, window_end = client_windows[client_name]
                        if validate_nonce(transaction, nonce, zero_bits):
                            # Nonce válido
                            conn.send(b"V 1")  # Notifica o cliente que o nonce é válido
                            validated_transactions.append((transaction, nonce, client_name))
                            # Remove a transação da lista de pendentes
                            pending_transactions.pop(0)
                            # Liberar a janela de validação
                            del client_windows[transaction]
                            # Notificar outros clientes para parar a mineração
                            for other_client in clients.values():
                                if other_client != conn:
                                    other_client.send(f"I {num_transacao}".encode('utf-8'))
                        else:
                            # Nonce inválido
                            conn.send(b"R 1")  # Notifica o cliente que o nonce é inválido

        except Exception as e:
            print(f"Erro ao lidar com o cliente {client_name}: {e}")
            break

    # Encerrar conexão
    if client_name:
        del clients[client_name]
        if client_name in client_windows:
            del client_windows[client_name]
        del last_activity[client_name]
    conn.close()
    print(f"Conexão com {client_name} encerrada.")

def check_inactive_clients():
    # Verifica clientes inativos e fecha conexões.
    while True:
        current_time = time.time()
        inactive_clients = []
        for client_name, last_time in last_activity.items():
            if current_time - last_time > 60:  # 60 segundos de inatividade
                inactive_clients.append(client_name)

        for client_name in inactive_clients:
            if client_name in clients:
                clients[client_name].close()
                del clients[client_name]
                del client_windows[client_name]
                del last_activity[client_name]
                print(f"Cliente {client_name} desconectado por inatividade.")

        time.sleep(10)  # Verifica a cada 10 segundos

def handle_user_input():
    # Função para lidar com a entrada do usuário via terminal.
    while True:
        try:
            command = input("Digite um comando (/newtrans, /validtrans, /pendtrans, /clients): ")
            if command == "/newtrans":
                transaction = input("Digite a transação: ")
                zero_bits = int(input("Digite o número de bits zero: "))
                pending_transactions.append((transaction, zero_bits))
                print("Transação adicionada com sucesso!")
            elif command == "/validtrans":
                print("Transações validadas:")
                for transacao in validated_transactions:
                    print(f"Transação: {transacao[0]}, Nonce: {transacao[1]}, Validado por: {transacao[2]}")
            elif command == "/pendtrans":
                print("Transações pendentes:")
                for transacao in pending_transactions:
                    print(f"Transação: {transacao[0]}, Bits zero: {transacao[1]}")
            elif command == "/clients":
                print("Clientes ativos:")
                for name, conn in clients.items():
                    print(f"Cliente: {name}")
            else:
                print("Comando desconhecido.")
        except Exception as e:
            print(f"Erro ao processar comando: {e}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Servidor escutando em {HOST}:{PORT}")

    # Iniciar thread para processar comandos do Telegram
    telegram_thread = threading.Thread(target=process_telegram_commands)
    telegram_thread.daemon = True
    telegram_thread.start()

    # Iniciar thread para verificar clientes inativos
    inactive_check_thread = threading.Thread(target=check_inactive_clients)
    inactive_check_thread.daemon = True
    inactive_check_thread.start()

    # Iniciar thread para lidar com a entrada do usuário
    user_input_thread = threading.Thread(target=handle_user_input)
    user_input_thread.daemon = True
    user_input_thread.start()

    while True:
        conn, addr = server.accept()
        print(f"Nova conexão de {addr}")
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    start_server()
