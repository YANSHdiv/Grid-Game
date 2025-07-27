import tkinter as tk
from tkinter import messagebox
import pygame
import random
import threading
import time

EDGE_ACTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
ALL_ACTIONS = EDGE_ACTIONS + [(-1, 1), (1, 1), (1, -1), (-1, -1)]
COLORS = {'human': (0, 0, 255), 'tiger': (255, 0, 0), 'food': (255, 255, 0), 'power': (0, 255, 0)}

def discretize(n):
    # Bucket distances into -2,-1,0,1,2 for manageable states
    if n < -2:
        return -2
    elif n > 2:
        return 2
    else:
        return n

class Agent:
    def __init__(self, x, y, color, agent_type):
        self.x = x
        self.y = y
        self.color = color
        self.agent_type = agent_type
        self.paused_until = 0  # For tigers pausing when eating humans
        self.retreating = False
        self.retreat_start_time = 0
        self.retreat_target = None

    def move(self, dx, dy, grid_w, grid_h):
        if self.agent_type == 'tiger' and time.time() < self.paused_until:
            # Tiger is busy eating human, can't move
            return
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < grid_h and 0 <= ny < grid_w:
            self.x = nx
            self.y = ny

    def pos(self):
        return (self.x, self.y)

class Game:
    def __init__(self, master):
        self.master = master
        self.master.title("Tiger Human Food Game")

        self.left_panel = tk.Frame(master, width=200, height=600)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(self.left_panel, text="Enter terrain size (WxH):").pack(pady=10)
        self.entry = tk.Entry(self.left_panel)
        self.entry.pack(pady=5)

        self.start_btn = tk.Button(self.left_panel, text="Start Game", command=self.start_game)
        self.start_btn.pack(pady=10)

        self.pause_btn = tk.Button(self.left_panel, text="Pause", command=self.pause_game, state=tk.DISABLED)
        self.pause_btn.pack(pady=5)

        self.reset_btn = tk.Button(self.left_panel, text="Reset", command=self.reset_game, state=tk.DISABLED)
        self.reset_btn.pack(pady=5)

        self.score_label = tk.Label(self.left_panel, text="Score: 0")
        self.score_label.pack(pady=10)

        self.lives_label = tk.Label(self.left_panel, text="Lives: 3")
        self.lives_label.pack(pady=5)

        self.embed_frame = tk.Frame(master, width=800, height=600)
        self.embed_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.running = False
        self.paused = False
        self.score = 0
        self.lives = 3
        self.power_active = False
        self.power_end_time = 0

        self.game_thread = None
        self.reset_requested = False

        # Q-learning parameters
        self.q_table_humans = {}
        self.q_table_tigers = {}
        self.alpha = 0.1
        self.gamma = 0.9
        self.epsilon = 0.1

    def get_q(self, q_table, state, action):
        if state not in q_table:
            q_table[state] = {a: 0.0 for a in ALL_ACTIONS}
        return q_table[state][action]

    def choose_action(self, q_table, state):
        if random.random() < self.epsilon:
            return random.choice(ALL_ACTIONS)
        else:
            q_values = q_table.get(state, {a: 0.0 for a in ALL_ACTIONS})
            max_q = max(q_values.values())
            best_actions = [a for a, q in q_values.items() if q == max_q]
            return random.choice(best_actions)

    def update_q(self, q_table, state, action, reward, next_state, next_action):
        current_q = self.get_q(q_table, state, action)
        next_q = self.get_q(q_table, next_state, next_action)
        new_q = current_q + self.alpha * (reward + self.gamma * next_q - current_q)
        q_table[state][action] = new_q

    def start_game(self):
        dims = self.entry.get().lower().replace(' ', '').split('x')
        if len(dims) != 2 or not dims[0].isdigit() or not dims[1].isdigit():
            messagebox.showerror("Invalid input", "Please enter dimensions like 800x600")
            return

        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()

        input_width = int(dims[0])
        input_height = int(dims[1])

        max_width = screen_width - 200
        max_height = screen_height - 200

        self.window_width = min(input_width, max_width)
        self.window_height = min(input_height, max_height)

        self.grid_w, self.grid_h = 20, 20
        self.cell_size = min(self.window_width // self.grid_w, self.window_height // self.grid_h)
        self.safe_zones = [(0, 0), (0, self.grid_w - 1), (self.grid_h - 1, 0), (self.grid_h - 1, self.grid_w - 1)]


        if self.running:
            return

        self.running = True
        self.paused = False
        self.score = 0
        self.lives = 3
        self.power_active = False
        self.power_end_time = 0
        self.reset_requested = False

        self.score_label.config(text="Score: 0")
        self.lives_label.config(text="Lives: 3")
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.reset_btn.config(state=tk.NORMAL)

        self.game_thread = threading.Thread(target=self.pygame_loop, daemon=True)
        self.game_thread.start()

    def pause_game(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.pause_btn.config(text="Resume" if self.paused else "Pause")

    def reset_game(self):
        if not self.running:
            return
        self.running = False
        self.paused = False
        self.pause_btn.config(text="Pause", state=tk.DISABLED)
        self.reset_btn.config(state=tk.DISABLED)
        self.reset_requested = True
        if self.game_thread and self.game_thread.is_alive():
            self.game_thread.join()
        self.start_game()

    def pygame_loop(self):
        pygame.init()
        window = pygame.display.set_mode((self.grid_w * self.cell_size, self.grid_h * self.cell_size))
        safe_zones = [(0, 0), (0, self.grid_w - 1), (self.grid_h - 1, 0), (self.grid_h - 1, self.grid_w - 1)]
        pygame.display.set_caption("Tiger Human Food")
        clock = pygame.time.Clock()

        # Create humans (2-5)
        num_humans = random.randint(2, 5)
        self.humans = []
        for _ in range(num_humans):
            while True:
                pos = (random.randint(0, self.grid_h - 1), random.randint(0, self.grid_w - 1))
                if all(h.pos() != pos for h in self.humans):
                    self.humans.append(Agent(pos[0], pos[1], COLORS['human'], 'human'))
                    break

        # Create tigers (2-5)
        num_tigers = random.randint(2, 5)
        self.tigers = []
        for _ in range(num_tigers):
            while True:
                pos = (random.randint(0, self.grid_h - 1), random.randint(0, self.grid_w - 1))
                if all(t.pos() != pos for t in self.tigers) and all(h.pos() != pos for h in self.humans):
                    self.tigers.append(Agent(pos[0], pos[1], COLORS['tiger'], 'tiger'))
                    break

        # Spawn food (5-20)
        food_count = random.randint(5, 20)
        food_list = self.spawn_food([h.pos() for h in self.humans], [t.pos() for t in self.tigers], count=food_count)

        power_up = None
        power_timer = pygame.time.get_ticks() + random.randint(5000, 10000)

        tiger_interval = 200
        human_interval = 500
        last_tiger_move = last_human_move = pygame.time.get_ticks()

        font = pygame.font.SysFont(None, 60)

        # Initialize states and actions for humans and tigers
        human_states = []
        human_actions = []
        for h in self.humans:
            nearest_food = self.closest(h.pos(), food_list)
            nearest_tiger = self.closest(h.pos(), [t.pos() for t in self.tigers])
            state = self.make_human_state(h.pos(), nearest_food, nearest_tiger)
            action = self.choose_action(self.q_table_humans, state)
            human_states.append(state)
            human_actions.append(action)

        tiger_states = []
        tiger_actions = []
        for t in self.tigers:
            nearest_human = self.closest(t.pos(), [h.pos() for h in self.humans])
            nearest_food = self.closest(t.pos(), food_list)
            state = self.make_tiger_state(t.pos(), nearest_human, nearest_food)
            action = self.choose_action(self.q_table_tigers, state)
            tiger_states.append(state)
            tiger_actions.append(action)

        def human_reward(h, old_pos, food_list, tigers):
            reward = -0.1  # step penalty to encourage fast food collection
            if h.pos() in food_list:
                reward += 10
            dist_to_food_before = self.manhattan(old_pos, self.closest(old_pos, food_list))
            dist_to_food_after = self.manhattan(h.pos(), self.closest(h.pos(), food_list))
            if dist_to_food_after < dist_to_food_before:
                reward += 1  # reward for moving closer to food

            # penalty if near tiger
            nearest_tiger_pos = self.closest(h.pos(), [t.pos() for t in tigers])
            dist_to_tiger = self.manhattan(h.pos(), nearest_tiger_pos)
            if dist_to_tiger <= 2:
                reward -= 5

            return reward

        def tiger_reward(t, old_pos, humans, food_list, power_active):
            reward = -0.05  # step penalty

            # Reward for being near food (guarding)
            nearest_food_pos = self.closest(t.pos(), food_list)
            dist_to_food = self.manhattan(t.pos(), nearest_food_pos)
            if dist_to_food <= 2:
                reward += 2

            # Reward for moving closer to human (attack)
            nearest_human_pos = self.closest(t.pos(), [h.pos() for h in humans])
            dist_to_human_before = self.manhattan(old_pos, nearest_human_pos)
            dist_to_human_after = self.manhattan(t.pos(), nearest_human_pos)
            if dist_to_human_after < dist_to_human_before:
                reward += 2

            # Extra reward if tiger is powered (power active)
            if power_active:
                reward += 1

            return reward

        while self.running:
            if self.reset_requested:
                break
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    return

            if self.paused:
                time.sleep(0.1)
                continue

            now = pygame.time.get_ticks()

            if power_up is None and now >= power_timer:
                power_up = self.spawn_power([h.pos() for h in self.humans], [t.pos() for t in self.tigers], food_list)

            if now - last_tiger_move > tiger_interval:
                # Tigers move
                for i, tiger in enumerate(self.tigers):
                    # Check if tiger is paused eating human
                    if time.time() < tiger.paused_until:
                        continue  # Skip movement

                    state = tiger_states[i]
                    action = tiger_actions[i]
                    old_pos = tiger.pos()

                    # Determine mode: attack or guard food
                    nearest_human = self.closest(tiger.pos(), [h.pos() for h in self.humans])
                    dist_human = self.manhattan(tiger.pos(), nearest_human)
                    nearest_food = self.closest(tiger.pos(), food_list)

                    if dist_human <= 3:
                        # Attack mode: move towards human
                        target = nearest_human
                    else:
                        # Guard mode: move towards nearest food
                        target = nearest_food

                    dx = target[0] - tiger.x
                    dy = target[1] - tiger.y
                    move = self.optimal_move(dx, dy)
                    tiger.move(*move, self.grid_w, self.grid_h)

                    # Check if caught a human
                    caught_human_idx = None
                    for hi, human in enumerate(self.humans):
                        if tiger.pos() == human.pos():
                            caught_human_idx = hi
                            break

                    reward = tiger_reward(tiger, old_pos, self.humans, food_list, self.power_active)

                    next_state = self.make_tiger_state(tiger.pos(), nearest_human, nearest_food)
                    next_action = self.choose_action(self.q_table_tigers, next_state)

                    self.update_q(self.q_table_tigers, state, action, reward, next_state, next_action)

                    tiger_states[i] = next_state
                    tiger_actions[i] = next_action

                    if caught_human_idx is not None:
                        # Human caught: tiger pauses for 4 seconds
                        tiger.paused_until = time.time() + 4
                        # Remove human and decrease lives
                        del self.humans[caught_human_idx]
                        self.lives -= 1
                        self.lives_label.config(text=f"Lives: {self.lives}")
                        if self.lives <= 0:
                            self.game_over(window, font)
                            return
                        break

                last_tiger_move = now

            if now - last_human_move > human_interval:
                # Humans move
                for i, human in enumerate(self.humans):
                    safe_corner = self.closest(human.pos(), self.safe_zones)
                    if human.retreating:
                        # Check if reached safe cell
                        if human.pos() == human.retreat_target:
                            # Wait 1 sec in safe zone
                            if pygame.time.get_ticks() - human.retreat_start_time >= 2000:
                                human.retreating = False
                            else:
                                continue
                        else:
                            # Move step-by-step toward retreat target while avoiding tiger
                            dx = human.retreat_target[0] - human.x
                            dy = human.retreat_target[1] - human.y

                            safe_moves = []
                            for move in ALL_ACTIONS:
                                nx, ny = human.x + move[0], human.y + move[1]
                                if 0 <= nx < self.grid_h and 0 <= ny < self.grid_w:
                                    dist_to_tiger = min([abs(nx - t.x) + abs(ny - t.y) for t in self.tigers])
                                    if dist_to_tiger > 1:
                                        safe_moves.append(move)

                            if safe_moves:
                                move = min(safe_moves, key=lambda m: abs((human.x + m[0]) - human.retreat_target[0]) + abs((human.y + m[1]) - human.retreat_target[1]))
                            else:
                                move = self.optimal_move(dx, dy)

                            human.move(*move, self.grid_w, self.grid_h)
                            continue  # skip Q-learning and food logic

                    # Normal behavior (not retreating)
                    state = human_states[i]
                    action = human_actions[i]
                    old_pos = human.pos()

                    nearest_food = self.closest(human.pos(), food_list)
                    nearest_tiger = self.closest(human.pos(), [t.pos() for t in self.tigers])

                    dx = nearest_food[0] - human.x
                    dy = nearest_food[1] - human.y

                    # Avoid tiger if close
                    safe_moves = []
                    for move in ALL_ACTIONS:
                        nx, ny = human.x + move[0], human.y + move[1]
                        if 0 <= nx < self.grid_h and 0 <= ny < self.grid_w:
                            dist_to_tiger = min([abs(nx - t.x) + abs(ny - t.y) for t in self.tigers])
                            if dist_to_tiger > 1:
                                safe_moves.append(move)

                    if safe_moves:
                        move = min(safe_moves, key=lambda m: abs((human.x + m[0]) - nearest_food[0]) + abs((human.y + m[1]) - nearest_food[1]))
                    else:
                        move = self.optimal_move(dx, dy)

                    human.move(*move, self.grid_w, self.grid_h)

                    # If food collected
                    if human.pos() in food_list:
                        food_list.remove(human.pos())
                        self.score += 10
                        self.score_label.config(text=f"Score: {self.score}")

                        # Set up retreat
                        safe_corner = self.closest(human.pos(), safe_zones)
                        human.retreat_target = safe_corner
                        human.retreating = True
                        human.retreat_start_time = pygame.time.get_ticks()
                        continue  # skip Q-learning during retreat

                    # Q-learning update
                    reward = human_reward(human, old_pos, food_list, self.tigers)
                    next_state = self.make_human_state(human.pos(), nearest_food, nearest_tiger)
                    next_action = self.choose_action(self.q_table_humans, next_state)
                    self.update_q(self.q_table_humans, state, action, reward, next_state, next_action)

                    human_states[i] = next_state
                    human_actions[i] = next_action



            # Check if power-up collected
            if power_up is not None:
                for tiger in self.tigers:
                    if tiger.pos() == power_up:
                        self.power_active = True
                        self.power_end_time = pygame.time.get_ticks() + 8000
                        power_up = None
                        break

            if self.power_active and pygame.time.get_ticks() > self.power_end_time:
                self.power_active = False

            window.fill((255, 255, 255))  # white background

            # Draw safe zones as bold green squares
            for sx, sy in safe_zones:
                rect = pygame.Rect(sy * self.cell_size, sx * self.cell_size, self.cell_size, self.cell_size)
                pygame.draw.rect(window, COLORS['power'], rect, 4)  # Bold green border

            # Draw grid lines
            for i in range(self.grid_w + 1):
                pygame.draw.line(window, (220, 220, 220), (i * self.cell_size, 0), (i * self.cell_size, self.grid_h * self.cell_size))
            for j in range(self.grid_h + 1):
                pygame.draw.line(window, (220, 220, 220), (0, j * self.cell_size), (self.grid_w * self.cell_size, j * self.cell_size))

            # Draw food
            for fx, fy in food_list:
                rect = pygame.Rect(fy * self.cell_size + self.cell_size // 4, fx * self.cell_size + self.cell_size // 4,
                                   self.cell_size // 2, self.cell_size // 2)
                pygame.draw.ellipse(window, COLORS['food'], rect)

            # Draw power-up
            if power_up is not None:
                px, py = power_up
                rect = pygame.Rect(py * self.cell_size + self.cell_size // 4, px * self.cell_size + self.cell_size // 4,
                                   self.cell_size // 2, self.cell_size // 2)
                pygame.draw.rect(window, COLORS['power'], rect)

            # Draw tigers as circles
            for tiger in self.tigers:
                cx = tiger.y * self.cell_size + self.cell_size // 2
                cy = tiger.x * self.cell_size + self.cell_size // 2
                pygame.draw.circle(window, tiger.color, (cx, cy), self.cell_size // 2 - 2)

            # Draw humans as stickmen (simple lines)
            for human in self.humans:
                cx = human.y * self.cell_size + self.cell_size // 2
                cy = human.x * self.cell_size + self.cell_size // 2
                head_radius = self.cell_size // 6
                # head
                pygame.draw.circle(window, human.color, (cx, cy - head_radius), head_radius)
                # body
                pygame.draw.line(window, human.color, (cx, cy - head_radius // 2), (cx, cy + head_radius), 2)
                # arms
                pygame.draw.line(window, human.color, (cx - head_radius, cy), (cx + head_radius, cy), 2)
                # legs
                pygame.draw.line(window, human.color, (cx, cy + head_radius), (cx - head_radius, cy + 2 * head_radius), 2)
                pygame.draw.line(window, human.color, (cx, cy + head_radius), (cx + head_radius, cy + 2 * head_radius), 2)

            pygame.display.flip()
            clock.tick(5)

            # Win condition: all food eaten
            if not food_list:
                self.game_win(window, font)
                break

        pygame.quit()
        self.running = False
        self.pause_btn.config(state=tk.DISABLED)
        self.reset_btn.config(state=tk.DISABLED)

    def spawn_food(self, human_positions, tiger_positions, count):
        food_positions = set()
        attempts = 0
        while len(food_positions) < count and attempts < 1000:
            pos = (random.randint(0, self.grid_h - 1), random.randint(0, self.grid_w - 1))
            if pos not in human_positions and pos not in tiger_positions:
                food_positions.add(pos)
            attempts += 1
        return list(food_positions)

    def spawn_power(self, human_positions, tiger_positions, food_positions):
        while True:
            pos = (random.randint(0, self.grid_h - 1), random.randint(0, self.grid_w - 1))
            if pos not in human_positions and pos not in tiger_positions and pos not in food_positions:
                return pos

    def closest(self, pos, positions):
        if not positions:
            return pos
        return min(positions, key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))

    def manhattan(self, p1, p2):
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    def make_human_state(self, human_pos, food_pos, tiger_pos):
        dx_food = discretize(food_pos[0] - human_pos[0])
        dy_food = discretize(food_pos[1] - human_pos[1])
        dx_tiger = discretize(tiger_pos[0] - human_pos[0])
        dy_tiger = discretize(tiger_pos[1] - human_pos[1])
        return (dx_food, dy_food, dx_tiger, dy_tiger)

    def make_tiger_state(self, tiger_pos, human_pos, food_pos):
        dx_human = discretize(human_pos[0] - tiger_pos[0])
        dy_human = discretize(human_pos[1] - tiger_pos[1])
        dx_food = discretize(food_pos[0] - tiger_pos[0])
        dy_food = discretize(food_pos[1] - tiger_pos[1])
        return (dx_human, dy_human, dx_food, dy_food)

    def optimal_move(self, dx, dy):
        # Move 1 step toward dx, dy (Manhattan)
        if dx > 0:
            return (1, 0)
        elif dx < 0:
            return (-1, 0)
        elif dy > 0:
            return (0, 1)
        elif dy < 0:
            return (0, -1)
        else:
            return (0, 0)

    def game_over(self, window, font):
        text = font.render("GAME OVER", True, (255, 0, 0))
        window.fill((255, 255, 255))
        window.blit(text, (self.grid_w * self.cell_size // 4, self.grid_h * self.cell_size // 3))
        pygame.display.flip()
        time.sleep(5)

    def game_win(self, window, font):
        text = font.render("YOU WIN!", True, (0, 255, 0))
        window.fill((255, 255, 255))
        window.blit(text, (self.grid_w * self.cell_size // 4, self.grid_h * self.cell_size // 3))
        pygame.display.flip()
        time.sleep(5)



if __name__ == "__main__":
    root = tk.Tk()
    game = Game(root)
    root.mainloop()
