import socket
import threading
import time
import hashlib
import requests

# Configurações do servidor
HOST = '0.0.0.0'
PORTA = 31471
TIMEOUT = 60
tam_janela = 1000000

# Variáveis globais
encerrar_servidor = False
pending_transactions = []      # Cada elemento: (transacao, bits_zero, client_counter, client_list)
validated_transactions = []    # Cada elemento: (transacao, nonce, nome_cliente)
next_transacao_id = 1
connected_clients = {}         # Cada elemento: nome -> {conn, addr, current_transaction, window, connection_time, last_tx_sent}

# Funções de comunicação binária
def enviar_mensagem_T(sock, num_transacao, num_cliente, tam_janela, bits_zero, transacao):
    transacao_bytes = transacao.encode('utf-8')
    tam_transacao = len(transacao_bytes)
    mensagem = (
        b'T' +
        num_transacao.to_bytes(2, 'big') +
        num_cliente.to_bytes(2, 'big') +
        tam_janela.to_bytes(4, 'big') +
        bits_zero.to_bytes(1, 'big') +
        tam_transacao.to_bytes(4, 'big') +
        transacao_bytes
    )
    sock.sendall(mensagem)

def ler_mensagem_S(sock):
    dados = sock.recv(6)
    if len(dados) < 6:
        raise ValueError("Mensagem S incompleta")
    num_transacao = int.from_bytes(dados[0:2], 'big')
    nonce = int.from_bytes(dados[2:6], 'big')
    return num_transacao, nonce

def validar_nonce(nonce, transacao, bits_zero):
    data = nonce.to_bytes(4, 'big') + transacao.encode('utf-8')
    hash_int = int(hashlib.sha256(data).hexdigest(), 16)
    target = 1 << (256 - bits_zero)
    return hash_int < target

def enviar_encerramento(sock):
    try:
        sock.sendall(b'Q')
    except:
        pass

# Função para tratar clientes conectados
def client_handler(conn, addr):
    global next_transacao_id, pending_transactions, validated_transactions, connected_clients, tam_janela
    conn.settimeout(TIMEOUT)
    nome = None
    try:
        while True:
            header = conn.recv(1)
            if not header:
                break  # Conexão encerrada

            # Ignora bytes de controle (espaço, \n, \r)
            if header in [b'\n', b'\r', b' ']:
                continue

            if header == b'G':
                nome_bytes = b''
                while len(nome_bytes) < 10:
                    chunk = conn.recv(10 - len(nome_bytes))
                    if not chunk:
                        break
                    nome_bytes += chunk
                if nome is None:
                    nome = nome_bytes.decode('utf-8').strip()
                    connected_clients[nome] = {
                        "conn": conn,
                        "addr": addr,
                        "current_transaction": None,
                        "window": None,
                        "connection_time": time.time(),
                        "last_tx_sent": None
                    }
                    print(f"Cliente '{nome}' conectado de {addr}.")
                if pending_transactions:
                    transacao, bits_zero, client_counter, client_list = pending_transactions[0]
                    num_cliente = client_counter
                    if nome not in client_list:
                        client_list.append(nome)
                    enviar_mensagem_T(conn, next_transacao_id, num_cliente, tam_janela, bits_zero, transacao)
                    pending_transactions[0] = (transacao, bits_zero, client_counter + 1, client_list)
                    
                    window_start = num_cliente * tam_janela
                    window_end = window_start + tam_janela
                    connected_clients[nome]["current_transaction"] = (next_transacao_id, transacao)
                    connected_clients[nome]["window"] = (window_start, window_end)
                    connected_clients[nome]["last_tx_sent"] = time.time()
                else:
                    conn.sendall(b'W')
            
            elif header == b'S':
                num_trans, nonce = ler_mensagem_S(conn)
                print(f"Cliente '{nome}' enviou nonce {nonce} para a transação {num_trans}.")
                if pending_transactions:
                    transacao, bits_zero, _, _ = pending_transactions[0]
                    if validar_nonce(nonce, transacao, bits_zero):
                        conn.sendall(b'V')
                        print(f"Nonce {nonce} validado para a transação {num_trans}.")
                        validated_transactions.append((transacao, nonce, nome))
                        
                        validated_trans_id = next_transacao_id
                        msg_I = b'I' + validated_trans_id.to_bytes(2, 'big')
                        for client_nome, dados in connected_clients.items():
                            if client_nome != nome:
                                try:
                                    dados["conn"].sendall(msg_I)
                                except Exception as e:
                                    print(f"Erro ao enviar mensagem I para {client_nome}: {e}")
                        
                        pending_transactions.pop(0)
                        next_transacao_id += 1
                    else:
                        conn.sendall(b'R')
                        print(f"Nonce {nonce} inválido para a transação {num_trans}.")
                else:
                    conn.sendall(b'W')
            
            elif header == b'Q':
                print("Servidor solicitou encerramento. Encerrando...")
                break
            
            else:
                print("Mensagem desconhecida recebida do cliente.")
    except Exception as e:
        # Se o erro for do tipo WinError 10038, indica que o socket já está fechado
        if "10038" in str(e):
            print(f"Cliente '{nome}' desconectado por inatividade (sem transações por 60 segundos).")
        else:
            print(f"Erro com cliente {addr}: {e}")
    finally:
        conn.close()
        if nome and nome in connected_clients:
            del connected_clients[nome]
        print(f"Conexão com {addr} encerrada.")


# Função para tratamento dos comandos de entrada do usuário no servidor
def user_input_thread():
    global pending_transactions, validated_transactions, connected_clients, encerrar_servidor
    while True:
        cmd = input("Digite um comando (/newtrans, /validtrans, /pendtrans, /clients, /exit): ").strip()
        if cmd.startswith("/newtrans"):
            try:
                command_content = cmd[len("/newtrans "):]
                last_space_index = command_content.rfind(" ")
                if last_space_index == -1:
                    raise ValueError("Formato inválido")
                transacao = command_content[:last_space_index]
                bits_str = command_content[last_space_index+1:]
                bits_zero = int(bits_str)
                pending_transactions.append((transacao, bits_zero, 0, []))
                print("Transação adicionada com sucesso!")
            except Exception as e:
                print("Formato inválido. Exemplo: /newtrans Meu Texto Com Espaços 4")
        elif cmd == "/validtrans":
            if validated_transactions:
                print("Transações validadas:")
                for t, nonce, cliente in validated_transactions:
                    print(f"Transação: {t}, Nonce: {nonce}, Validado por: {cliente}")
            else:
                print("Nenhuma transação validada ainda.")
        elif cmd == "/pendtrans":
            if pending_transactions:
                print("Transações pendentes:")
                for t, bits, contador, client_list in pending_transactions:
                    clientes = ", ".join(client_list) if client_list else "Nenhum"
                    print(f"Transação: {t}, Bits zero: {bits}, Clientes minerando: {clientes}")
            else:
                print("Nenhuma transação pendente.")
        elif cmd == "/clients":
            if connected_clients:
                print("Clientes conectados:")
                for nome, dados in connected_clients.items():
                    if dados["current_transaction"]:
                        trans_id, transacao = dados["current_transaction"]
                        window = dados["window"]
                        print(f"Cliente: {nome}, Transação: {transacao}, Janela: {window[0]} a {window[1]-1}")
                    else:
                        print(f"Cliente: {nome}, Sem transação atribuída")
            else:
                print("Nenhum cliente conectado.")
        elif cmd == "/exit":
            print("Encerrando servidor e notificando clientes...")
            for nome, dados in list(connected_clients.items()):
                enviar_encerramento(dados["conn"])
                dados["conn"].close()
            encerrar_servidor = True
            break
        else:
            print("Comando desconhecido.")

# Função para monitorar timeouts dos clientes (60 segundos sem receber transação T)
def monitor_client_timeouts():
    global connected_clients, encerrar_servidor
    while not encerrar_servidor:
        time.sleep(5)
        now = time.time()
        for nome in list(connected_clients.keys()):
            dados = connected_clients[nome]
            last_tx = dados.get("last_tx_sent")
            if last_tx is None:
                last_tx = dados.get("connection_time", now)
            if now - last_tx > 60:
                print(f"Cliente '{nome}' não recebeu transações por mais de 60 segundos. Desconectando...")
                try:
                    enviar_encerramento(dados["conn"])
                    dados["conn"].close()
                except Exception as e:
                    if "10038" in str(e):
                        print(f"Cliente '{nome}' desconectado por inatividade (sem transações por 60 segundos).")
                    else:
                        print(f"Erro ao desconectar cliente '{nome}': {e}")
                del connected_clients[nome]


# Funções para integração com o Telegram via requests
TELEGRAM_API_URL = "https://api.telegram.org/bot6083297671:AAEx6pVBTfsLZ0-Kqq048eVqaLQKgi8sVW4"
BOT_NAME = "mecLove_bot"

def send_message(chat_id, text):
    url = TELEGRAM_API_URL + "/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")

def get_validtrans_text():
    if validated_transactions:
        lines = ["Transações validadas:"]
        for t, nonce, cliente in validated_transactions:
            lines.append(f"Transação: {t}, Nonce: {nonce}, Validado por: {cliente}")
        return "\n".join(lines)
    else:
        return "Nenhuma transação validada ainda."

def get_pendtrans_text():
    if pending_transactions:
        lines = ["Transações pendentes:"]
        for t, bits, contador, client_list in pending_transactions:
            clientes = ", ".join(client_list) if client_list else "Nenhum"
            lines.append(f"Transação: {t}, Bits zero: {bits}, Clientes minerando: {clientes}")
        return "\n".join(lines)
    else:
        return "Nenhuma transação pendente."

def get_clients_text():
    if connected_clients:
        lines = ["Clientes conectados:"]
        for nome, dados in connected_clients.items():
            if dados["current_transaction"]:
                trans_id, transacao = dados["current_transaction"]
                window = dados["window"]
                lines.append(f"Cliente: {nome}, Transação: {transacao}, Janela: {window[0]} a {window[1]-1}")
            else:
                lines.append(f"Cliente: {nome}, Sem transação atribuída")
        return "\n".join(lines)
    else:
        return "Nenhum cliente conectado."

def telegram_bot_thread():
    offset = None
    while not encerrar_servidor:
        params = {}
        if offset is not None:
            params["offset"] = offset
        try:
            response = requests.get(TELEGRAM_API_URL + "/getUpdates", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" in update and "text" in update["message"]:
                            chat_id = update["message"]["chat"]["id"]
                            text = update["message"]["text"].strip()
                            if text == "/validtrans":
                                send_message(chat_id, get_validtrans_text())
                            elif text == "/pendtrans":
                                send_message(chat_id, get_pendtrans_text())
                            elif text == "/clients":
                                send_message(chat_id, get_clients_text())
                            else:
                                send_message(chat_id, "Comando desconhecido. Comandos disponíveis: /validtrans, /pendtrans, /clients")
            else:
                print("Erro ao obter atualizações do Telegram:", response.status_code)
        except Exception as e:
            print("Erro no telegram_bot_thread:", e)
        time.sleep(3)

# Função principal do servidor
def server_main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((HOST, PORTA))
    server_sock.listen(5)
    print(f"Servidor escutando em {HOST}:{PORTA}")
    
    # Inicia threads auxiliares
    threading.Thread(target=user_input_thread, daemon=True).start()
    threading.Thread(target=monitor_client_timeouts, daemon=True).start()
    threading.Thread(target=telegram_bot_thread, daemon=True).start()
    
    while not encerrar_servidor:
        try:
            conn, addr = server_sock.accept()
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"Erro ao aceitar conexão: {e}")
            break
    server_sock.close()

if __name__ == "__main__":
    server_main()
