import socket
import json
import msvcrt
import threading
import time
import signal
from colorama import init, Fore, Style
import sys

#
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
        pass

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

    def obterConteudoCelula(self, x, y):
        if not self.estadoJogo or 'jogadores' not in self.estadoJogo:
            return ('.', Style.RESET_ALL)
        
        # Verifica se há um jogador na célula
        for pid, dados in self.estadoJogo['jogadores'].items():
            if dados['position'] == [x, y] or dados['position'] == (x, y):  # Aceita tanto lista quanto tupla
                if str(pid) == str(self.idJogador):
                    return ('P', Fore.GREEN)  # Jogador atual em verde
                return ('J', Fore.RED)  # Outros jogadores em vermelho
        
        # Se não há jogador, retorna o conteúdo do mapa
        try:
            celula = self.estadoJogo['map'][x][y]
            if celula.isdigit():
                return (celula, Fore.YELLOW)  # Tesouros em amarelo
            elif celula == 'X':
                return (celula, Fore.CYAN)  # Entrada da sala em ciano
            return (celula, Style.RESET_ALL)
        except:
            return ('.', Style.RESET_ALL)

    def gerarBufferTela(self):
        if not self.estadoJogo:
            return ""

        buffer = []
        buffer.append(Fore.YELLOW + "=== CAÇA AO TESOURO ===" + Style.RESET_ALL)
        buffer.append("")

        # Adiciona índices das colunas
        buffer.append("   " + " ".join(str(i) for i in range(len(self.estadoJogo['map'][0]))))

        # Gera o mapa
        for i in range(len(self.estadoJogo['map'])):
            linha = f"{i:2} "
            for j in range(len(self.estadoJogo['map'][0])):
                conteudo, cor = self.obterConteudoCelula(i, j)
                linha += cor + conteudo + " " + Style.RESET_ALL
            buffer.append(linha)

        # Adiciona informações do jogador
        if str(self.idJogador) in self.estadoJogo['jogadores']:
            jogador = self.estadoJogo['jogadores'][str(self.idJogador)]
            buffer.append("")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)
            buffer.append(f"Pontuação: {Fore.GREEN}{jogador['score']}{Style.RESET_ALL} | "
                        f"Tesouros restantes: {Fore.YELLOW}{self.estadoJogo['treasures_left']}{Style.RESET_ALL}")

            # Verifica se o jogador está na entrada da sala do tesouro
            pos = jogador['position']
            if isinstance(pos, list):
                pos = tuple(pos)
            mapa = self.estadoJogo['map']
            for i in range(len(mapa)):
                if 'X' in mapa[i]:
                    j = mapa[i].index('X')
                    if pos == (i, j):
                        buffer.append(Fore.YELLOW + 
                                    f"Sala do tesouro! Pressione E para entrar ({self.estadoJogo['room_treasures']} restantes)" + 
                                    Style.RESET_ALL)

            buffer.append("\nControles: WASD/Setas para mover, E para entrar na sala, Q para sair")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)

        return "\n".join(buffer)

    def desenharTela(self):
        if not self.estadoJogo:
            return

        novaRenderizacao = self.gerarBufferTela()
        if novaRenderizacao != self.ultimaRenderizacao:
            self.limparTela()
            print(novaRenderizacao)
            self.ultimaRenderizacao = novaRenderizacao

    def teclaValida(self, tecla):
        teclasValidas = [
            b'w', b'a', b's', b'd',
            b'W', b'A', b'S', b'D',
            b'e', b'E',
            b'q', b'Q',
            b'H', b'P', b'K', b'M',
            b'\xe0'
        ]
        return tecla in teclasValidas

    def processarEntrada(self):
        mapeamentoTeclas = {
            b'H': 'up',    # Seta para cima
            b'P': 'down',  # Seta para baixo
            b'K': 'left',  # Seta para esquerda
            b'M': 'right', # Seta para direita
            b'w': 'up',
            b'W': 'up',
            b's': 'down',
            b'S': 'down',
            b'a': 'left',
            b'A': 'left',
            b'd': 'right',
            b'D': 'right'
        }
        
        while self.ativo:
            try:
                if msvcrt.kbhit():
                    tecla = msvcrt.getch()
                    
                    if not self.teclaValida(tecla):
                        continue
                    
                    if tecla in mapeamentoTeclas:
                        resposta = self.enviarComando({
                            'type': 'move',
                            'direction': mapeamentoTeclas[tecla]
                        })
                        if resposta:
                            self.estadoJogo = resposta
                    
                    elif tecla == b'\xe0':  # Tecla especial (setas)
                        tecla = msvcrt.getch()
                        if tecla in mapeamentoTeclas:
                            resposta = self.enviarComando({
                                'type': 'move',
                                'direction': mapeamentoTeclas[tecla]
                            })
                            if resposta:
                                self.estadoJogo = resposta
                    
                    elif tecla in [b'e', b'E']:
                        resposta = self.enviarComando({'type': 'enter_room'})
                        if resposta and resposta.get('status') == 'success':
                            self.estadoJogo = resposta['state']
                            time.sleep(0.1)
                    elif tecla in [b'q', b'Q']:
                        self.ativo = False
                        break
            except Exception as e:
                print(f"Erro ao processar entrada: {e}")
                continue

    def configurarTerminal(self):
        print("\033[2J", end='')
        print("\033[?25l", end='')
        print("\033[H", end='')
        sys.stdout.flush()

    def restaurarTerminal(self):
        print("\033[?25h", end='')
        sys.stdout.flush()

    def executar(self):
        if self.conectar():
            try:
                self.configurarTerminal()
                
                threadEntrada = threading.Thread(target=self.processarEntrada)
                threadEntrada.daemon = True
                threadEntrada.start()

                while self.ativo:
                    try:
                        self.atualizarEstadoJogo()
                        self.desenharTela()
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"Erro no loop principal: {e}")
                        continue
            finally:
                self.restaurarTerminal()
                self.socket.close()

if __name__ == "__main__":
    while True:
        try:
            cliente = Jogador()
            cliente.executar()
            if not cliente.ativo:
                break
        except Exception as e:
            print(f"Erro ao iniciar cliente: {e}")
            continue