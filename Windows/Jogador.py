import socket
import json
import msvcrt
import threading
import time
import signal
from colorama import init, Fore, Style
import sys

class ClienteJogo:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.idJogador = None
        self.estadoJogo = None
        self.executando = True
        self.ultimoRender = ""
        init(autoreset=True)
        
        signal.signal(signal.SIGINT, self._manipuladorSinal)
        signal.signal(signal.SIGTERM, self._manipuladorSinal)
    
    def _manipuladorSinal(self, signum, frame):
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
            self.executando = False
            return None
    
    def atualizarEstadoJogo(self):
        resposta = self.enviarComando({'type': 'get_state'})
        if resposta:
            self.estadoJogo = resposta

    def obterConteudoCelula(self, x, y):
        # Primeiro verifica se há um jogador na célula
        if self.estadoJogo and 'players' in self.estadoJogo:
            for pid, pdata in self.estadoJogo['players'].items():
                if pdata['position'] == (x, y):
                    if str(pid) == str(self.idJogador):
                        return ('P', Fore.GREEN)
                    return ('J', Fore.RED)
        
        # Se não há jogador, retorna o conteúdo do mapa
        celula = self.estadoJogo['map'][x][y]
        if celula.isdigit():
            return (celula, Fore.YELLOW)
        elif celula == 'X':
            return (celula, Fore.CYAN)
        return (celula, Style.RESET_ALL)

    def gerarBufferTela(self):
        if not self.estadoJogo:
            return ""

        buffer = []
        buffer.append(Fore.YELLOW + "=== CAÇA AO TESOURO ===" + Style.RESET_ALL)
        buffer.append("")

        # Mapa com índices
        buffer.append("   " + " ".join([str(i) for i in range(len(self.estadoJogo['map'][0]))]))
        
        for i, linha in enumerate(self.estadoJogo['map']):
            linhaBuffer = f"{i:2} "
            for j, _ in enumerate(linha):
                conteudo, cor = self.obterConteudoCelula(i, j)
                linhaBuffer += cor + conteudo + " " + Style.RESET_ALL
            buffer.append(linhaBuffer)
        
        jogador = self.estadoJogo['players'].get(str(self.idJogador))
        if jogador:
            buffer.append("")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)
            buffer.append(f"Pontuação: {Fore.GREEN}{jogador['score']}{Style.RESET_ALL} | "
                        f"Tesouros restantes: {Fore.YELLOW}{self.estadoJogo['treasures_left']}{Style.RESET_ALL}")
            
            posicaoAtual = jogador['position']
            for i, linha in enumerate(self.estadoJogo['map']):
                if 'X' in linha and posicaoAtual == (i, linha.index('X')):
                    buffer.append(Fore.YELLOW + 
                                f"Sala do tesouro! Pressione E para entrar ({self.estadoJogo['room_treasures']} restantes)" + 
                                Style.RESET_ALL)
            
            buffer.append("\nControles: WASD/Setas para mover, E para entrar na sala, Q para sair")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)

        return "\n".join(buffer)
    
    def desenharTela(self):
        if not self.estadoJogo:
            return
        
        novoRender = self.gerarBufferTela()
        
        if novoRender != self.ultimoRender:
            self.limparTela()
            print(novoRender)
            self.ultimoRender = novoRender
    
    def chaveValida(self, chave):
        chavesValidas = [
            b'w', b'a', b's', b'd',
            b'W', b'A', b'S', b'D',
            b'e', b'E',  # Trocado de 'k'/'K' para 'e'/'E'
            b'q', b'Q',
            b'H', b'P', b'K', b'M',
            b'\xe0'
        ]
        return chave in chavesValidas
    
    def tratarEntrada(self):
        mapeamentoTeclas = {
            b'H': 'up',    
            b'P': 'down',  
            b'K': 'left',  
            b'M': 'right', 
            b'w': 'up',
            b'W': 'up',
            b's': 'down',
            b'S': 'down',
            b'a': 'left',
            b'A': 'left',
            b'd': 'right',
            b'D': 'right'
        }
        
        while self.executando:
            try:
                if msvcrt.kbhit():
                    chave = msvcrt.getch()
                    
                    if not self.chaveValida(chave):
                        continue
                    
                    if chave in mapeamentoTeclas:
                        resposta = self.enviarComando({
                            'type': 'move',
                            'direction': mapeamentoTeclas[chave]
                        })
                        if resposta:
                            self.estadoJogo = resposta
                    
                    elif chave == b'\xe0':
                        chave = msvcrt.getch()
                        if chave in mapeamentoTeclas:
                            resposta = self.enviarComando({
                                'type': 'move',
                                'direction': mapeamentoTeclas[chave]
                            })
                            if resposta:
                                self.estadoJogo = resposta
                    
                    elif chave in [b'e', b'E']:  # Trocado de 'k'/'K' para 'e'/'E'
                        resposta = self.enviarComando({'type': 'enter_room'})
                        if resposta and resposta.get('status') == 'success':
                            self.estadoJogo = resposta['state']
                            time.sleep(0.1)

                    elif chave in [b'q', b'Q']:
                        self.executando = False
                        break
            
            except Exception:
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
                
                threadEntrada = threading.Thread(target=self.tratarEntrada)
                threadEntrada.daemon = True
                threadEntrada.start()

                while self.executando:
                    try:
                        self.atualizarEstadoJogo()
                        self.desenharTela()
                        time.sleep(0.05)
                    except Exception:
                        continue
                
            finally:
                self.restaurarTerminal()
                self.socket.close()

if __name__ == "__main__":
    while True:
        try:
            cliente = ClienteJogo()
            cliente.executar()
            if not cliente.executando:
                break
        except Exception:
            continue
