import socket
import threading
import time
import hashlib

# Configuração do servidor
HOST = '0.0.0.0'       # IP do servidor
PORTA = 31471          # Porta do servidor
TIMEOUT = 60           # Tempo limite para desconectar cliente inativo (60 segundos)
encerrar_servidor = False  # Variável de controle do servidor
tam_janela = 1000000    # Tamanho da janela de validação

# Variáveis globais para gerenciamento
pending_transactions = []      # Lista de tuplas: (transacao, bits_zero)
validated_transactions = []    # Lista de tuplas: (transacao, nonce, nome_cliente)
next_transacao_id = 1          # ID incremental para cada nova transação
connected_clients = {}         # Dict: nome_cliente -> (conn, addr)

# Funções de comunicação binária

def enviar_mensagem_T(sock, num_transacao, num_cliente, tam_janela, bits_zero, transacao):
    # 'T' + numTransação (2 bytes) + numCliente (2 bytes) + tamJanela (4 bytes) +
    # bitsZero (1 byte) + tamTransação (4 bytes) + transacao (n bytes)
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
    # Lê os 6 bytes após o tipo 'S': numTransação (2 bytes) + nonce (4 bytes)
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

def client_handler(conn, addr):
    global next_transacao_id, pending_transactions, validated_transactions, connected_clients
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
                # Para 'G', leia os 10 bytes seguintes para o nome
                nome_bytes = b''
                while len(nome_bytes) < 10:
                    chunk = conn.recv(10 - len(nome_bytes))
                    if not chunk:
                        break
                    nome_bytes += chunk
                if nome is None:
                    nome = nome_bytes.decode('utf-8').strip()
                    connected_clients[nome] = (conn, addr)
                    print(f"Cliente '{nome}' conectado de {addr}.")
                # Se houver transações pendentes, envia a primeira; senão, envia 'W'
                if pending_transactions:
                    # pending_transactions[0] é uma tupla: (transacao, bits_zero, client_counter)
                    transacao, bits_zero, client_counter = pending_transactions[0]
                    num_cliente = client_counter  # Define o número do cliente atual
                    enviar_mensagem_T(conn, next_transacao_id, num_cliente, tam_janela, bits_zero, transacao)
                    print(f"Enviando transação {next_transacao_id} para {nome} com cliente número {num_cliente}.")
                    # Incrementa o contador para a próxima requisição deste mesmo processo
                    pending_transactions[0] = (transacao, bits_zero, client_counter + 1)
                else:
                    conn.sendall(b'W')

            elif header == b'S':
                num_trans, nonce = ler_mensagem_S(conn)
                print(f"Cliente '{nome}' enviou nonce {nonce} para a transação {num_trans}.")
                if pending_transactions:
                    transacao, bits_zero, _ = pending_transactions[0]
                    if validar_nonce(nonce, transacao, bits_zero):
                        conn.sendall(b'V')
                        print(f"Nonce {nonce} validado para a transação {num_trans}.")
                        validated_transactions.append((transacao, nonce, nome))
                        
                        # Guarda o id da transação validada antes de incrementá-lo
                        validated_trans_id = next_transacao_id
                        
                        # Envia mensagem "I" (para Interromper) para todos os outros clientes
                        # Formato: 'I' + numTransação (2 bytes)
                        msg_I = b'I' + validated_trans_id.to_bytes(2, 'big')
                        for client_nome, (client_conn, _) in connected_clients.items():
                            if client_nome != nome:  # Não envia para o cliente que encontrou o nonce
                                try:
                                    client_conn.sendall(msg_I)
                                except Exception as e:
                                    print(f"Erro ao enviar mensagem I para {client_nome}: {e}")
                        
                        pending_transactions.pop(0)
                        next_transacao_id += 1
                    else:
                        conn.sendall(b'R')
                        print(f"Nonce {nonce} inválido para a transação {num_trans}.")
                else:
                    conn.sendall(b'W')
            else:
                print("Mensagem desconhecida recebida do cliente.")
    except Exception as e:
        print(f"Erro com cliente {addr}: {e}")
    finally:
        conn.close()
        if nome and nome in connected_clients:
            del connected_clients[nome]
        print(f"Conexão com {addr} encerrada.")

def user_input_thread():
    global pending_transactions, validated_transactions, connected_clients, encerrar_servidor
    while True:
        cmd = input("Digite um comando (/newtrans, /validtrans, /pendtrans, /clients, /exit): ").strip()
        if cmd.startswith("/newtrans"):
            try:
                # Exemplo: /newtrans Meu Texto Com Espaços 4
                command_content = cmd[len("/newtrans "):]
                last_space_index = command_content.rfind(" ")
                if last_space_index == -1:
                    raise ValueError("Formato inválido")
                transacao = command_content[:last_space_index]
                bits_str = command_content[last_space_index+1:]
                bits_zero = int(bits_str)
                # Armazena a transação com contador de clientes iniciando em 0
                pending_transactions.append((transacao, bits_zero, 0))
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
                for t, bits, contador in pending_transactions:
                    print(f"Transação: {t}, Bits zero: {bits}, Clientes já minerando: {contador}")
            else:
                print("Nenhuma transação pendente.")
        elif cmd == "/clients":
            if connected_clients:
                print("Clientes conectados:")
                for nome, (_, addr) in connected_clients.items():
                    print(f"Cliente: {nome}, Endereço: {addr}")
            else:
                print("Nenhum cliente conectado.")
        elif cmd == "/exit":
            print("Encerrando servidor e notificando clientes...")
            for nome, (conn, _) in list(connected_clients.items()):
                enviar_encerramento(conn)
                conn.close()
            encerrar_servidor = True
            break
        else:
            print("Comando desconhecido.")


def server_main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((HOST, PORTA))
    server_sock.listen(5)
    print(f"Servidor escutando em {HOST}:{PORTA}")
    
    threading.Thread(target=user_input_thread, daemon=True).start()
    
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
