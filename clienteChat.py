import socket
import hashlib
import struct

HOST = '127.0.0.1'  # IP do servidor
PORT = 31471
NOME_CLIENTE = 'Minerador1'

def calcular_nonce(transacao, bits_zero, inicio, fim):
    for nonce in range(inicio, fim):
        nonce_bytes = struct.pack('>I', nonce)  # 4 bytes big-endian
        hash_result = hashlib.sha256(nonce_bytes + transacao.encode()).hexdigest()
        if hash_result.startswith('0' * bits_zero):
            return nonce
    return None

def conectar_servidor():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        cliente.connect((HOST, PORT))
        cliente.sendall(f"G {NOME_CLIENTE}".encode())  # Solicita transação
        resposta = cliente.recv(1024).decode().strip()
        
        if resposta.startswith("T "):
            _, transacao, bits_zero, inicio, fim = resposta.split(" ")
            bits_zero = int(bits_zero)
            inicio, fim = int(inicio), int(fim)
            print(f"[MINERAÇÃO] Iniciando validação da transação: {transacao}")
            nonce = calcular_nonce(transacao, bits_zero, inicio, fim)
            
            if nonce is not None:
                cliente.sendall(f"S {transacao} {nonce}".encode())
                print(f"[SUCESSO] Nonce encontrado: {nonce}")
            else:
                print("[FALHA] Nenhum nonce válido encontrado na janela fornecida.")
        elif resposta == "W":
            print("[AGUARDANDO] Nenhuma transação disponível.")

if __name__ == "__main__":
    conectar_servidor()
