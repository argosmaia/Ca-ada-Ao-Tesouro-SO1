import socket
import threading
import json
import time
import random
from threading import Lock, Event
import os
from colorama import init, Fore, Style

class Jogo:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.tamanhoMapa = 8
        self.tamanhoSala = 4
        self.numeroTesouros = 15
        self.mapa = [["." for _ in range(self.tamanhoMapa)] for _ in range(self.tamanhoMapa)]
        self.salaTesouro = None
        self.travaMapa = Lock()
        self.travaJogador = Lock()
        self.ativo = True
        
        # Estado do jogo
        self.jogadores = {}
        self.jogadoresSalaTesouro = set()
        self.jogadoresQuePoderamEntrar = set()  # Novo: conjunto para controlar quem já entrou
        self.tesourosColetados = 0
        self.tesourosTotais = self.numeroTesouros + 5
        
        # Controle de acesso à sala do tesouro
        self.travaSala = Lock()
        self.salaOcupada = False
        self.tempoLimiteSala = 30  # Tempo limite em segundos
        self.jogadorAtualNaSala = None
        self.timerSala = None
        
        # Sala do tesouro
        self.posicaoSalaX = random.randint(0, self.tamanhoMapa - 1)
        self.posicaoSalaY = random.randint(0, self.tamanhoMapa - 1)
        self.tesourosNaSala = 5
        
        init(autoreset=True)
        self._inicializarMapas()
        self.socketServidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketServidor.bind((self.host, self.port))
        self.socketServidor.listen(5)

    def _inicializarMapas(self):
        with self.travaMapa:
            # Inicializa mapa principal
            for _ in range(self.numeroTesouros):
                while True:
                    x, y = random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1)
                    if self.mapa[x][y] == "." and (x, y) != (self.posicaoSalaX, self.posicaoSalaY):
                        self.mapa[x][y] = str(random.randint(1, 9))
                        break
            
            # Marca a entrada da sala do tesouro
            self.mapa[self.posicaoSalaX][self.posicaoSalaY] = "X"
            
            # Inicializa a sala do tesouro
            self._inicializarSalaTesouro()

    def _inicializarSalaTesouro(self):
        self.salaTesouro = [["." for _ in range(self.tamanhoSala)] 
                            for _ in range(self.tamanhoSala)]
        
        tesourosColocados = 0
        while tesourosColocados < self.tesourosNaSala:
            x = random.randint(0, self.tamanhoSala - 1)
            y = random.randint(0, self.tamanhoSala - 1)
            if self.salaTesouro[x][y] == ".":
                self.salaTesouro[x][y] = str(random.randint(5, 9))
                tesourosColocados += 1

    def _temporizadorSala(self, idJogador):
        time.sleep(self.tempoLimiteSala)
        with self.travaSala:
            if self.jogadorAtualNaSala == idJogador:
                self.sairSalaTesouro(idJogador)
                self.salaOcupada = False
                self.jogadorAtualNaSala = None
                self.jogadoresQuePoderamEntrar.add(idJogador)  # Marca que este jogador já teve sua vez

    def entrarSalaTesouro(self, idJogador):
        with self.travaSala:
            jogador = self.jogadores.get(idJogador)
            if not jogador:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            # Verifica se o jogador já teve sua vez
            if idJogador in self.jogadoresQuePoderamEntrar:
                return {'status': 'error', 'message': 'Você já teve sua vez na sala do tesouro'}
            
            # Verifica se está na posição correta
            x, y = jogador['position']
            if (x, y) != (self.posicaoSalaX, self.posicaoSalaY):
                return {'status': 'error', 'message': 'Não está na entrada'}
            
            # Verifica se a sala está ocupada
            if self.salaOcupada:
                return {'status': 'error', 'message': 'Sala ocupada por outro jogador'}
            
            # Ocupa a sala
            self.salaOcupada = True
            self.jogadorAtualNaSala = idJogador
            self.jogadoresSalaTesouro.add(idJogador)
            self.jogadores[idJogador]['position'] = (0, 0)
            
            # Inicia o temporizador
            self.timerSala = threading.Thread(target=self._temporizadorSala, args=(idJogador,))
            self.timerSala.daemon = True
            self.timerSala.start()
            
            return {
                'status': 'success',
                'message': f'Bem-vindo à sala do tesouro! Você tem {self.tempoLimiteSala} segundos',
                'state': self.obterEstadoJogo(idJogador)
            }

    def sairSalaTesouro(self, idJogador):
        with self.travaSala:
            if idJogador in self.jogadoresSalaTesouro:
                self.jogadoresSalaTesouro.remove(idJogador)
                self.jogadores[idJogador]['position'] = (self.posicaoSalaX, self.posicaoSalaY)
                
                # Libera a sala
                if self.jogadorAtualNaSala == idJogador:
                    self.salaOcupada = False
                    self.jogadorAtualNaSala = None
                
                return {
                    'status': 'success',
                    'message': 'Tempo esgotado! Voltou ao mapa principal',
                    'state': self.obterEstadoJogo(idJogador)
                }
            return {'status': 'error', 'message': 'Jogador não está na sala'}

    def exibirEstado(self):
        os.system('cls')
        print(Fore.CYAN + "==== Status do Servidor ====" + Style.RESET_ALL)
        print(f"Servidor rodando em {self.host}:{self.port}")
        print(f"Jogadores conectados: {len(self.jogadores)}")
        print(f"Jogadores na sala do tesouro: {len(self.jogadoresSalaTesouro)}")
        print(f"Tesouros coletados: {self.tesourosColetados}/{self.tesourosTotais}")
        print(f"Tesouros na sala especial: {self.tesourosNaSala}")
        
        if self.jogadorAtualNaSala:
            print(f"\nJogador {self.jogadorAtualNaSala} está na sala do tesouro")
        
        print("\nPlacar:")
        for pid, jogador in self.jogadores.items():
            statusSala = "na sala do tesouro" if pid in self.jogadoresSalaTesouro else "no mapa principal"
            jaJogou = "já teve sua vez" if pid in self.jogadoresQuePoderamEntrar else "ainda não entrou na sala"
            print(f"Jogador {pid}: {jogador['score']} pts ({statusSala}, {jaJogou})")
        
        print("\nCtrl+C para sair")
        print(Fore.CYAN + "=========================" + Style.RESET_ALL)

    def obterEstadoJogo(self, idJogador=None):
        with self.travaJogador:
            if idJogador in self.jogadoresSalaTesouro:
                return {
                    'map': self.salaTesouro,
                    'jogadores': {pid: dados for pid, dados in self.jogadores.items() 
                              if pid in self.jogadoresSalaTesouro},
                    'treasures_left': self.tesourosTotais - self.tesourosColetados,
                    'room_treasures': self.tesourosNaSala,
                    'naSalaTesouro': True,
                    'mapaTam': self.tamanhoSala
                }
            else:
                return {
                    'map': self.mapa,
                    'jogadores': {pid: dados for pid, dados in self.jogadores.items() 
                              if pid not in self.jogadoresSalaTesouro},
                    'treasures_left': self.tesourosTotais - self.tesourosColetados,
                    'room_treasures': self.tesourosNaSala,
                    'naSalaTesouro': False,
                    'mapaTam': self.tamanhoMapa
                }

    def gerenciarCliente(self, socketCliente, idJogador):
        try:
            while self.ativo:
                try:
                    dados = socketCliente.recv(1024).decode()
                    if not dados:
                        break
                    
                    comando = json.loads(dados)
                    resposta = self.processarComando(idJogador, comando)
                    socketCliente.send(json.dumps(resposta).encode())
                    
                    self.exibirEstado()
                    
                    if self.tesourosColetados >= self.tesourosTotais:
                        self.finalizarJogo()
                        
                except (json.JSONDecodeError, socket.error):
                    break
        finally:
            self.removerJogador(idJogador)
            socketCliente.close()
            self.exibirEstado()

    def processarComando(self, idJogador, comando):
        tipoComando = comando.get('type')
        if tipoComando == 'move':
            return self.moverJogador(idJogador, comando['direction'])
        elif tipoComando == 'enter_room':
            return self.entrarSalaTesouro(idJogador)
        elif tipoComando == 'leave_room':
            return self.sairSalaTesouro(idJogador)
        elif tipoComando == 'get_state':
            return self.obterEstadoJogo(idJogador)
        return {'status': 'error', 'message': 'Comando inválido'}

    def moverJogador(self, idJogador, direcao):
        with self.travaMapa:
            if idJogador not in self.jogadores:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            naSalaTesouro = idJogador in self.jogadoresSalaTesouro
            mapaAtual = self.salaTesouro if naSalaTesouro else self.mapa
            tamanhoAtual = self.tamanhoSala if naSalaTesouro else self.tamanhoMapa
            
            x, y = self.jogadores[idJogador]['position']
            novoX, novoY = x, y
            
            if direcao == 'up' and x > 0:
                novoX = x - 1
            elif direcao == 'down' and x < tamanhoAtual - 1:
                novoX = x + 1
            elif direcao == 'left' and y > 0:
                novoY = y - 1
            elif direcao == 'right' and y < tamanhoAtual - 1:
                novoY = y + 1
            
            if (novoX, novoY) != (x, y):
                self.jogadores[idJogador]['position'] = (novoX, novoY)
                
                if mapaAtual[novoX][novoY].isdigit():
                    valor = int(mapaAtual[novoX][novoY])
                    self.jogadores[idJogador]['score'] += valor
                    self.tesourosColetados += 1
                    mapaAtual[novoX][novoY] = "."
                    if naSalaTesouro:
                        self.tesourosNaSala -= 1
            
            return self.obterEstadoJogo(idJogador)

    def adicionarJogador(self, idJogador):
        with self.travaJogador:
            posicaoX, posicaoY = random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1)
            while self.mapa[posicaoX][posicaoY] != ".":
                posicaoX, posicaoY = random.randint(0, self.tamanhoMapa - 1), random.randint(0, self.tamanhoMapa - 1)
            
            self.jogadores[idJogador] = {
                'position': (posicaoX, posicaoY),
                'score': 0
            }

    def removerJogador(self, idJogador):
        with self.travaJogador:
            if idJogador in self.jogadores:
                del self.jogadores[idJogador]
            if idJogador in self.jogadoresSalaTesouro:
                self.jogadoresSalaTesouro.remove(idJogador)

    def finalizarJogo(self):
        self.ativo = False
        if self.jogadores:
            idGanhador = max(self.jogadores.items(), key=lambda x: x[1]['score'])[0]
            pontuacaoGanhador = self.jogadores[idGanhador]['score']
            print(Fore.GREEN + f"\nJogo finalizado! Jogador {idGanhador} venceu com {pontuacaoGanhador} pontos!" + Style.RESET_ALL)
        return {
            'status': 'game_over',
            'winner': idGanhador if self.jogadores else None,
            'score': pontuacaoGanhador if self.jogadores else 0
        }

    def executar(self):
        print(Fore.CYAN + f"Servidor iniciado em {self.host}:{self.port}" + Style.RESET_ALL)
        try:
            self.exibirEstado()
            while self.ativo:
                socketCliente, endereco = self.socketServidor.accept()
                idJogador = random.randint(1000, 9999)
                self.adicionarJogador(idJogador)
                
                socketCliente.send(str(idJogador).encode())
                
                thread = threading.Thread(target=self.gerenciarCliente, 
                                       args=(socketCliente, idJogador))
                thread.daemon = True
                thread.start()
                
                self.exibirEstado()
                
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nDesligando servidor..." + Style.RESET_ALL)
        finally:
            self.ativo = False
            self.socketServidor.close()

def main():
    # Configurações do servidor
    host = 'localhost'
    porta = 5000
    try:
        # Criar e iniciar o servidor
        print(Fore.CYAN + "Iniciando servidor de Caça ao Tesouro..." + Style.RESET_ALL)
        servidor = Jogo(host=host, port=porta)
        servidor.executar() #
    except Exception as e:
        print(Fore.RED + f"Erro ao iniciar servidor: {e}" + Style.RESET_ALL)
    finally:
        print(Fore.YELLOW + "Servidor finalizado." + Style.RESET_ALL)

if __name__ == "__main__":
    main()