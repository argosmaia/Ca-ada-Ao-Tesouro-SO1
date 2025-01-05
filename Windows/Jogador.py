# Jogador.py corrigido
import socket
import json
import msvcrt
import threading
import time
import signal
from colorama import init, Fore, Style
import sys

class Jogador:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.idJogador = None
        self.estadoJogo = None
        self.ativo = True
        self.ultimaRenderizacao = ""
        init(autoreset=True)

        signal.signal(signal.SIGINT, self._tratadorSinal)
        signal.signal(signal.SIGTERM, self._tratadorSinal)

    def _tratadorSinal(self, signum, frame):
        self.ativo = False

    def limparTela(self):
        sys.stdout.write("\033[H")
        sys.stdout.flush()

    def conectar(self):
        try:
            self.socket.connect((self.host, self.port))
            self.idJogador = int(self.socket.recv(1024).decode())
            return True
        except socket.error as e:
            print(f"Erro de conexão: {e}")
            return False

    def enviarComando(self, comando):
        try:
            self.socket.send(json.dumps(comando).encode())
            resposta = self.socket.recv(1024).decode()
            return json.loads(resposta)
        except (socket.error, json.JSONDecodeError) as e:
            print(f"Erro de comunicação: {e}")
            self.ativo = False
            return None

    def atualizarEstadoJogo(self):
        resposta = self.enviarComando({'type': 'get_state'})
        if resposta:
            self.estadoJogo = resposta

    def gerarBufferTela(self):
        if not self.estadoJogo:
            return ""

        buffer = [Fore.YELLOW + "=== CAÇA AO TESOURO ===" + Style.RESET_ALL]
        buffer.append("   " + " ".join(str(i) for i in range(len(self.estadoJogo['map'][0]))))

        for i, linha in enumerate(self.estadoJogo['map']):
            linhaTexto = f"{i:2} "
            for celula in linha:
                if celula.isdigit():
                    linhaTexto += Fore.YELLOW + celula + " " + Style.RESET_ALL
                elif celula == 'X':
                    linhaTexto += Fore.CYAN + celula + " " + Style.RESET_ALL
                else:
                    linhaTexto += celula + " "
            buffer.append(linhaTexto)

        jogador = self.estadoJogo['jogadores'].get(str(self.idJogador), {})
        buffer.append(f"Pontuação: {Fore.GREEN}{jogador.get('score', 0)}{Style.RESET_ALL} | Tesouros restantes: {Fore.YELLOW}{self.estadoJogo['treasures_left']}{Style.RESET_ALL}")
        buffer.append("Controles: WASD/Setas para mover, E para entrar na sala, Q para sair")
        return "\n".join(buffer)

    def desenharTela(self):
        novaRenderizacao = self.gerarBufferTela()
        if novaRenderizacao != self.ultimaRenderizacao:
            self.limparTela()
            print(novaRenderizacao)
            self.ultimaRenderizacao = novaRenderizacao

    def processarEntrada(self):
        teclasMovimento = {
            b'w': 'up', b's': 'down', b'a': 'left', b'd': 'right',
            b'H': 'up', b'P': 'down', b'K': 'left', b'M': 'right'
        }

        while self.ativo:
            if msvcrt.kbhit():
                tecla = msvcrt.getch()
                if tecla in teclasMovimento:
                    self.enviarComando({'type': 'move', 'direction': teclasMovimento[tecla]})
                elif tecla in [b'e', b'E']:
                    self.enviarComando({'type': 'enter_room'})
                elif tecla in [b'q', b'Q']:
                    self.ativo = False

    def executar(self):
        if self.conectar():
            threading.Thread(target=self.processarEntrada, daemon=True).start()
            while self.ativo:
                self.atualizarEstadoJogo()
                self.desenharTela()
                time.sleep(0.1)

if __name__ == "__main__":
    Jogador().executar()
