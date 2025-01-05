# Jogo.py corrigido para movimentação independente de jogadores
import socket
import threading
import json
import time
import random
from threading import Lock
from colorama import init, Fore, Style

class Jogo:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.tamanhoMapa = 8
        self.numeroTesouros = 15
        self.mapa = [["." for _ in range(self.tamanhoMapa)] for _ in range(self.tamanhoMapa)]
        self.jogadores = {}
        self.tesourosColetados = 0
        self.tesourosTotais = self.numeroTesouros
        self.travaMapa = Lock()
        self.jogoFinalizado = False

        # Sala do Tesouro
        self.tamanhoSala = self.tamanhoMapa // 2
        self.posicaoSala = (random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1))
        self.salaTesouro = [["." for _ in range(self.tamanhoSala)] for _ in range(self.tamanhoSala)]
        self.tesourosNaSala = 10
        self.salaOcupada = False
        self.jogadorNaSala = None
        self.travaSala = Lock()

        init(autoreset=True)
        self._inicializarMapa()
        self.socketServidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketServidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socketServidor.bind((self.host, self.port))
        self.socketServidor.listen(5)

    def _inicializarMapa(self):
        # Coloca tesouros no mapa principal
        for _ in range(self.numeroTesouros):
            while True:
                x, y = random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1)
                if self.mapa[x][y] == "." and (x, y) != self.posicaoSala:
                    self.mapa[x][y] = str(random.randint(1, 9))
                    break

        # Marca a entrada da sala do tesouro
        self.mapa[self.posicaoSala[0]][self.posicaoSala[1]] = "X"

        # Coloca tesouros na sala do tesouro
        tesourosColocados = 0
        while tesourosColocados < self.tesourosNaSala:
            x, y = random.randint(0, self.tamanhoSala - 1), random.randint(0, self.tamanhoSala - 1)
            if self.salaTesouro[x][y] == ".":
                self.salaTesouro[x][y] = str(random.randint(5, 15))
                tesourosColocados += 1

    def moverJogador(self, idJogador, direcao):
        with self.travaMapa:
            jogador = self.jogadores.get(idJogador)
            if not jogador:
                return {'status': 'error', 'message': 'Jogador não encontrado'}

            if jogador.get('naSala'):
                mapaAtual = self.salaTesouro
                tamanhoAtual = self.tamanhoSala
            else:
                mapaAtual = self.mapa
                tamanhoAtual = self.tamanhoMapa

            x, y = jogador['position']
            novoX, novoY = x, y

            if direcao == 'up' and x > 0:
                novoX -= 1
            elif direcao == 'down' and x < tamanhoAtual - 1:
                novoX += 1
            elif direcao == 'left' and y > 0:
                novoY -= 1
            elif direcao == 'right' and y < tamanhoAtual - 1:
                novoY += 1

            if (novoX, novoY) != (x, y):
                jogador['position'] = (novoX, novoY)
                if mapaAtual[novoX][novoY].isdigit():
                    jogador['score'] += int(mapaAtual[novoX][novoY])
                    self.tesourosColetados += 1
                    mapaAtual[novoX][novoY] = "."

            return self.obterEstadoJogo(idJogador)

    def entrarSalaTesouro(self, idJogador):
        with self.travaSala:
            jogador = self.jogadores.get(idJogador)
            if not jogador:
                return {'status': 'error', 'message': 'Jogador não encontrado'}

            if self.salaOcupada:
                return {'status': 'error', 'message': 'Sala ocupada, aguarde sua vez'}

            if jogador['position'] != self.posicaoSala:
                return {'status': 'error', 'message': 'Você não está na entrada da sala do tesouro'}

            self.salaOcupada = True
            self.jogadorNaSala = idJogador
            jogador['naSala'] = True
            jogador['position'] = (0, 0)

            threading.Thread(target=self._sairSalaAposTempo, args=(idJogador,), daemon=True).start()

            return {'status': 'success', 'state': self.obterEstadoJogo(idJogador)}

    def _sairSalaAposTempo(self, idJogador):
        time.sleep(10)
        self.sairSalaTesouro(idJogador)

    def sairSalaTesouro(self, idJogador):
        with self.travaSala:
            jogador = self.jogadores.get(idJogador)
            if jogador and jogador.get('naSala'):
                jogador['naSala'] = False
                jogador['position'] = self.posicaoSala
                self.salaOcupada = False
                self.jogadorNaSala = None

    def obterEstadoJogo(self, idJogador):
        jogador = self.jogadores.get(idJogador, {})
        if jogador.get('naSala'):
            return {
                'map': self.salaTesouro,
                'jogadores': {k: v for k, v in self.jogadores.items() if v.get('naSala')},
                'treasures_left': None  
            }
        else:
            mapaComJogadores = [linha[:] for linha in self.mapa]
            for pid, dados in self.jogadores.items():
                if not dados.get('naSala'):
                    x, y = dados['position']
                    if pid == idJogador:
                        mapaComJogadores[x][y] = 'P'
                    else:
                        mapaComJogadores[x][y] = 'J'

            return {
                'map': mapaComJogadores,
                'jogadores': self.jogadores,
                'treasures_left': None  # Ou remova esta linha completamente
            }

    def finalizarJogo(self):
        with self.travaMapa:  # Garante que apenas uma thread possa finalizar o jogo
            if self.jogoFinalizado:  # Verifica se o jogo já foi finalizado
                return
            self.jogoFinalizado = True
            # Identificar o maior score
            pontuacoes = [jogador['score'] for jogador in self.jogadores.values()]
            maior_pontuacao = max(pontuacoes, default=0)
            vencedores = [
                (id_jogador, dados) for id_jogador, dados in self.jogadores.items()
                if dados['score'] == maior_pontuacao
            ]

            if len(vencedores) > 1:
                print(Fore.RED + "\nEmpate! Múltiplos jogadores alcançaram a mesma pontuação máxima." + Style.RESET_ALL)
            else:
                id_vencedor, dados_vencedor = vencedores[0]
                print(Fore.GREEN + f"\nJogo finalizado! Jogador {id_vencedor} venceu com {dados_vencedor['score']} pontos!" + Style.RESET_ALL)


    def processarComando(self, idJogador, comando):
        if comando['type'] == 'move':
            return self.moverJogador(idJogador, comando['direction'])
        elif comando['type'] == 'enter_room':
            return self.entrarSalaTesouro(idJogador)
        elif comando['type'] == 'get_state':
            return self.obterEstadoJogo(idJogador)
        return {'status': 'error', 'message': 'Comando inválido'}

    def gerenciarCliente(self, socketCliente, idJogador):
        try:
            while True:
                dados = socketCliente.recv(1024).decode()
                if not dados:
                    break

                comando = json.loads(dados)
                resposta = self.processarComando(idJogador, comando)
                socketCliente.send(json.dumps(resposta).encode())

                if all(all(celula == "." for celula in linha) for linha in self.mapa) and all(all(celula == "." for celula in linha) for linha in self.salaTesouro):
                    self.finalizarJogo()
                    break

        except (json.JSONDecodeError, socket.error):
            pass
        finally:
            self.jogadores.pop(idJogador, None)
            socketCliente.close()

    def adicionarJogador(self, idJogador):
        while True:
            x, y = random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1)
            if self.mapa[x][y] == ".":
                self.jogadores[idJogador] = {'position': (x, y), 'score': 0, 'naSala': False}
                break

    def executar(self):
        print(Fore.CYAN + f"Servidor iniciado em {self.host}:{self.port}" + Style.RESET_ALL)
        try:
            while True:
                socketCliente, _ = self.socketServidor.accept()
                idJogador = random.randint(1000, 9999)
                self.adicionarJogador(idJogador)
                socketCliente.send(str(idJogador).encode())

                threading.Thread(target=self.gerenciarCliente, args=(socketCliente, idJogador), daemon=True).start()
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nDesligando servidor..." + Style.RESET_ALL)
        finally:
            self.socketServidor.close()

if __name__ == "__main__":
    Jogo().executar() #