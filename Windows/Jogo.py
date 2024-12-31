import socket
import threading
import json
import time
import random
from threading import Lock
import os
from colorama import init, Fore, Style

class GameServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.map_size = 8
        self.treasure_room_size = 4  # Tamanho da sala do tesouro
        self.num_treasures = 15
        self.main_map = [["." for _ in range(self.map_size)] for _ in range(self.map_size)]
        self.treasure_room = None
        self.map_lock = Lock()
        self.player_lock = Lock()
        self.game_active = True
        
        # Game state
        self.players = {}
        self.players_in_treasure_room = set()  # Conjunto para rastrear jogadores na sala
        self.collected_treasures = 0
        self.total_treasures = self.num_treasures + 5
        
        # Treasure room
        self.treasure_room_x = random.randint(0, self.map_size - 1)
        self.treasure_room_y = random.randint(0, self.map_size - 1)
        self.treasures_in_room = 5
        self.room_lock = Lock()
        
        init(autoreset=True)
        self._initialize_maps()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
    
    def _initialize_maps(self):
        with self.map_lock:
            # Inicializa mapa principal
            for _ in range(self.num_treasures):
                while True:
                    x, y = random.randint(0, self.map_size - 1), random.randint(0, self.map_size - 1)
                    if self.main_map[x][y] == "." and (x, y) != (self.treasure_room_x, self.treasure_room_y):
                        self.main_map[x][y] = str(random.randint(1, 9))
                        break
            
            # Marca a entrada da sala do tesouro
            self.main_map[self.treasure_room_x][self.treasure_room_y] = "X"
            
            # Inicializa a sala do tesouro
            self._initialize_treasure_room()
    
    def _initialize_treasure_room(self):
        self.treasure_room = [["." for _ in range(self.treasure_room_size)] 
                            for _ in range(self.treasure_room_size)]
        
        # Coloca tesouros na sala
        treasures_placed = 0
        while treasures_placed < self.treasures_in_room:
            x = random.randint(0, self.treasure_room_size - 1)
            y = random.randint(0, self.treasure_room_size - 1)
            if self.treasure_room[x][y] == ".":
                self.treasure_room[x][y] = str(random.randint(5, 9))  # Tesouros maiores na sala especial
                treasures_placed += 1
    
    def get_game_state(self, player_id=None):
        with self.player_lock:
            if player_id in self.players_in_treasure_room:
                return {
                    'map': self.treasure_room,
                    'players': {pid: data for pid, data in self.players.items() 
                              if pid in self.players_in_treasure_room},
                    'treasures_left': self.total_treasures - self.collected_treasures,
                    'room_treasures': self.treasures_in_room,
                    'in_treasure_room': True,
                    'map_size': self.treasure_room_size
                }
            else:
                return {
                    'map': self.main_map,
                    'players': {pid: data for pid, data in self.players.items() 
                              if pid not in self.players_in_treasure_room},
                    'treasures_left': self.total_treasures - self.collected_treasures,
                    'room_treasures': self.treasures_in_room,
                    'in_treasure_room': False,
                    'map_size': self.map_size
                }
    
    def handle_client(self, client_socket, player_id):
        try:
            while self.game_active:
                try:
                    data = client_socket.recv(1024).decode()
                    if not data:
                        break
                    
                    command = json.loads(data)
                    response = self.process_command(player_id, command)
                    client_socket.send(json.dumps(response).encode())
                    
                    self.display_server_status()
                    
                    if self.collected_treasures >= self.total_treasures:
                        self.end_game()
                        
                except (json.JSONDecodeError, socket.error):
                    break
        finally:
            self.remove_player(player_id)
            client_socket.close()
            self.display_server_status()
    
    def process_command(self, player_id, command):
        cmd_type = command.get('type')
        if cmd_type == 'move':
            return self.move_player(player_id, command['direction'])
        elif cmd_type == 'enter_room':
            return self.enter_treasure_room(player_id)
        elif cmd_type == 'leave_room':
            return self.leave_treasure_room(player_id)
        elif cmd_type == 'get_state':
            return self.get_game_state(player_id)
        return {'status': 'error', 'message': 'Comando inválido'}
    
    def move_player(self, player_id, direction):
        with self.map_lock:
            if player_id not in self.players:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            in_treasure_room = player_id in self.players_in_treasure_room
            current_map = self.treasure_room if in_treasure_room else self.main_map
            map_size = self.treasure_room_size if in_treasure_room else self.map_size
            
            x, y = self.players[player_id]['position']
            new_x, new_y = x, y
            
            if direction == 'up' and x > 0:
                new_x = x - 1
            elif direction == 'down' and x < map_size - 1:
                new_x = x + 1
            elif direction == 'left' and y > 0:
                new_y = y - 1
            elif direction == 'right' and y < map_size - 1:
                new_y = y + 1
            
            if (new_x, new_y) != (x, y):
                self.players[player_id]['position'] = (new_x, new_y)
                
                if current_map[new_x][new_y].isdigit():
                    value = int(current_map[new_x][new_y])
                    self.players[player_id]['score'] += value
                    self.collected_treasures += 1
                    current_map[new_x][new_y] = "."
                    if in_treasure_room:
                        self.treasures_in_room -= 1
            
            return self.get_game_state(player_id)
    
    def enter_treasure_room(self, player_id):
        with self.room_lock:
            player = self.players.get(player_id)
            if not player:
                return {'status': 'error', 'message': 'Jogador não encontrado'}
            
            x, y = player['position']
            if (x, y) != (self.treasure_room_x, self.treasure_room_y):
                return {'status': 'error', 'message': 'Não está na entrada'}
            
            # Move o jogador para a sala do tesouro
            self.players_in_treasure_room.add(player_id)
            self.players[player_id]['position'] = (0, 0)  # Posição inicial na sala
            
            return {
                'status': 'success',
                'message': 'Bem-vindo à sala do tesouro! Pressione ESC para sair',
                'state': self.get_game_state(player_id)
            }
    
    def leave_treasure_room(self, player_id):
        with self.room_lock:
            if player_id in self.players_in_treasure_room:
                self.players_in_treasure_room.remove(player_id)
                self.players[player_id]['position'] = (self.treasure_room_x, self.treasure_room_y)
                
                return {
                    'status': 'success',
                    'message': 'Voltou ao mapa principal',
                    'state': self.get_game_state(player_id)
                }
            return {'status': 'error', 'message': 'Jogador não está na sala'}
    
    def add_player(self, player_id):
        with self.player_lock:
            start_x, start_y = random.randint(0, self.map_size - 1), random.randint(0, self.map_size - 1)
            while self.main_map[start_x][start_y] != ".":
                start_x, start_y = random.randint(0, self.map_size - 1), random.randint(0, self.map_size - 1)
            
            self.players[player_id] = {
                'position': (start_x, start_y),
                'score': 0
            }
    
    def remove_player(self, player_id):
        with self.player_lock:
            if player_id in self.players:
                del self.players[player_id]
            if player_id in self.players_in_treasure_room:
                self.players_in_treasure_room.remove(player_id)
    
    def display_server_status(self):
        os.system('cls')
        print(Fore.CYAN + "==== Status do Servidor ====" + Style.RESET_ALL)
        print(f"Servidor rodando em {self.host}:{self.port}")
        print(f"Jogadores conectados: {len(self.players)}")
        print(f"Jogadores na sala do tesouro: {len(self.players_in_treasure_room)}")
        print(f"Tesouros coletados: {self.collected_treasures}/{self.total_treasures}")
        print(f"Tesouros na sala especial: {self.treasures_in_room}")
        print("\nPlacar:")
        for pid, player in self.players.items():
            room_status = "na sala do tesouro" if pid in self.players_in_treasure_room else "no mapa principal"
            print(f"Jogador {pid}: {player['score']} pts ({room_status})")
        print("\nCtrl+C para sair")
        print(Fore.CYAN + "=========================" + Style.RESET_ALL)
    
    def end_game(self):
        self.game_active = False
        if self.players:
            winner_id = max(self.players.items(), key=lambda x: x[1]['score'])[0]
            winner_score = self.players[winner_id]['score']
            print(Fore.GREEN + f"\nJogo finalizado! Jogador {winner_id} venceu com {winner_score} pontos!" + Style.RESET_ALL)
        return {
            'status': 'game_over',
            'winner': winner_id if self.players else None,
            'score': winner_score if self.players else 0
        }
    
    def run(self):
        print(Fore.CYAN + f"Servidor iniciado em {self.host}:{self.port}" + Style.RESET_ALL)
        try:
            self.display_server_status()
            while self.game_active:
                client_socket, addr = self.server_socket.accept()
                player_id = random.randint(1000, 9999)
                self.add_player(player_id)
                
                client_socket.send(str(player_id).encode())
                
                thread = threading.Thread(target=self.handle_client, 
                                       args=(client_socket, player_id))
                thread.daemon = True
                thread.start()
                
                self.display_server_status()
                
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\nDesligando servidor..." + Style.RESET_ALL)
        finally:
            self.game_active = False
            self.server_socket.close()

if __name__ == "__main__":
    server = GameServer()
    server.run()
    