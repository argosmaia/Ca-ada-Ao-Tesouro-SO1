import socket
import threading
import json
import time
import random
from threading import Lock

class GameServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.map_size = 10
        self.num_treasures = 20
        self.main_map = [["." for _ in range(self.map_size)] for _ in range(self.map_size)]
        self.map_lock = Lock()
        self.player_lock = Lock()
        self.game_active = True
        
        # Game state
        self.players = {}
        self.collected_treasures = 0
        self.total_treasures = self.num_treasures + 5  # Regular + room treasures
        
        # Treasure room
        self.treasure_room_x = random.randint(0, self.map_size - 1)
        self.treasure_room_y = random.randint(0, self.map_size - 1)
        self.treasures_in_room = 5
        self.room_lock = Lock()
        
        # Initialize game
        self._initialize_map()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
    
    def _initialize_map(self):
        with self.map_lock:
            # Place regular treasures
            for _ in range(self.num_treasures):
                while True:
                    x, y = random.randint(0, self.map_size - 1), random.randint(0, self.map_size - 1)
                    if self.main_map[x][y] == "." and (x, y) != (self.treasure_room_x, self.treasure_room_y):
                        self.main_map[x][y] = str(random.randint(1, 9))
                        break
            
            # Mark treasure room
            self.main_map[self.treasure_room_x][self.treasure_room_y] = "X"
    
    def get_game_state(self):
        with self.player_lock:
            return {
                'map': self.main_map,
                'players': self.players,
                'treasures_left': self.total_treasures - self.collected_treasures,
                'room_treasures': self.treasures_in_room
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
                    
                    # Check if game should end
                    if self.collected_treasures >= self.total_treasures:
                        self.end_game()
                        
                except (json.JSONDecodeError, socket.error):
                    break
        finally:
            self.remove_player(player_id)
            client_socket.close()
    
    def process_command(self, player_id, command):
        cmd_type = command.get('type')
        if cmd_type == 'move':
            return self.move_player(player_id, command['direction'])
        elif cmd_type == 'enter_room':
            return self.handle_treasure_room(player_id)
        elif cmd_type == 'get_state':
            return self.get_game_state()
        return {'status': 'error', 'message': 'Invalid command'}
    
    def move_player(self, player_id, direction):
        with self.map_lock:
            if player_id not in self.players:
                return {'status': 'error', 'message': 'Player not found'}
            
            x, y = self.players[player_id]['position']
            new_position = {
                'up': (max(0, x - 1), y),
                'down': (min(self.map_size - 1, x + 1), y),
                'left': (x, max(0, y - 1)),
                'right': (x, min(self.map_size - 1, y + 1))
            }.get(direction, (x, y))
            
            self.players[player_id]['position'] = new_position
            new_x, new_y = new_position
            
            if self.main_map[new_x][new_y].isdigit():
                self.players[player_id]['score'] += int(self.main_map[new_x][new_y])
                self.collected_treasures += 1
                self.main_map[new_x][new_y] = "."
            
            return self.get_game_state()
    
    def handle_treasure_room(self, player_id):
        with self.room_lock:
            player = self.players.get(player_id)
            if not player:
                return {'status': 'error', 'message': 'Player not found'}
            
            x, y = player['position']
            if (x, y) != (self.treasure_room_x, self.treasure_room_y):
                return {'status': 'error', 'message': 'Not in treasure room'}
            
            if self.treasures_in_room <= 0:
                return {'status': 'error', 'message': 'Room is empty'}
            
            self.treasures_in_room -= 1
            self.collected_treasures += 1
            self.players[player_id]['score'] += 10
            
            return {
                'status': 'success',
                'message': f'Found treasure! Room treasures left: {self.treasures_in_room}',
                'state': self.get_game_state()
            }
    
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
    
    def end_game(self):
        self.game_active = False
        winner_id = max(self.players.items(), key=lambda x: x[1]['score'])[0]
        winner_score = self.players[winner_id]['score']
        return {
            'status': 'game_over',
            'winner': winner_id,
            'score': winner_score
        }
    
    def run(self):
        print(f"Server starting on {self.host}:{self.port}")
        try:
            while self.game_active:
                client_socket, addr = self.server_socket.accept()
                player_id = random.randint(1000, 9999)
                self.add_player(player_id)
                
                client_socket.send(str(player_id).encode())
                
                thread = threading.Thread(target=self.handle_client, 
                                       args=(client_socket, player_id))
                thread.start()
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = GameServer()
    server.run()