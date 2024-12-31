import socket
import threading
import json
import time
import random
from threading import Lock
import os
from colorama import init, Fore, Style

class Jogo:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.mapaTam = 8
        self.salaTam = 4  # Tamanho da sala do tesouro
        self.numTesouros = 15
        self.mapa = [["." for _ in range(self.mapaTam)] for _ in range(self.mapaTam)]
        self.salaTesouro = None
        self.travaMapa = Lock()
        self.travaJogador = Lock()
        self.ativo = True
        
        # Game state
        self.jogadores = {}
        self.jogadoresSalaTesouro = set()  # Conjunto para rastrear jogadores na sala
        self.tesourosColetados = 0
        self.tesourosTotais = self.numTesouros + 5
        
        # Treasure room
        self.salaTesouro_x = random.randint(0, self.mapaTam - 1)
        self.salaTesouro_y = random.randint(0, self.mapaTam - 1)
        self.tesourosNaSala = 5
        self.travaSala = Lock()
        
        init(autoreset=True)
        self._initialize_maps()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
    
    def _initialize_maps(self):
        with self.travaMapa:
            # Inicializa mapa principal
            for _ in range(self.numTesouros):
                while True:
                    x, y = random.randint(0, self.mapaTam - 1), random.randint(0, self.mapaTam - 1)
                    if self.mapa[x][y] == "." and (x, y) != (self.salaTesouro_x, self.salaTesouro_y):
                        self.mapa[x][y] = str(random.randint(1, 9))
                        break
            
            # Marca a entrada da sala do tesouro
            self.mapa[self.salaTesouro_x][self.salaTesouro_y] = "X"
            
            # Inicializa a sala do tesouro
            self._initialize_salaTesouro()
    
    def _initialize_salaTesouro(self):
        self.salaTesouro = [["." for _ in range(self.salaTam)] 
                            for _ in range(self.salaTam)]
        
        # Coloca tesouros na sala
        tesourosColocados = 0
        while tesourosColocados < self.tesourosNaSala:
            x = random.randint(0, self.salaTam - 1)
            y = random.randint(0, self.salaTam - 1)
            if self.salaTesouro[x][y] == ".":
                self.salaTesouro[x][y] = str(random.randint(5, 9))  # Tesouros maiores na sala especial
                tesourosColocados += 1
    
    def pegaJogo(self, jogadorId=None):
        with self.travaJogador:
            if jogadorId in self.jogadoresSalaTesouro:
                return {
                    'map': self.salaTesouro,
                    'jogadores': {pid: data for pid, data in self.jogadores.items() 
                              if pid in self.jogadoresSalaTesouro},
                    'treasures_left': self.tesourosTotais - self.tesourosColetados,
                    'room_treasures': self.tesourosNaSala,
                    'naSalaTesouro': True,
                    'mapaTam': self.salaTam
                }
            else:
                return {
                    'map': self.mapa,
                    'jogadores': {pid: data for pid, data in self.jogadores.items() 
                              if pid not in self.jogadoresSalaTesouro},
                    'treasures_left': self.tesourosTotais - self.tesourosColetados,
                    'room_treasures': self.tesourosNaSala,
                    'naSalaTesouro': False,
                    'mapaTam': self.mapaTam
                }
    
    def handle_client(self, client_socket, jogadorId):
        try:
            while self.ativo:
                try:
                    data = client_socket.recv(1024).decode()
                    if not data:
                        break
                    
                    comando = json.loads(data)
                    response = self.processosComando(jogadorId, comando)
                    client_socket.send(json.dumps(response).encode())
                    
                    self.display()
                    
                    if self.tesourosColetados >= self.tesourosTotais:
                        self.fim()
                        
                except (json.JSONDecodeError, socket.error):
                    break
        finally:
            self.removerJogador(jogadorId)
            client_socket.close()
            self.display()
    
    def processosComando(self, jogadorId, comando):
        cmd_type = comando.get('type')
        if cmd_type == 'move':
            return self.moverJogador(jogadorId, comando['direction'])
        elif cmd_type == 'enter_room':
            return self.entrarSalaTesouro(jogadorId)
        elif cmd_type == 'leave_room':
            return self.sairSalaTesouro(jogadorId)
        elif cmd_type == 'get_state':
            return self.pegaJogo(jogadorId)
        return {'status': 'error', 'message': 'Comando inválido'}
    
    def moverJogador(self, jogadorId, direction):
        with self.travaMapa:
            if jogadorId not in self.jogadores:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            naSalaTesouro = jogadorId in self.jogadoresSalaTesouro
            mapaAtual = self.salaTesouro if naSalaTesouro else self.mapa
            mapaTam = self.salaTam if naSalaTesouro else self.mapaTam
            
            x, y = self.jogadores[jogadorId]['position']
            novoX, novoY = x, y
            
            if direction == 'up' and x > 0:
                novoX = x - 1
            elif direction == 'down' and x < mapaTam - 1:
                novoX = x + 1
            elif direction == 'left' and y > 0:
                novoY = y - 1
            elif direction == 'right' and y < mapaTam - 1:
                novoY = y + 1
            
            if (novoX, novoY) != (x, y):
                self.jogadores[jogadorId]['position'] = (novoX, novoY)
                
                if mapaAtual[novoX][novoY].isdigit():
                    value = int(mapaAtual[novoX][novoY])
                    self.jogadores[jogadorId]['score'] += value
                    self.tesourosColetados += 1
                    mapaAtual[novoX][novoY] = "."
                    if naSalaTesouro:
                        self.tesourosNaSala -= 1
            
            return self.pegaJogo(jogadorId)
    
    def entrarSalaTesouro(self, jogadorId):
        with self.travaSala:
            player = self.jogadores.get(jogadorId)
            if not player:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            x, y = player['position']
            if (x, y) != (self.salaTesouro_x, self.salaTesouro_y):
                return {'status': 'error', 'message': 'Não está na entrada'}
            
            # Move o jogador para a sala do tesouro
            self.jogadoresSalaTesouro.add(jogadorId)
            self.jogadores[jogadorId]['position'] = (0, 0)  # Posição inicial na sala
            
            return {
                'status': 'success',
                'message': 'Bem-vindo à sala do tesouro! Pressione ESC para sair',
                'state': self.pegaJogo(jogadorId)
            }
    
    def sairSalaTesouro(self, jogadorId):
        with self.travaSala:
            if jogadorId in self.jogadoresSalaTesouro:
                self.jogadoresSalaTesouro.remove(jogadorId)
                self.jogadores[jogadorId]['position'] = (self.salaTesouro_x, self.salaTesouro_y)
                
                return {
                    'status': 'success',
                    'message': 'Voltou ao mapa principal',
                    'state': self.pegaJogo(jogadorId)
                }
            return {'status': 'error', 'message': 'Jogador não está na sala'}
    
    def addJogador(self, jogadorId):
        with self.travaJogador:
            inicioX, inicioY = random.randint(0, self.mapaTam - 1), random.randint(0, self.mapaTam - 1)
            while self.mapa[inicioX][inicioY] != ".":
                inicioX, inicioY = random.randint(0, self.mapaTam - 1), random.randint(0, self.mapaTam - 1)
            
            self.jogadores[jogadorId] = {
                'position': (inicioX, inicioY),
                'score': 0
            }
    
    def removerJogador(self, jogadorId):
        with self.travaJogador:
            if jogadorId in self.jogadores:
                del self.jogadores[jogadorId]
            if jogadorId in self.jogadoresSalaTesouro:
                self.jogadoresSalaTesouro.remove(jogadorId)
    
    def display(self):
        os.system('cls')
        print(Fore.CYAN + "==== Status do Servidor ====" + Style.RESET_ALL)
        print(f"Servidor rodando em {self.host}:{self.port}")
        print(f"Jogadores conectados: {len(self.jogadores)}")
        print(f"Jogadores na sala do tesouro: {len(self.jogadoresSalaTesouro)}")
        print(f"Tesouros coletados: {self.tesourosColetados}/{self.tesourosTotais}")
        print(f"Tesouros na sala especial: {self.tesourosNaSala}")
        print("\nPlacar:")
        for pid, player in self.jogadores.items():
            room_status = "na sala do tesouro" if pid in self.jogadoresSalaTesouro else "no mapa principal"
            print(f"Jogador {pid}: {player['score']} pts ({room_status})")
        print("\nCtrl+C para sair")
        print(Fore.CYAN + "=========================" + Style.RESET_ALL)
    
    def fim(self):
        self.ativo = False
        if self.jogadores:
            ganhador = max(self.jogadores.items(), key=lambda x: x[1]['score'])[0]
            ganhadorPlacar = self.jogadores[ganhador]['score']
            print(Fore.GREEN + f"\nJogo finalizado! Jogador {ganhador} venceu com {ganhadorPlacar} pontos!" + Style.RESET_ALL)
        return {
            'status': 'game_over',
            'winner': ganhador if self.jogadores else None,
            'score': ganhadorPlacar if self.jogadores else 0
        }
    
    def run(self):
        print(Fore.CYAN + f"Servidor iniciado em {self.host}:{self.port}" + Style.RESET_ALL)
        try:
            self.display()
            while self.ativo:
                client_socket, addr = self.server_socket.accept()
                jogadorId = random.randint(1000, 9999)
                self.addJogador(jogadorId)
                
                client_socket.send(str(jogadorId).encode())
                
                thread = threading.Thread(target=self.handle_client, 
                                       args=(client_socket, jogadorId))
                thread.daemon = True
                thread.start()
                
                self.display()
                
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nDesligando servidor..." + Style.RESET_ALL)
        finally:
            self.ativo = False
            self.server_socket.close()

if __name__ == "__main__":
    server = Jogo()
    server.run()
    