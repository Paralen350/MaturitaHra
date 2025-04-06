"""& "g:/win32app/Portable Python-3.10.5 x64/App/Python/python.exe" -m venv venv

Set-ExecutionPolicy -Scope CurrentUser 

poté zadej 0

.\venv\Scripts\activate

"""
# Import potřebných knihoven
import pygame
from pygame.locals import *  # Import konstant jako QUIT, K_ESCAPE apod.
import pickle  # Pro ukládání/načítání herních levelů
from os import path  # Pro práci s cestami k souborům
import mysql.connector  # Pro připojení k MySQL databázi
import bcrypt  # Pro hashování hesel
import time  # Pro měření času

# Konstanty hry
FPS = 60  # Počet snímků za sekundu
SCREEN_WIDTH = 1000  # Šířka obrazovky
SCREEN_HEIGHT = 1000  # Výška obrazovky
TILE_SIZE = 50  # Velikost jednoho dlaždice v pixelech
MAX_LEVELS = 12  # Maximální počet levelů

# Globální skupiny pro sprite (herní objekty)
slime_group = pygame.sprite.Group()  # Skupina pro nepřátele (slizáky)
lava_group = pygame.sprite.Group()  # Skupina pro lávu
exit_group = pygame.sprite.Group()  # Skupina pro východy
platform_group = pygame.sprite.Group()  # Skupina pro pohyblivé platformy

# Inicializace Pygame
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))  # Vytvoření okna
pygame.display.set_caption("Gameska")  # Název okna
clock = pygame.time.Clock()  # Objekt pro řízení FPS

# Nastavení fontu
font = pygame.font.SysFont('Futura', 30)  # Základní font pro text

# Funkce pro připojení k databázi
def connect_db():
    try:
        mydb = mysql.connector.connect(
            host="dbs.spskladno.cz",
            user="student10",
            password="spsnet",
            database="vyuka10"
        )
        return mydb
    except mysql.connector.Error as err:
        print(f"Chyba připojení k databázi: {err}")
        return None

# Funkce pro vytvoření tabulek v databázi
def setup_database():
    mydb = connect_db()
    if mydb:
        cursor = mydb.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS uzivateletestpygame (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE,
            password VARCHAR(255),
            score INT DEFAULT 0
        )
        """)
        mydb.commit()
        cursor.close()
        mydb.close()
        print("Databáze připravena")
    else:
        print("Nepodařilo se připojit k databázi")

# Volání funkce pro nastavení databáze
setup_database()

# Třída pro vstupní políčka (login/registrace)
class InputBox:
    def __init__(self, x, y, w, h, text='', password=False):
        self.rect = pygame.Rect(x, y, w, h)  # Obdélník pro vstupní pole
        self.color_inactive = pygame.Color('black')  # Barva neaktivního pole
        self.color_active = pygame.Color('black')  # Barva aktivního pole
        self.color = self.color_inactive  # Aktuální barva
        self.text = text  # Zadaný text
        self.password = password  # Zda se jedná o pole pro heslo
        self.display_text = '' if password else text  # Text k zobrazení (*** pro hesla)
        self.font = pygame.font.SysFont('Futura', 32)  # Font pro text
        self.txt_surface = self.font.render(self.display_text, True, self.color)  # Vykreslený text
        self.active = False  # Zda je pole aktivní

    # Zpracování událostí pro vstupní pole
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Přepínání aktivního stavu při kliknutí
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    return True  # Potvrzení Enterem
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]  # Mazání textu
                else:
                    self.text += event.unicode  # Přidání znaku
                # Pro hesla zobrazujeme hvězdičky
                self.display_text = '*' * len(self.text) if self.password else self.text
                self.txt_surface = self.font.render(self.display_text, True, self.color)
        return False

    # Aktualizace velikosti pole podle textu
    def update(self):
        width = max(200, self.txt_surface.get_width()+10)
        self.rect.w = width

    # Vykreslení vstupního pole
    def draw(self, screen):
        screen.blit(self.txt_surface, (self.rect.x+5, self.rect.y+5))
        pygame.draw.rect(screen, self.color, self.rect, 2)

# Třída pro správu uživatelů
class UserManager:
    def __init__(self):
        self.current_user = None  # Přihlášený uživatel
        self.score = 0  # Skóre uživatele
    
    # Přihlášení uživatele
    def login(self, username, password):
        mydb = connect_db()
        if mydb:
            cursor = mydb.cursor()
            cursor.execute("SELECT username, password, score FROM uzivateletestpygame WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            mydb.close()
            # Ověření hesla pomocí bcrypt
            if user and bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
                self.current_user = user[0]
                self.score = user[2]
                return True
            return False
        return False
    
    # Registrace nového uživatele
    def register(self, username, password):
        """
    Registruje nového uživatele do databáze s hashem hesla.

    Parametry:
        username (str): Uživatelské jméno (min. 3 znaky)
        password (str): Heslo (min. 3 znaky)

    Návratová hodnota:
        bool: True pokud registrace proběhla úspěšně,
              False pokud uživatel existuje nebo DB chyba

    Vyvolá výjimku:
        ValueError: Pokud username/password jsou příliš krátké
        mysql.connector.Error: Při chybě databáze
    """
        mydb = connect_db()
        if mydb:
            cursor = mydb.cursor()
            try:
                # Kontrola existence uživatele
                cursor.execute("SELECT username FROM uzivateletestpygame WHERE username = %s", (username,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    cursor.close()
                    mydb.close()
                    return False
                
                # Hashování hesla
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                
                # Vložení nového uživatele
                cursor.execute("INSERT INTO uzivateletestpygame (username, password, score) VALUES (%s, %s, %s)", 
                            (username, hashed_password.decode('utf-8'), 0))
                mydb.commit()
                cursor.close()
                mydb.close()
                
                self.current_user = username
                self.score = 0
                return True
            except mysql.connector.Error as err:
                print(f"Databázová chyba: {err}")
                cursor.close()
                mydb.close()
                return False
        return False
    
    # Aktualizace skóre uživatele
    def update_score(self, new_score):
        if self.current_user and new_score > self.score:
            self.score = new_score
            mydb = connect_db()
            if mydb:
                cursor = mydb.cursor()
                cursor.execute("UPDATE uzivateletestpygame SET score = %s WHERE username = %s", 
                            (new_score, self.current_user))
                mydb.commit()
                cursor.close()
                mydb.close()
    
    # Získání žebříčku nejlepších hráčů
    def get_leaderboard(self):
        leaderboard = []
        mydb = connect_db()
        if mydb:
            cursor = mydb.cursor()
            cursor.execute("SELECT username, score FROM uzivateletestpygame ORDER BY score DESC LIMIT 10")
            leaderboard = cursor.fetchall()
            cursor.close()
            mydb.close()
        return leaderboard

# Třída pro kameru (sledování hráče)
class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)  # Obdélník kamery
        self.width = width  # Šířka světa
        self.height = height  # Výška světa
    
    # Aplikace pozice kamery na objekt
    def apply(self, entity):
        return pygame.Rect(entity.rect.x - self.camera.x, 
                          entity.rect.y - self.camera.y,
                          entity.rect.width, entity.rect.height)
    
    # Aktualizace pozice kamery podle hráče
    def update(self, target):
        self.camera.x = target.rect.x - SCREEN_WIDTH // 2
        self.camera.y = target.rect.y - SCREEN_HEIGHT // 2
        # Omezení pohybu kamery na hranice světa
        self.camera.x = max(-(self.width - SCREEN_WIDTH), min(0, self.camera.x))
        self.camera.y = max(-(self.height - SCREEN_HEIGHT), min(0, self.camera.y))

# Třída pro stav hry
class GameState:
    def __init__(self):
        self.main_menu = True  # Zda je zobrazeno hlavní menu
        self.login_menu = False  # Zda je zobrazeno přihlašovací menu
        self.register_menu = False  # Zda je zobrazeno registrační menu
        self.leaderboard_menu = False  # Zda je zobrazen žebříček
        self.game_over = 0  # Stav hry: 0=hra běží, -1=prohra, 1=výhra levelu, 2=výhra hry
        self.level = 0  # Aktuální level
        self.start_time = 0  # Čas začátku levelu
        self.win_time = 0  # Čas výhry pro zpožděný návrat do menu
    
    # Resetování levelu
    def reset_level(self, player):
        self.game_over = 0
        self.start_time = time.time()
        player.reset(100, SCREEN_HEIGHT - 130)  # Resetování pozice hráče
        # Vyčištění skupin objektů
        slime_group.empty()
        lava_group.empty()
        exit_group.empty()
        platform_group.empty()

        # Načtení dat levelu ze souboru
        if path.exists(f'level{self.level}_data'):
            pickle_in = open(f'level{self.level}_data', 'rb')
            world_data = pickle.load(pickle_in)
            return World(world_data)
        return None

# Třída pro tlačítka
class Button:
    def __init__(self, x, y, image):
        self.image = image  # Obrázek tlačítka
        self.rect = self.image.get_rect()  # Obdélník tlačítka
        self.rect.x = x
        self.rect.y = y
        self.clicked = False  # Zda bylo tlačítko kliknuto
    
    # Vykreslení tlačítka
    def draw(self, surface, camera=None):
        action = False
        pos = pygame.mouse.get_pos()
        if camera:
            draw_rect = pygame.Rect(self.rect.x - camera.camera.x, 
                                  self.rect.y - camera.camera.y,
                                  self.rect.width, self.rect.height)
        else:
            draw_rect = self.rect
        if draw_rect.collidepoint(pos):
            if pygame.mouse.get_pressed()[0] == 1 and not self.clicked:
                action = True
                self.clicked = True
            if pygame.mouse.get_pressed()[0] == 0:
                self.clicked = False
        surface.blit(self.image, draw_rect)
        return action  # Vrací True, pokud bylo tlačítko stisknuto

# Třída pro pohyblivé platformy
class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y, move_x, move_y):
        pygame.sprite.Sprite.__init__(self)
        img = pygame.image.load('img/platform.png')
        self.image = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE // 2))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.move_counter = 0  # Počítadlo pohybu
        self.move_direction = 1  # Směr pohybu (1 nebo -1)
        self.move_x = move_x  # Rychlost pohybu v X
        self.move_y = move_y  # Rychlost pohybu v Y

    # Aktualizace pozice platformy
    def update(self):
        self.rect.x += self.move_direction * self.move_x
        self.rect.y += self.move_direction * self.move_y
        self.move_counter += 1
        # Změna směru po určité době
        if abs(self.move_counter) > 50:
            self.move_direction *= -1
            self.move_counter *= -1

# Třída pro hráče
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.reset(x, y)  # Inicializace hráče
    
    # Resetování hráče
    def reset(self, x, y):
        self.images_right = []  # Animace pohybu doprava
        self.images_left = []  # Animace pohybu doleva
        self.index = 0  # Index aktuálního snímku animace
        self.counter = 0  # Počítadlo pro animaci
        # Načtení obrázků pro animaci
        for num in range(1, 13):
            img_right = pygame.image.load(f'img/girl{num}.png')
            img_right = pygame.transform.scale(img_right, (40, 80))
            img_left = pygame.transform.flip(img_right, True, False)
            self.images_right.append(img_right)
            self.images_left.append(img_left)
        self.dead_image = pygame.image.load('img/ghost.png')  # Obrázek při smrti
        self.image = self.images_right[self.index]
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self.vel_y = 0  # Rychlost pádu
        self.jumped = False  # Zda hráč skočil
        self.direction = 0  # Směr pohybu (-1 = vlevo, 1 = vpravo)
        self.in_air = True  # Zda je hráč ve vzduchu
    
    # Aktualizace stavu hráče
    def update(self, game_over, world):
        dx = 0  # Změna pozice X
        dy = 0  # Změna pozice Y
        walk_cooldown = 5  # Rychlost animace chůze
        col_thresh = 20  # Práh kolize pro platformy
        """
    Aktualizuje stav hráče v každém snímku. Zpracovává:
    - Vstup z klávesnice (pohyb, skok)
    - Fyziku (gravitace, kolize)
    - Animace chůze
    - Interakce s objekty (nepřátelé, platformy, východy)
    - Stav hry (prohra/výhra)

    Parametry:
        game_over (int): Aktuální stav hry (0=hra běží, -1=prohra, 1=výhra)
        world (World): Reference na herní svět pro detekci kolizí

    Návratová hodnota:
        int: Nový stav hry (aktualizuje game_over)
    """

        if game_over == 0:  # Pokud hra běží
            key = pygame.key.get_pressed()
            # Skok
            if key[pygame.K_SPACE] and not self.jumped and not self.in_air:
                self.vel_y = -15
                self.jumped = True
            if not key[pygame.K_SPACE]:
                self.jumped = False
            # Pohyb doleva
            if key[pygame.K_LEFT]:
                dx -= 5
                self.counter += 1
                self.direction = -1
            # Pohyb doprava
            if key[pygame.K_RIGHT]:
                dx += 5
                self.counter += 1
                self.direction = 1
            # Reset animace při nečinnosti
            if not key[pygame.K_LEFT] and not key[pygame.K_RIGHT]:
                self.counter = 0
                self.index = 0
                if self.direction == 1:
                    self.image = self.images_right[self.index]
                if self.direction == -1:
                    self.image = self.images_left[self.index]
            
            # Animace chůze
            if self.counter > walk_cooldown:
                self.counter = 0
                self.index += 1
                if self.index >= len(self.images_right):
                    self.index = 0
                if self.direction == 1:
                    self.image = self.images_right[self.index]
                if self.direction == -1:
                    self.image = self.images_left[self.index]
            
            # Gravitace
            self.vel_y += 1
            if self.vel_y > 10:
                self.vel_y = 10
            dy += self.vel_y
            self.in_air = True
            
            # Kolize s dlaždicemi světa
            for tile in world.tile_list:
                # Kolize v ose X
                if tile[1].colliderect(self.rect.x + dx, self.rect.y, self.width, self.height):
                    dx = 0
                # Kolize v ose Y
                if tile[1].colliderect(self.rect.x, self.rect.y + dy, self.width, self.height):
                    # Kolize shora
                    if self.vel_y < 0:
                        dy = tile[1].bottom - self.rect.top
                        self.vel_y = 0
                    # Kolize zdola
                    elif self.vel_y >= 0:
                        dy = tile[1].top - self.rect.bottom
                        self.vel_y = 0
                        self.in_air = False
            
            # Kolize s platformami
            for platform in platform_group:
                # Kolize v ose X
                if platform.rect.colliderect(self.rect.x + dx, self.rect.y, self.width, self.height):
                    dx = 0
                # Kolize v ose Y
                if platform.rect.colliderect(self.rect.x, self.rect.y + dy, self.width, self.height):
                    # Kolize shora
                    if abs((self.rect.top + dy) - platform.rect.bottom) < col_thresh:
                        self.vel_y = 0
                        dy = platform.rect.bottom - self.rect.top
                    # Kolize zdola
                    elif abs((self.rect.bottom + dy) - platform.rect.top) < col_thresh:
                        self.rect.bottom = platform.rect.top - 1
                        self.in_air = False
                        dy = 0
                    # Pohyb společně s platformou
                    if platform.move_x != 0:
                        self.rect.x += platform.move_direction
            
            # Kolize s nepřáteli
            if pygame.sprite.spritecollide(self, slime_group, False):
                game_over = -1
            # Kolize s lávou
            if pygame.sprite.spritecollide(self, lava_group, False):
                game_over = -1
            # Kolize s východem
            if pygame.sprite.spritecollide(self, exit_group, False):
                game_over = 1
            
            # Aktualizace pozice hráče
            self.rect.x += dx
            self.rect.y += dy
        
        # Pokud hráč zemřel
        elif game_over == -1:
            self.image = self.dead_image
            if self.rect.y > 200:
                self.rect.y -= 5  # Efekt "vznášení" po smrti
        
        return game_over

# Třída pro herní svět/level
class World:
    def __init__(self, data):
        self.tile_list = []  # Seznam všech dlaždic
        dirt_img = pygame.image.load('img/dirt.png')  # Obrázek hlíny
        grass_img = pygame.image.load('img/grass.png')  # Obrázek trávy
        
        # Výpočet rozměrů světa
        world_width = len(data[0]) * TILE_SIZE
        world_height = len(data) * TILE_SIZE
        
        row_count = 0
        for row in data:
            col_count = 0
            for tile in row:
                # 1 = hlína
                if tile == 1:
                    img = pygame.transform.scale(dirt_img, (TILE_SIZE, TILE_SIZE))
                    img_rect = img.get_rect()
                    img_rect.x = col_count * TILE_SIZE
                    img_rect.y = row_count * TILE_SIZE
                    tile = (img, img_rect)
                    self.tile_list.append(tile)
                # 2 = tráva
                if tile == 2:
                    img = pygame.transform.scale(grass_img, (TILE_SIZE, TILE_SIZE))
                    img_rect = img.get_rect()
                    img_rect.x = col_count * TILE_SIZE
                    img_rect.y = row_count * TILE_SIZE
                    tile = (img, img_rect)
                    self.tile_list.append(tile)
                # 3 = slizák (nepřítel)
                if tile == 3:
                    slime = Enemy(col_count * TILE_SIZE, row_count * TILE_SIZE + 15)
                    slime_group.add(slime)
                # 4 = horizontální platforma
                if tile == 4:
                    platform = Platform(col_count * TILE_SIZE, row_count * TILE_SIZE, 1, 0)
                    platform_group.add(platform)
                # 5 = vertikální platforma
                if tile == 5:
                    platform = Platform(col_count * TILE_SIZE, row_count * TILE_SIZE, 0, 1)
                    platform_group.add(platform)
                # 6 = láva
                if tile == 6:
                    lava = Lava(col_count * TILE_SIZE, row_count * TILE_SIZE + (TILE_SIZE // 2))
                    lava_group.add(lava)
                # 8 = východ
                if tile == 8:
                    exit = Exit(col_count * TILE_SIZE, row_count * TILE_SIZE - (TILE_SIZE // 2))
                    exit_group.add(exit)
                col_count += 1
            row_count += 1
        
        self.width = world_width
        self.height = world_height

    # Vykreslení světa
    def draw(self, surface, camera=None):
        for tile in self.tile_list:
            if camera:
                draw_rect = pygame.Rect(tile[1].x - camera.camera.x, 
                                     tile[1].y - camera.camera.y,
                                     tile[1].width, tile[1].height)
                surface.blit(tile[0], draw_rect)
            else:
                surface.blit(tile[0], tile[1])

# Třída pro nepřátele (slizáky)
class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load('img/slime.png')
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.move_direction = 1  # Směr pohybu
        self.move_counter = 0  # Počítadlo pohybu
    
    # Aktualizace pozice nepřítele
    def update(self):
        self.rect.x += self.move_direction
        self.move_counter += 1
        # Změna směru po určité době
        if abs(self.move_counter) > 50:
            self.move_direction *= -1
            self.move_counter *= -1

# Třída pro lávu
class Lava(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        img = pygame.image.load('img/lava.png')
        self.image = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE // 2))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

# Třída pro východ
class Exit(pygame.sprite.Sprite):
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        img = pygame.image.load('img/exit.png')
        self.image = pygame.transform.scale(img, (TILE_SIZE, int(TILE_SIZE * 1.5)))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

# Funkce pro načítání obrázků
def load_images():
    """
    Načte všechny obrázky potřebné pro hru. Pokud soubor neexistuje,
    vytvoří náhradní tlačítko s barevným pozadím a textem.

    Návratová hodnota:
        dict: Slovník s klíči:
            - 'sun': Obrázek slunce
            - 'bg': Obrázek pozadí
            - 'restart_btn': Tlačítko restart
            - ... (další klíče viz kód)
            
    Poznámka:
        Pro chybějící tlačítka generuje základní verzi s textem.
        Očekává se, že obrázky jsou ve složce 'img/'.
    """

    images = {
        'sun': pygame.image.load('img/sun.png'),
        'bg': pygame.image.load('img/sky.png'),
        'restart_btn': pygame.image.load('img/restart_btn.png'),
        'start_btn': pygame.image.load('img/start_btn.png'),
        'exit_btn': pygame.image.load('img/exit_btn.png'),
        'login_btn': pygame.image.load('img/login_btn.png') if path.exists('img/login_btn.png') else None,
        'register_btn': pygame.image.load('img/register_btn.png') if path.exists('img/register_btn.png') else None,
        'back_btn': pygame.image.load('img/back_btn.png') if path.exists('img/back_btn.png') else None,
        'leaderboard_btn': pygame.image.load('img/leaderboard_btn.png') if path.exists('img/leaderboard_btn.png') else None
    }

    # Vytvoření výchozích tlačítek, pokud obrázky neexistují
    btn_width, btn_height = 200, 50
    if not images['start_btn']:
        start_surf = pygame.Surface((btn_width, btn_height))
        start_surf.fill((0, 200, 0))  # Zelené tlačítko
        text = font.render('Start', True, (255, 255, 255))
        start_surf.blit(text, (btn_width//2 - 30, btn_height//2 - 10))
        images['start_btn'] = start_surf

    if not images['exit_btn']:
        exit_surf = pygame.Surface((btn_width, btn_height))
        exit_surf.fill((200, 0, 0))  # Červené tlačítko
        text = font.render('Exit', True, (255, 255, 255))
        exit_surf.blit(text, (btn_width//2 - 30, btn_height//2 - 10))
        images['exit_btn'] = exit_surf

    if not images['login_btn']:
        login_surf = pygame.Surface((btn_width, btn_height))
        login_surf.fill((100, 100, 200))  # Modré tlačítko
        text = font.render('Login', True, (255, 255, 255))
        login_surf.blit(text, (btn_width//2 - 30, btn_height//2 - 10))
        images['login_btn'] = login_surf

    if not images['register_btn']:
        register_surf = pygame.Surface((btn_width, btn_height))
        register_surf.fill((100, 200, 100))  # Světle zelené tlačítko
        text = font.render('Register', True, (255, 255, 255))
        register_surf.blit(text, (btn_width//2 - 50, btn_height//2 - 10))
        images['register_btn'] = register_surf

    if not images['back_btn']:
        back_surf = pygame.Surface((btn_width, btn_height))
        back_surf.fill((200, 100, 100))  # Oranžové tlačítko
        text = font.render('Back', True, (255, 255, 255))
        back_surf.blit(text, (btn_width//2 - 30, btn_height//2 - 10))
        images['back_btn'] = back_surf

    if not images['leaderboard_btn']:
        leaderboard_surf = pygame.Surface((btn_width, btn_height))
        leaderboard_surf.fill((200, 200, 100))  # Žluté tlačítko
        text = font.render('Leaderboard', True, (255, 255, 255))
        leaderboard_surf.blit(text, (btn_width//2 - 70, btn_height//2 - 10))
        images['leaderboard_btn'] = leaderboard_surf

    return images

# Funkce pro vykreslení textu
def draw_text(surface, text, font, color, x, y):
    img = font.render(text, True, color)
    surface.blit(img, (x, y))

# Funkce pro vykreslení skupin objektů s ohledem na kameru
def draw_groups_with_camera(surface, camera):
    for sprite in slime_group:
        draw_rect = camera.apply(sprite)
        surface.blit(sprite.image, draw_rect)
    for sprite in lava_group:
        draw_rect = camera.apply(sprite)
        surface.blit(sprite.image, draw_rect)
    for sprite in exit_group:
        draw_rect = camera.apply(sprite)
        surface.blit(sprite.image, draw_rect)

# Hlavní funkce hry
def main():
    game_state = GameState()  # Stav hry
    images = load_images()  # Načtení obrázků
    user_manager = UserManager()  # Správce uživatelů

    # Vytvoření vstupních polí pro login/registraci
    username_box = InputBox(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 100, 200, 50)
    password_box = InputBox(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 25, 200, 50, password=True)

    error_message = ""  # Zpráva o chybě při přihlášení/registraci

    player = Player(100, SCREEN_HEIGHT - 130)  # Vytvoření hráče

    # Načtení prvního levelu
    world = None
    if path.exists(f'level{game_state.level}_data'):
        with open(f'level{game_state.level}_data', 'rb') as f:
            world_data = pickle.load(f)
            world = World(world_data)
            camera = Camera(world.width, world.height)
    else:
        # Výchozí velikost kamery, pokud neexistují data levelu
        camera = Camera(SCREEN_WIDTH * 2, SCREEN_HEIGHT * 2)

    # Vytvoření tlačítek
    restart_button = Button(SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT // 2 + 150, images['restart_btn'])
    start_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 150, images['start_btn'])
    exit_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 130, images['exit_btn'])
    login_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 220, images['login_btn'])
    register_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 100, images['register_btn'])
    submit_login_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 20, images['login_btn'])
    submit_register_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 100, images['register_btn'])
    back_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 250, images['back_btn'])
    leaderboard_button = Button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 250, images['leaderboard_btn'])

    running = True
    while running:
        clock.tick(FPS)  # Omezení FPS

        # Zpracování událostí
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    # Návrat do menu pomocí ESC
                    if game_state.login_menu or game_state.register_menu or game_state.leaderboard_menu:
                        game_state.login_menu = False
                        game_state.register_menu = False
                        game_state.leaderboard_menu = False
                    else:
                        game_state.main_menu = True
                        game_state.level = 0
                        world = game_state.reset_level(player)

            # Zpracování vstupních polí
            if game_state.login_menu or game_state.register_menu:
                username_box.handle_event(event)
                password_box.handle_event(event)

        # Aktualizace vstupních polí
        username_box.update()
        password_box.update()

        # Vykreslení pozadí
        screen.blit(images['bg'], (0, 0))
        screen.blit(images['sun'], (400, 100))

        # Hlavní menu
        if game_state.main_menu:
            if user_manager.current_user:
                # Přihlášený uživatel - zobrazení uvítací zprávy
                draw_text(screen, f"Vítej, {user_manager.current_user}!", font, (0, 0, 0), 
                         SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 300)

                # Název hry
                draw_text(screen, "Gameska", pygame.font.SysFont('Futura', 60), (0, 0, 0), 
                         SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 400)

                # Tlačítka pro přihlášeného uživatele
                if start_button.draw(screen):
                    game_state.main_menu = False
                    game_state.level = 1
                    world = game_state.reset_level(player)
                    if world:
                        camera = Camera(world.width, world.height)

                if leaderboard_button.draw(screen):
                    game_state.main_menu = False
                    game_state.leaderboard_menu = True

                if exit_button.draw(screen):
                    running = False
            else:
                # Nepřihlášený uživatel - zobrazení přihlašovacích možností
                draw_text(screen, "Gameska", pygame.font.SysFont('Futura', 60), (0, 0, 0), 
                         SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 400)

                draw_text(screen, "Prosím přihlašte se nebo zaregistrujte", font, (0, 0, 0), 
                         SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 - 300)

                if login_button.draw(screen):
                    game_state.main_menu = False
                    game_state.login_menu = True
                    username_box.text = ""
                    password_box.text = ""
                    username_box.display_text = ""
                    password_box.display_text = ""
                    error_message = ""

                if register_button.draw(screen):
                    game_state.main_menu = False
                    game_state.register_menu = True
                    username_box.text = ""
                    password_box.text = ""
                    username_box.display_text = ""
                    password_box.display_text = ""
                    error_message = ""

                if exit_button.draw(screen):
                    running = False

        # Přihlašovací menu
        elif game_state.login_menu:
            draw_text(screen, "Přihlášení", pygame.font.SysFont('Futura', 60), (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT // 2 - 200)

            draw_text(screen, "Uživatel:", font, (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 85)

            draw_text(screen, "Heslo:", font, (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 10)

            # Zobrazení chybové zprávy
            if error_message:
                draw_text(screen, error_message, font, (255, 0, 0), 
                         SCREEN_WIDTH // 2 - len(error_message) * 5, SCREEN_HEIGHT // 2 + 125)

            # Vykreslení vstupních polí
            username_box.draw(screen)
            password_box.draw(screen)

            # Tlačítka
            if submit_login_button.draw(screen):
                if username_box.text and password_box.text:
                    if user_manager.login(username_box.text, password_box.text):
                        game_state.login_menu = False
                        game_state.main_menu = True
                        error_message = ""
                    else:
                        error_message = "Neplatné uživatelské jméno nebo heslo"
                else:
                    error_message = "Prosím vyplňte uživatelské jméno a heslo"

            if back_button.draw(screen):
                game_state.login_menu = False
                game_state.main_menu = True
                error_message = ""

        # Registrační menu
        elif game_state.register_menu:
            draw_text(screen, "Registrace", pygame.font.SysFont('Futura', 60), (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 200)

            draw_text(screen, "Uživatel:", font, (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 85)

            draw_text(screen, "Heslo:", font, (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 10)

            # Zobrazení chybové zprávy
            if error_message:
                draw_text(screen, error_message, font, (255, 0, 0), 
                         SCREEN_WIDTH // 2 - len(error_message) * 5, SCREEN_HEIGHT // 2 + 125)

            # Vykreslení vstupních polí
            username_box.draw(screen)
            password_box.draw(screen)

            # Tlačítka
            if submit_register_button.draw(screen):
                if username_box.text and password_box.text:
                    if len(username_box.text) < 3 or len(password_box.text) < 3:
                        error_message = "Uživatelské jméno a heslo musí mít alespoň 3 znaky"
                    elif user_manager.register(username_box.text, password_box.text):
                        game_state.register_menu = False
                        game_state.main_menu = True
                        error_message = ""
                    else:
                        error_message = "Uživatelské jméno již existuje"
                else:
                    error_message = "Prosím vyplňte uživatelské jméno a heslo"

            if back_button.draw(screen):
                game_state.register_menu = False
                game_state.main_menu = True
                error_message = ""

        # Žebříček nejlepších hráčů
        elif game_state.leaderboard_menu:
            draw_text(screen, "Žebříček", pygame.font.SysFont('Futura', 60), (0, 0, 0), 
                     SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 400)

            # Získání žebříčku
            leaderboard = user_manager.get_leaderboard()

            if leaderboard:
                # Hlavička tabulky
                draw_text(screen, "Uživatel", font, (0, 0, 0), SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 300)
                draw_text(screen, "Skóre", font, (0, 0, 0), SCREEN_WIDTH // 2 + 150, SCREEN_HEIGHT // 2 - 300)

                # Oddělovací čára
                pygame.draw.line(screen, (0, 0, 0), 
                               (SCREEN_WIDTH // 2 - 300, SCREEN_HEIGHT // 2 - 270),
                               (SCREEN_WIDTH // 2 + 300, SCREEN_HEIGHT // 2 - 270), 2)

                # Zobrazení položek žebříčku
                for i, (username, score) in enumerate(leaderboard):
                    y_pos = SCREEN_HEIGHT // 2 - 250 + (i * 40)
                    # Zvýraznění aktuálního uživatele
                    if username == user_manager.current_user:
                        pygame.draw.rect(screen, (200, 200, 255), 
                                      (SCREEN_WIDTH // 2 - 300, y_pos - 5, 600, 40))

                    draw_text(screen, f"{i+1}. {username}", font, (0, 0, 0), 
                             SCREEN_WIDTH // 2 - 250, y_pos)
                    draw_text(screen, str(score), font, (0, 0, 0), 
                             SCREEN_WIDTH // 2 + 150, y_pos)
            else:
                draw_text(screen, "Žádná skóre!", font, (0, 0, 0), 
                         SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2)

            if back_button.draw(screen):
                game_state.leaderboard_menu = False
                game_state.main_menu = True

        # Herní scéna
        else:
            """
    Sleduje globální stav hry a spravuje přechody mezi obrazovkami.
    
    Atributy:
        main_menu (bool): Zda je zobrazeno hlavní menu
        level (int): Aktuální level (1-12)
        game_over (int): Stav hry: 
            0 = hra běží, 
            -1 = prohra, 
            1 = výhra levelu,
            2 = výhra hry
            """
            if world:
                # Aktualizace kamery a hráče
                camera.update(player)
                game_state.game_over = player.update(game_state.game_over, world)

                # Aktualizace nepřátel a platforem
                slime_group.update()
                platform_group.update()

                # Vykreslení světa s ohledem na kameru
                world.draw(screen, camera)
                draw_groups_with_camera(screen, camera)

                # Vykreslení platforem
                for platform in platform_group:
                    draw_rect = camera.apply(platform)
                    screen.blit(platform.image, draw_rect)

                # Vykreslení hráče
                player_draw_rect = camera.apply(player)
                screen.blit(player.image, player_draw_rect)

                # Zobrazení čísla levelu
                draw_text(screen, f'Level: {game_state.level}', font, (255, 255, 255), 10, 10)

                # Zobrazení skóre (pokud je uživatel přihlášen)
                if user_manager.current_user:
                    draw_text(screen, f'Skóre: {user_manager.score}', font, (255, 255, 255), 10, 40)

                # Kontrola dokončení levelu
                if game_state.game_over == 1:
                    # Výpočet skóre: 100 - (5 * sekundy)
                    time_taken = int(time.time() - game_state.start_time)
                    score = max(0, 100 - (5 * time_taken))
                    user_manager.update_score(user_manager.score + score)

                    # Přechod na další level
                    game_state.level += 1
                    if game_state.level <= MAX_LEVELS:
                        world = game_state.reset_level(player)
                        if world:
                            camera = Camera(world.width, world.height)
                            game_state.game_over = 0
                    else:
                        # Hra dokončena
                        game_state.win_time = time.time()
                        game_state.game_over = 2  # Stav pro výhru

                # Kontrola prohry
                if game_state.game_over == -1:
                    draw_text(screen, 'KONEC HRY!', font, (255, 0, 0), SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2)
                    if restart_button.draw(screen):
                        world = game_state.reset_level(player)
                        if world:
                            camera = Camera(world.width, world.height)

                # Kontrola výhry (dokončení všech levelů)
                if game_state.game_over == 2:
                    draw_text(screen, 'VÝHRA!', font, (0, 255, 0), SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2)
                    # Návrat do menu po 5 sekundách
                    if time.time() - game_state.win_time > 5:
                        game_state.main_menu = True
                        game_state.level = 0
                        game_state.game_over = 0
                        world = game_state.reset_level(player)

        pygame.display.update()  # Aktualizace obrazovky

    pygame.quit()  # Ukončení Pygame

if __name__ == "__main__":
    main()




#Úprava levelů - do dalšího .py souboru
"""import pygame
import pickle
from os import path


pygame.init()

clock = pygame.time.Clock()
fps = 60

#game window
tile_size = 50
cols = 20
margin = 100
screen_width = tile_size * cols
screen_height = (tile_size * cols) + margin

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Level Editor')


#load images
sun_img = pygame.image.load('img/sun.png')
sun_img = pygame.transform.scale(sun_img, (tile_size, tile_size))
bg_img = pygame.image.load('img/sky.png')
bg_img = pygame.transform.scale(bg_img, (screen_width, screen_height - margin))
dirt_img = pygame.image.load('img/dirt.png')
grass_img = pygame.image.load('img/grass.png')
blob_img = pygame.image.load('img/slime.png')
platform_x_img = pygame.image.load('img/platform_x.png')
platform_y_img = pygame.image.load('img/platform_y.png')
lava_img = pygame.image.load('img/lava.png')
exit_img = pygame.image.load('img/exit.png')
save_img = pygame.image.load('img/save_btn.png')
load_img = pygame.image.load('img/load_btn.png')


#define game variables
clicked = False
level = 1

#define colours
white = (255, 255, 255)
green = (144, 201, 120)

font = pygame.font.SysFont('Futura', 24)

#create empty tile list
world_data = []
for row in range(20):
	r = [0] * 20
	world_data.append(r)

#create boundary
for tile in range(0, 20):
	world_data[19][tile] = 2
	world_data[0][tile] = 1
	world_data[tile][0] = 1
	world_data[tile][19] = 1

#function for outputting text onto the screen
def draw_text(text, font, text_col, x, y):
	img = font.render(text, True, text_col)
	screen.blit(img, (x, y))

def draw_grid():
	for c in range(21):
		#vertical lines
		pygame.draw.line(screen, white, (c * tile_size, 0), (c * tile_size, screen_height - margin))
		#horizontal lines
		pygame.draw.line(screen, white, (0, c * tile_size), (screen_width, c * tile_size))


def draw_world():
	for row in range(20):
		for col in range(20):
			if world_data[row][col] > 0:
				if world_data[row][col] == 1:
					#dirt blocks
					img = pygame.transform.scale(dirt_img, (tile_size, tile_size))
					screen.blit(img, (col * tile_size, row * tile_size))
				if world_data[row][col] == 2:
					#grass blocks
					img = pygame.transform.scale(grass_img, (tile_size, tile_size))
					screen.blit(img, (col * tile_size, row * tile_size))
				if world_data[row][col] == 3:
					#enemy blocks
					img = pygame.transform.scale(blob_img, (tile_size, int(tile_size * 0.75)))
					screen.blit(img, (col * tile_size, row * tile_size + (tile_size * 0.25)))
				if world_data[row][col] == 4:
					#horizontally moving platform
					img = pygame.transform.scale(platform_x_img, (tile_size, tile_size // 2))
					screen.blit(img, (col * tile_size, row * tile_size))
				if world_data[row][col] == 5:
					#vertically moving platform
					img = pygame.transform.scale(platform_y_img, (tile_size, tile_size // 2))
					screen.blit(img, (col * tile_size, row * tile_size))
				if world_data[row][col] == 6:
					#lava
					img = pygame.transform.scale(lava_img, (tile_size, tile_size // 2))
					screen.blit(img, (col * tile_size, row * tile_size + (tile_size // 2)))
				if world_data[row][col] == 7:
					#exit
					img = pygame.transform.scale(exit_img, (tile_size, int(tile_size * 1.5)))
					screen.blit(img, (col * tile_size, row * tile_size - (tile_size // 2)))



class Button():
	def __init__(self, x, y, image):
		self.image = image
		self.rect = self.image.get_rect()
		self.rect.topleft = (x, y)
		self.clicked = False

	def draw(self):
		action = False

		#get mouse position
		pos = pygame.mouse.get_pos()

		#check mouseover and clicked conditions
		if self.rect.collidepoint(pos):
			if pygame.mouse.get_pressed()[0] == 1 and self.clicked == False:
				action = True
				self.clicked = True

		if pygame.mouse.get_pressed()[0] == 0:
			self.clicked = False

		#draw button
		screen.blit(self.image, (self.rect.x, self.rect.y))

		return action

#create load and save buttons
save_button = Button(screen_width // 2 - 150, screen_height - 80, save_img)
load_button = Button(screen_width // 2 + 50, screen_height - 80, load_img)

#main game loop
run = True
while run:

	clock.tick(fps)

	#draw background
	screen.fill(green)
	screen.blit(bg_img, (0, 0))
	screen.blit(sun_img, (tile_size * 2, tile_size * 2))

	#load and save level
	if save_button.draw():
		#save level data
		pickle_out = open(f'level{level}_data', 'wb')
		pickle.dump(world_data, pickle_out)
		pickle_out.close()
	if load_button.draw():
		#load in level data
		if path.exists(f'level{level}_data'):
			pickle_in = open(f'level{level}_data', 'rb')
			world_data = pickle.load(pickle_in)


	#show the grid and draw the level tiles
	draw_grid()
	draw_world()


	#text showing current level
	draw_text(f'Level: {level}', font, white, tile_size, screen_height - 60)
	draw_text('Press UP or DOWN to change level', font, white, tile_size, screen_height - 40)

	#event handler
	for event in pygame.event.get():
		#quit game
		if event.type == pygame.QUIT:
			run = False
		#mouseclicks to change tiles
		if event.type == pygame.MOUSEBUTTONDOWN and clicked == False:
			clicked = True
			pos = pygame.mouse.get_pos()
			x = pos[0] // tile_size
			y = pos[1] // tile_size
			#check that the coordinates are within the tile area
			if x < 20 and y < 20:
				#update tile value
				if pygame.mouse.get_pressed()[0] == 1:
					world_data[y][x] += 1
					if world_data[y][x] > 8:
						world_data[y][x] = 0
				elif pygame.mouse.get_pressed()[2] == 1:
					world_data[y][x] -= 1
					if world_data[y][x] < 0:
						world_data[y][x] = 8
		if event.type == pygame.MOUSEBUTTONUP:
			clicked = False
		#up and down key presses to change level number
		if event.type == pygame.KEYDOWN:
			if event.key == pygame.K_UP:
				level += 1
			elif event.key == pygame.K_DOWN and level > 1:
				level -= 1

	#update game display window
	pygame.display.update()

pygame.quit()"""