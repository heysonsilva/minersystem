import socket
import hashlib
import time

# Configuração do cliente
host = '127.0.0.1'  # Endereço do servidor
porta = 31471         # Porta do servidor

def enviar_mensagem_G(sock, client_name):
    # Garante que o nome tenha exatamente 10 bytes
    nome_bytes = client_name.encode('utf-8')[:10]
    if len(nome_bytes) < 10:
        nome_bytes = nome_bytes.ljust(10, b' ')
    mensagem = b'G' + nome_bytes
    sock.sendall(mensagem)

def ler_mensagem_T(sock):
    # Lê os campos da mensagem T: numTransação (2 bytes), numCliente (2 bytes),
    # tamJanela (4 bytes), bitsZero (1 byte), tamTransação (4 bytes) e transação (n bytes)
    num_trans_bytes = sock.recv(2)
    num_cliente_bytes = sock.recv(2)
    tam_janela_bytes = sock.recv(4)
    bits_zero_byte = sock.recv(1)
    tam_trans_bytes = sock.recv(4)
    
    num_transacao = int.from_bytes(num_trans_bytes, 'big')
    num_cliente = int.from_bytes(num_cliente_bytes, 'big')
    tam_janela = int.from_bytes(tam_janela_bytes, 'big')
    bits_zero = int.from_bytes(bits_zero_byte, 'big')
    tam_transacao = int.from_bytes(tam_trans_bytes, 'big')
    
    transacao_bytes = b''
    while len(transacao_bytes) < tam_transacao:
        transacao_bytes += sock.recv(tam_transacao - len(transacao_bytes))
    transacao = transacao_bytes.decode('utf-8', 'ignore')
    
    return num_transacao, num_cliente, tam_janela, bits_zero, transacao

def enviar_mensagem_S(sock, num_transacao, nonce):
    # Envia 'S' + numTransação (2 bytes) + nonce (4 bytes)
    mensagem = b'S' + num_transacao.to_bytes(2, 'big') + nonce.to_bytes(4, 'big')
    sock.sendall(mensagem)

def mine_transaction(transaction, zero_bits, window_start, window_end):
    for nonce in range(window_start, window_end):
        data = nonce.to_bytes(4, 'big') + transaction.encode('utf-8')
        hash_int = int(hashlib.sha256(data).hexdigest(), 16)
        target = 1 << (256 - zero_bits)
        if hash_int < target:
            return nonce
    return None


def client_main():
    client_name = input("Digite o nome do cliente (até 10 caracteres): ")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, porta))
    print("Conectado ao servidor.")
    
    # Envia a mensagem G para solicitar uma transação
    enviar_mensagem_G(sock, client_name)
    
    while True:
        try:
            tipo = sock.recv(1)
            if not tipo:
                print("Servidor desconectado.")
                break
            
            if tipo == b'T':
                num_transacao, num_cliente, tam_janela, bits_zero, transacao = ler_mensagem_T(sock)
                print(f"\nTransação recebida: {transacao}")
                print(f"Bits zero: {bits_zero}, Janela de validação: {tam_janela}")
                
                window_start = num_cliente * tam_janela
                window_end = window_start + tam_janela
                print(f"Procurando nonce na janela: {window_start} a {window_end - 1}")
                
                nonce = mine_transaction(transacao, bits_zero, window_start, window_end)
                if nonce is not None:
                    print(f"Nonce encontrado: {nonce}")
                    enviar_mensagem_S(sock, num_transacao, nonce)
                    
                    resposta = sock.recv(1)
                    if resposta == b'V':
                        print("Nonce validado com sucesso!")
                    elif resposta == b'R':
                        print("Nonce inválido, continue a mineração...")
                    # Solicita nova transação após o processamento da resposta
                    enviar_mensagem_G(sock, client_name)
                else:
                    print("Nenhum nonce encontrado na janela. Solicitando nova transação...")
                    enviar_mensagem_G(sock, client_name)
            
            elif tipo == b'W':
                print("Nenhuma transação disponível. Aguardando 10 segundos...")
                time.sleep(10)
                enviar_mensagem_G(sock, client_name)
            
            elif tipo == b'Q':
                print("Servidor solicitou encerramento. Encerrando...")
                break
            
            else:
                print("Mensagem desconhecida recebida.")
        except Exception as e:
            print("Erro:", e)
            break
    
    sock.close()
    print("Conexão encerrada.")

if __name__ == "__main__":
    client_main()
