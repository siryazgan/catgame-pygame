import asyncio
import pygame
import random
import os, sys

def resource(relative_path):
    base_path = getattr(
        sys,
        '_MEIPASS',
        os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path).replace("\\", "/")

def load_image(img_path):
    img = pygame.image.load(img_path).convert_alpha()
    return img

def load_sprite_sheet(img_path, size, scale=1):
    img = load_image(img_path)
    sheet = []
    for x in range(img.get_width() // size[0]):
        sub = img.subsurface((x * size[0], 0, size[0], size[1]))
        sheet.append(pygame.transform.scale(sub, (int(size[0] * scale), int(size[1] * scale))))
    return sheet

class Animation:
    def __init__(self, images, loop=True, img_dur=5):
        self.frame = 0.0
        self.images = images
        self.loop = loop
        self.img_dur = img_dur
        self.done = False

    def copy(self):
        return Animation(self.images, self.loop, self.img_dur)

    def update_frame(self, speed_multiplier):
        if self.loop:
            self.frame = (self.frame + speed_multiplier) % (self.img_dur * len(self.images))
        else:
            self.frame = min(self.frame + speed_multiplier, self.img_dur * len(self.images) - 1)
            if self.frame >= self.img_dur * len(self.images) - 1:
                self.done = True

    def image(self):
        return self.images[int(self.frame / self.img_dur)]

class Main:
    def __init__(self):
        pygame.mixer.init()
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("MEOWWWW")
        self.screen = pygame.display.set_mode((800,600))
        pygame.display.set_icon(load_image(resource('assets/icon_png.png')))
        
        self.clock = pygame.time.Clock()

        self.assets = {
            'cat_walk': Animation(load_sprite_sheet(resource('assets/Walk.png'), (48, 48), 2.5), img_dur=5),
            'black_cat': Animation(load_sprite_sheet(resource('assets/black_cat.png'), (48, 48), 2.5), img_dur=5),
            'font': pygame.font.Font(resource('assets/font.ttf'), 20),
            'meow_sounds': [pygame.mixer.Sound(resource(f'assets/meow{x}.ogg')) for x in range(1,4)],
            'heart': load_image(resource('assets/heart.png'))
        }

        try:
            with open(resource('assets/highscore.txt'), 'r') as f:
                self.highscore = int(f.read())
        except FileNotFoundError:
                self.highscore = 0

        self.lives = 9
        self.score = 0
        self.combo = 1
        self.last_catch_time = 0
        self.slowdown_timer = 0
        self.spawner = Spawner(self)
        self.paused = False
        self.game_state = 'menu'
        self.list = []
        self.paused_background = None
    
    def write_highscore(self):
        with open(resource('assets/highscore.txt'), 'w') as f:
            f.write(str(self.highscore))

    def register_catch(self, base_points):
        now = pygame.time.get_ticks()
        if now - self.last_catch_time < 2000:
            self.combo += 1
        else:
            self.combo = 1
        self.last_catch_time = now
        self.score += base_points * self.combo

        if self.score > self.highscore:
            self.highscore = self.score

    async def show_menu(self):
        waiting = True
        while waiting:
            self.screen.fill((0, 0, 100))
            title = self.assets['font'].render("Welcome to MEOWWWW!", True, (255, 255, 0))
            prompt = self.assets['font'].render("Click anywhere to start", True, (255, 255, 255))
            self.screen.blit(title, (self.screen.get_width()//2 - title.get_width()//2, 150))
            self.screen.blit(prompt, (self.screen.get_width()//2 - prompt.get_width()//2, 300))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.write_highscore()
                    return
                if event.type == pygame.MOUSEBUTTONDOWN:
                    waiting = False
            self.clock.tick(60)
            await asyncio.sleep(0)
        self.game_state = "playing"

    async def show_game_over(self):
        waiting = True
        while waiting:
            self.screen.fill((0, 0, 0))
            over_text = self.assets['font'].render("GAME OVER", True, (255, 0, 0))
            score_text = self.assets['font'].render("Final Score: " + str(self.score), True, (255, 255, 255))
            prompt = self.assets['font'].render("Click to Restart", True, (255, 255, 255))
            self.screen.blit(over_text, (self.screen.get_width()//2 - over_text.get_width()//2, 150))
            self.screen.blit(score_text, (self.screen.get_width()//2 - score_text.get_width()//2, 220))
            self.screen.blit(prompt, (self.screen.get_width()//2 - prompt.get_width()//2, 300))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.write_highscore()
                    return
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    waiting = False
            self.clock.tick(60)
            await asyncio.sleep(0)
        self.lives = 9
        self.score = 0
        self.combo = 1
        self.list = []
        self.spawner = Spawner(self)
        self.spawner.last_spawn_time = pygame.time.get_ticks()
        self.spawner.last_speed_change = pygame.time.get_ticks()
        self.game_state = "playing"

    def activate_slowdown(self):
        self.slowdown_timer = pygame.time.get_ticks() + 5000

    def slowdown_active(self):
        return pygame.time.get_ticks() < self.slowdown_timer

    async def run(self):
        await self.show_menu()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.write_highscore()
                    return
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.game_state == "playing" and not self.paused:
                        for cat in self.list.copy():
                            cat.check_collision(pygame.mouse.get_pos())
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                        if self.paused:
                            self.paused_background = self.screen.copy()

            if not self.paused and self.game_state == "playing":
                self.screen.fill((100,200,100))
                for cat in self.list:
                    cat.update()
                    cat.render(self.screen)
                self.spawner.handle_spawn()

                self.screen.blit(self.assets['font'].render('Highscore: ' + str(self.highscore), False, (255,255,255)), (10, 10))
                self.screen.blit(self.assets['font'].render('Score: ' + str(self.score) + "  Combo: x" + str(self.combo), False, (255,255,255)), (10, 50))
                for i in range(self.lives):
                    self.screen.blit(self.assets['heart'], (self.screen.get_width() - (i + 1) * self.assets['heart'].get_width() * 1.1, 10))
                if self.slowdown_active():
                    tint = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                    tint.fill((0, 150, 150, 50))
                    self.screen.blit(tint, (0, 0))
                if self.lives <= 0:
                    await self.show_game_over()
            else:
                if self.paused_background:
                    self.screen.blit(self.paused_background, (0, 0))
                else:
                    self.screen.fill((100,200,100))
                paused_overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
                paused_overlay.fill((0, 0, 0, 150))
                self.screen.blit(paused_overlay, (0,0))
                pause_text = self.assets['font'].render("PAUSED", True, (255,255,255))
                self.screen.blit(pause_text, (self.screen.get_width()//2 - pause_text.get_width()//2,
                                              self.screen.get_height()//2 - pause_text.get_height()//2))

            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(0)

class Spawner:
    def __init__(self, game):
        self.game = game
        self.sprite_size = self.game.assets['cat_walk'].image().get_width()
        self.s_width = self.game.screen.get_width()
        self.s_height = self.game.screen.get_height()
        self.speed = 3
        self.last_spawn_time = 0
        self.last_speed_change = 0
        self.spawn_rate = 2000

    def choose_location(self):
        OFFSET = self.sprite_size / 2
        side = random.choice(['left', 'right', 'top', 'bottom'])
        if side in {'left', 'right'}:
            if side == 'left':
                x = -self.sprite_size
                speed_x = random.randint(self.speed, self.speed + 2)
            else:
                x = self.s_width
                speed_x = -random.randint(self.speed, self.speed + 2)
            y = random.randint(0, self.s_height - self.sprite_size)
            if not (y - OFFSET < 0 or y + OFFSET > self.s_height - self.sprite_size):
                dy = random.choice([random.randint(0, int(y - OFFSET)), random.randint(int(y + OFFSET), self.s_height - self.sprite_size)]) - y
            elif y - OFFSET < 0:
                dy = random.randint(int(y + OFFSET), self.s_height - self.sprite_size) - y
            else:
                dy = random.randint(0, int(y - OFFSET)) - y        
            speed_y = (dy) * abs(speed_x) / self.s_width
        else:
            if side == 'top':
                y = -self.sprite_size
                speed_y = random.randint(self.speed, self.speed + 2)
            else:
                y = self.s_height
                speed_y = -random.randint(self.speed, self.speed + 2)
            x = random.randint(0, self.s_width - self.sprite_size)
            if not (x - OFFSET < 0 or x + OFFSET > self.s_width - self.sprite_size):
                dx = random.choice([random.randint(0, int(x - OFFSET)), random.randint(int(x + OFFSET), self.s_width - self.sprite_size)]) - x
            elif x - OFFSET < 0:
                dx = random.randint(int(x + OFFSET), self.s_width - self.sprite_size) - x
            else:
                dx = random.randint(0, int(x - OFFSET)) - x
            speed_x = (dx) * abs(speed_y) / self.s_height
        
        return (x, y), (speed_x, speed_y)

    def handle_spawn(self):
        ticks = pygame.time.get_ticks()
        if ticks - self.last_spawn_time > self.spawn_rate:
            self.spawn()
            self.last_spawn_time = pygame.time.get_ticks()
        if ticks - self.last_speed_change > 4000:
            self.last_speed_change = ticks
            self.spawn_rate = max(750, self.spawn_rate - 400)

    def spawn(self):
        pos, speed = self.choose_location()
        roll = random.randint(0, 100)
        if roll < 5:
            self.game.list.append(Cat(self.game, pos, speed, color='black'))
        elif roll >= 95:
            self.game.list.append(Cat(self.game, pos, speed, color='gold'))
        else:
            self.game.list.append(Cat(self.game, pos, speed))

class Cat:
    def __init__(self, game, pos, speed, color='orange'):
        self.game = game
        self.pos = list(pos)
        self.size = (self.game.assets['cat_walk'].image().get_width(), self.game.assets['cat_walk'].image().get_height())
        self.speed = speed
        self.entered_screen = False
        if self.speed[0] < 0:
            self.flip = True
        elif self.speed[0] > 0:
            self.flip = False
        else:
            self.flip = random.choice([True, False])
        self.color = color

        if self.color in {'orange', 'gold'}:
            self.animation = game.assets['cat_walk'].copy()
        else:
            self.animation = game.assets['black_cat'].copy()
    
    def update(self):
        slow_factor = 0.5 if self.game.slowdown_active() else 1.0
        self.animation.update_frame(slow_factor)
        self.pos[0] += self.speed[0] * slow_factor
        self.pos[1] += self.speed[1] * slow_factor
        if (0 < self.pos[0] < self.game.screen.get_width() - self.size[0]) and (0 < self.pos[1] < self.game.screen.get_height() - self.size[1]):
            self.entered_screen = True

        if self.entered_screen and not self.get_mask().overlap(pygame.mask.from_surface(self.game.screen), (-self.pos[0], -self.pos[1])):
            if self in self.game.list:
                self.game.list.remove(self)
            self.game.lives -= 1

    def check_collision(self, mouse_pos):
        if self.get_mask().overlap(pygame.mask.from_surface(pygame.Surface((1,1))), (mouse_pos[0] - self.pos[0], mouse_pos[1] - self.pos[1])):
            if self in self.game.list:
                self.game.list.remove(self)
            if self.color == 'orange':
                self.game.register_catch(1)
            elif self.color == 'black':
                self.game.register_catch(5)
            elif self.color == 'gold':
                self.game.register_catch(10)
                self.game.activate_slowdown()
            random.choice(self.game.assets['meow_sounds']).play()
    
    def get_mask(self):
        return pygame.mask.from_surface(self.animation.image())

    def render(self, screen):
        img = self.animation.image()
        if self.color == 'gold':
            img = img.copy()
            img.fill((255,215,0), special_flags=pygame.BLEND_RGB_ADD)
        screen.blit(pygame.transform.flip(img, self.flip, False), self.pos)
    
async def main():
    game = Main()
    await game.run()

asyncio.run(main())