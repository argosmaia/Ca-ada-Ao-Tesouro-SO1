import socket
import json
import curses
import sys
import threading
import time

class GameClient:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_state = None
        self.running = True
    
    def connect(self):
        try:
            self.socket.connect((self.host, self.port))
            self.player_id = int(self.socket.recv(1024).decode())
            return True
        except socket.error as e:
            print(f"Connection failed: {e}")
            return False
    
    def send_command(self, command):
        try:
            self.socket.send(json.dumps(command).encode())
            response = self.socket.recv(1024).decode()
            return json.loads(response)
        except (socket.error, json.JSONDecodeError) as e:
            print(f"Error communicating with server: {e}")
            self.running = False
            return None
    
    def update_game_state(self):
        response = self.send_command({'type': 'get_state'})
        if response:
            self.game_state = response
    
    def draw_screen(self, stdscr):
        if not self.game_state:
            return
        
        stdscr.clear()
        
        # Draw map
        for i, row in enumerate(self.game_state['map']):
            for j, cell in enumerate(row):
                # Draw players
                is_player = False
                for pid, pdata in self.game_state['players'].items():
                    if pdata['position'] == (i, j):
                        if int(pid) == self.player_id:
                            stdscr.addstr(i, j, "P", curses.A_BOLD)
                        else:
                            stdscr.addstr(i, j, "O")
                        is_player = True
                        break
                
                if not is_player:
                    stdscr.addstr(i, j, cell)
        
        # Draw status
        status_y = len(self.game_state['map']) + 2
        player = self.game_state['players'].get(str(self.player_id))
        if player:
            stdscr.addstr(status_y, 0, f"Score: {player['score']} | ")
            stdscr.addstr(f"Treasures left: {self.game_state['treasures_left']}")
            
            # Show treasure room info if on X
            if player['position'] == (self.game_state['map'].index('X' in row) 
                                    for row in self.game_state['map']):
                stdscr.addstr(status_y + 1, 0, 
                            f"Press 'k' to collect treasure ({self.game_state['room_treasures']} left)")
        
        stdscr.refresh()
    
    def handle_input(self, stdscr):
        key_mapping = {
            'KEY_UP': 'up',
            'KEY_DOWN': 'down',
            'KEY_LEFT': 'left',
            'KEY_RIGHT': 'right',
            'w': 'up',
            's': 'down',
            'a': 'left',
            'd': 'right'
        }
        
        while self.running:
            try:
                key = stdscr.getkey()
                
                if key in key_mapping:
                    response = self.send_command({
                        'type': 'move',
                        'direction': key_mapping[key]
                    })
                    if response:
                        self.game_state = response
                
                elif key == 'k':
                    response = self.send_command({'type': 'enter_room'})
                    if response and response.get('status') == 'success':
                        self.game_state = response['state']
                        stdscr.addstr(len(self.game_state['map']) + 3, 0, 
                                    response['message'])
                
                elif key == 'q':
                    self.running = False
                    break
                
            except curses.error:
                continue
    
    def run(self):
        def curses_main(stdscr):
            curses.curs_set(0)
            stdscr.nodelay(1)
            stdscr.timeout(100)
            
            # Start input handling thread
            input_thread = threading.Thread(target=self.handle_input, args=(stdscr,))
            input_thread.start()
            
            # Main game loop
            while self.running:
                self.update_game_state()
                self.draw_screen(stdscr)
                time.sleep(0.1)
            
            input_thread.join()
        
        if self.connect():
            try:
                curses.wrapper(curses_main)
            finally:
                self.socket.close()

if __name__ == "__main__":
    client = GameClient()
    client.run()