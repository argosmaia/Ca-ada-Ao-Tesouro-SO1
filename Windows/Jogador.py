import socket
import json
import msvcrt
import threading
import time
import signal
from colorama import init, Fore, Style
import sys

class GameClient:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_state = None
        self.running = True
        self.last_render = ""
        init(autoreset=True)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        pass

    def clear_screen(self):
        sys.stdout.write("\033[H")
        sys.stdout.flush()
        
    def connect(self):
        try:
            self.socket.connect((self.host, self.port))
            self.player_id = int(self.socket.recv(1024).decode())
            return True
        except socket.error as e:
            print(f"Erro de conexão: {e}")
            return False
    
    def send_command(self, command):
        try:
            self.socket.send(json.dumps(command).encode())
            response = self.socket.recv(1024).decode()
            return json.loads(response)
        except (socket.error, json.JSONDecodeError) as e:
            print(f"Erro de comunicação: {e}")
            self.running = False
            return None
    
    def update_game_state(self):
        response = self.send_command({'type': 'get_state'})
        if response:
            self.game_state = response

    def get_cell_content(self, x, y):
        # Primeiro verifica se há um jogador na célula
        if self.game_state and 'players' in self.game_state:
            for pid, pdata in self.game_state['players'].items():
                if pdata['position'] == (x, y):
                    if str(pid) == str(self.player_id):
                        return ('P', Fore.GREEN)
                    return ('J', Fore.RED)
        
        # Se não há jogador, retorna o conteúdo do mapa
        cell = self.game_state['map'][x][y]
        if cell.isdigit():
            return (cell, Fore.YELLOW)
        elif cell == 'X':
            return (cell, Fore.CYAN)
        return (cell, Style.RESET_ALL)

    def generate_screen_buffer(self):
        if not self.game_state:
            return ""

        buffer = []
        buffer.append(Fore.YELLOW + "=== CAÇA AO TESOURO ===" + Style.RESET_ALL)
        buffer.append("")

        # Mapa com índices
        buffer.append("   " + " ".join([str(i) for i in range(len(self.game_state['map'][0]))]))
        
        for i, row in enumerate(self.game_state['map']):
            line = f"{i:2} "
            for j, _ in enumerate(row):
                content, color = self.get_cell_content(i, j)
                line += color + content + " " + Style.RESET_ALL
            buffer.append(line)
        
        player = self.game_state['players'].get(str(self.player_id))
        if player:
            buffer.append("")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)
            buffer.append(f"Pontuação: {Fore.GREEN}{player['score']}{Style.RESET_ALL} | "
                        f"Tesouros restantes: {Fore.YELLOW}{self.game_state['treasures_left']}{Style.RESET_ALL}")
            
            current_pos = player['position']
            for i, row in enumerate(self.game_state['map']):
                if 'X' in row and current_pos == (i, row.index('X')):
                    buffer.append(Fore.YELLOW + 
                                f"Sala do tesouro! Pressione E para entrar ({self.game_state['room_treasures']} restantes)" + 
                                Style.RESET_ALL)
            
            buffer.append("\nControles: WASD/Setas para mover, E para entrar na sala, Q para sair")
            buffer.append(Fore.CYAN + "="*40 + Style.RESET_ALL)

        return "\n".join(buffer)
    
    def draw_screen(self):
        if not self.game_state:
            return
        
        new_render = self.generate_screen_buffer()
        
        if new_render != self.last_render:
            self.clear_screen()
            print(new_render)
            self.last_render = new_render
    
    def is_valid_key(self, key):
        valid_keys = [
            b'w', b'a', b's', b'd',
            b'W', b'A', b'S', b'D',
            b'e', b'E',  # Trocado de 'k'/'K' para 'e'/'E'
            b'q', b'Q',
            b'H', b'P', b'K', b'M',
            b'\xe0'
        ]
        return key in valid_keys
    
    def handle_input(self):
        key_mapping = {
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
        
        while self.running:
            try:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    
                    if not self.is_valid_key(key):
                        continue
                    
                    if key in key_mapping:
                        response = self.send_command({
                            'type': 'move',
                            'direction': key_mapping[key]
                        })
                        if response:
                            self.game_state = response
                    
                    elif key == b'\xe0':
                        key = msvcrt.getch()
                        if key in key_mapping:
                            response = self.send_command({
                                'type': 'move',
                                'direction': key_mapping[key]
                            })
                            if response:
                                self.game_state = response
                    
                    elif key in [b'e', b'E']:  # Trocado de 'k'/'K' para 'e'/'E'
                        response = self.send_command({'type': 'enter_room'})
                        if response and response.get('status') == 'success':
                            self.game_state = response['state']
                            time.sleep(0.1)

                    elif key in [b'q', b'Q']:
                        self.running = False
                        break
            
            except Exception:
                continue
    
    def setup_terminal(self):
        print("\033[2J", end='')
        print("\033[?25l", end='')
        print("\033[H", end='')
        sys.stdout.flush()

    def restore_terminal(self):
        print("\033[?25h", end='')
        sys.stdout.flush()
    
    def run(self):
        if self.connect():
            try:
                self.setup_terminal()
                
                input_thread = threading.Thread(target=self.handle_input)
                input_thread.daemon = True
                input_thread.start()

                while self.running:
                    try:
                        self.update_game_state()
                        self.draw_screen()
                        time.sleep(0.05)
                    except Exception:
                        continue
                
            finally:
                self.restore_terminal()
                self.socket.close()

if __name__ == "__main__":
    while True:
        try:
            client = GameClient()
            client.run()
            if not client.running:
                break
        except Exception:
            continue