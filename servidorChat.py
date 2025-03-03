import socket
import threading
import requests

HOST = '0.0.0.0'  # Escuta em todas as interfaces
PORT = 31471
TELEGRAM_BOT_TOKEN = '6083297671:AAEx6pVBTfsLZ0-Kqq048eVqaLQKgi8sVW4'
TELEGRAM_CHAT_ID = '1002444177777'

# Lista de transações pendentes e validadas
transacoes_pendentes = []
transacoes_validadas = {}
clientes = {}

def enviar_mensagem_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem}
    requests.post(url, json=payload)

def handle_client(conn, addr):
    print(f"[NOVA CONEXÃO] {addr} conectado.")
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode().strip()
            print(f"[RECEBIDO] {addr}: {msg}")
            
            if msg.startswith("G "):
                nome_cliente = msg.split(" ")[1]
                if transacoes_pendentes:
                    transacao = transacoes_pendentes.pop(0)
                    clientes[nome_cliente] = transacao
                    resposta = f"T {transacao}"
                else:
                    resposta = "W"  # Não há transações disponíveis
                conn.sendall(resposta.encode())
            
            elif msg.startswith("S "):
                parts = msg.split(" ")
                num_transacao, nonce = parts[1], parts[2]
                transacoes_validadas[num_transacao] = nonce
                resposta = f"V {num_transacao}"
                conn.sendall(resposta.encode())
                
                # Enviar notificação ao Telegram
                mensagem = f"Transação {num_transacao} validada com nonce {nonce}!"
                enviar_mensagem_telegram(mensagem)
        except Exception as e:
            print(f"[ERRO] {e}")
            break
    print(f"[DESCONECTADO] {addr}")
    conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVIDOR RODANDO] Aguardando conexões na porta {PORT}...")
    
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ATIVAS] {threading.active_count() - 1} conexões ativas.")

if __name__ == "__main__":
    start_server()
