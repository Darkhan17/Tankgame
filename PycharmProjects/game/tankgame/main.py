import pika
import json
import uuid
from threading import Thread
import pygame
import time
from enum import Enum
import random
from pygame import mixer
import threading
import concurrent.futures
from multiprocessing.pool import ThreadPool
IP='34.254.177.17'
PORT=5672
USERNAME='dar-tanks'
PASSWORD='5orPLExUYnyVYZg48caMpX'
VIRTUAL_HOST='dar-tanks'
pygame.init()
height=600
width=1100
screen=pygame.display.set_mode((width,height))
pygame.display.set_caption('WORLD OF TANKS')
font = pygame.font.SysFont('Arial', 40)
pygame.init()

def game_menu():
    background = pygame.image.load('back.jpeg')
    menu_loop=True
    font = pygame.font.SysFont('Arial', 40)

    while menu_loop:
        screen.blit(background, (0, 0))
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                menu_loop=False
        header=font.render("GAME MENU", 1, (255,0,0))
        screen.blit(header,(450,200))
        mouse=pygame.mouse.get_pos()
        button('Single player',400,250,300,50,(100,100,100),(255,0,0),'single')
        button('Multiplayer',400,350,300,50,(100,100,100),(255,0,0),'multiplayer')
        button('Multiplayer AI',400,450,300,50,(100,100,100),(255,0,0),'AI')
        button('QUIT',400,550,300,50,(100,100,100),(255,0,0),'QUIT')
        icon=pygame.image.load('logo.png').convert_alpha()
        icon.set_colorkey((0,0,0))
        screen.blit(icon,(280,0))


        pygame.display.flip()

def button(message,x,y,width,height,color1,color2,action=None):
    font = pygame.font.SysFont('Arial', 40)
    mouse = pygame.mouse.get_pos()
    click=pygame.mouse.get_pressed()
    if x + width > mouse[0] > x and y + height > mouse[1] > y:
        pygame.draw.rect(screen, color2, (x, y, width, height))
        if click[0]==1 and action!=None:
            if action=="multiplayer":
                game_multiplayer()
            if action=='QUIT':
                pygame.quit()
            if action=="single":
                game_single()
            if action=='AI':
                Ai_multiplayer()


    else:
        pygame.draw.rect(screen, color1, (x, y, width, height))
    textsurface = font.render(message, True, (0, 0, 0))
    textrect = textsurface.get_rect()
    textrect.center = ((x + int(width / 2), y + int(height / 2)))
    screen.blit(textsurface, textrect)


class TankRpcClient:
    def __init__(self):
        self.connection=pika.BlockingConnection(
            pika.ConnectionParameters(
                host=IP,
                port=PORT,
                virtual_host=VIRTUAL_HOST,
                credentials=pika.PlainCredentials(
                    username=USERNAME,
                    password=PASSWORD
            )
        )
    )
        self.channel= self.connection.channel()
        queue=self.channel.queue_declare(queue='',auto_delete=True,exclusive=True)
        self.callback_queue= queue.method.queue
        self.channel.queue_bind(
             exchange='X:routing.topic',
             queue=self.callback_queue
    )
        self.channel.basic_consume(
        queue=self.callback_queue,
        on_message_callback=self.on_response,
        auto_ack=True)

        self.response=None
        self.corr_id=None
        self.token=None
        self.tank_id=None
        self.room_id=None

    def on_response(self, ch, method,props,body):
        if self.corr_id==props.correlation_id:
            self.response= json.loads(body)
            print(self.response)


    def call(self, key, message={}):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='X:routing.topic',
            routing_key=key,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message)
        )
        while self.response is None:

            self.connection.process_data_events()
    def check_server_status(self):
        self.call('tank.request.healthcheck')
        return self.response['status']== '200'

    def obtain_token(self, room_id):
        message = {'roomId': room_id}
        self.call('tank.request.register',message)
        if 'token' in self.response:
            self.token=self.response['token']
            self.tank_id=self.response['tankId']
            self.room_id=self.response['roomId']
            return True
        return False



    def turn_tank(self, token, direction):
        message={'token':token,
                'direction':direction}
        self.call('tank.request.turn',message)



    def fire_bullet(self,token):
        message={'token':token}
        self.call('tank.request.fire',message)



class TankConsumerClient(Thread):
    def __init__(self,room_id):
        super().__init__()
        self.connection=pika.BlockingConnection(
            pika.ConnectionParameters(
                host=IP,
                port=PORT,
                virtual_host=VIRTUAL_HOST,
                credentials=pika.PlainCredentials(
                    username=USERNAME,
                    password=PASSWORD
                    )
                )
            )
        self.channel= self.connection.channel()
        queue=self.channel.queue_declare(queue='',auto_delete=True,exclusive=True)
        event_listener=queue.method.queue
        self.channel.queue_bind(exchange='X:routing.topic',queue=event_listener,routing_key='event.state.'+room_id)
        self.channel.basic_consume(
            event_listener,
            on_message_callback=self.on_response,
            auto_ack=True
            )
        self.response=None
    def on_response(self, ch, method, props, body):
        self.response=json.loads(body)
        print(self.response)
    def run(self):
        self.channel.start_consuming()

UP='UP'
DOWN='DOWN'
LEFT='LEFT'
RIGHT='RIGHT'

MOVE_KEYS = {
    pygame.K_UP: UP,
    pygame.K_LEFT:LEFT,
    pygame.K_DOWN: DOWN,
    pygame.K_RIGHT: RIGHT
}
class Tank:
    def __init__(self,id,x,y,width,height,direction,health,score,img):
        self.id=id
        self.x=x
        self.y=y
        self.width=width
        self.height=height
        self.directon=direction
        self.helth=health
        self.score=score
        self.icon = pygame.image.load(str(img)+'.png').convert_alpha()
        self.icon.set_colorkey((0, 0, 0))
        self.rect = pygame.Surface((self.width, self.height))
        self.rect.set_colorkey((0, 0, 0))
        self.rect.blit(self.icon, (0, 0))

    def draw(self):
        if self.directon =='UP':
            self.rect = pygame.transform.rotate(self.icon, 0)
        if self.directon == 'RIGHT':
            self.rect = pygame.transform.rotate(self.icon, -90)
        if self.directon == 'LEFT':
            self.rect = pygame.transform.rotate(self.icon, 90)
        if self.directon =='DOWN':
            self.rect=pygame.transform.rotate(self.icon, 180)
        screen.blit(self.rect,(self.x,self.y))
class Bullet:
    def __init__(self,owner,x,y,width,height,direction,id):
        self.owner=owner
        self.x=x
        self.y=y
        self.width=width
        self.height=height
        self.direction=direction
        self.id=id
    def draw(self):
        if self.owner!=self.id:
            pygame.draw.rect(screen,(255,0,0),(self.x,self.y,self.width,self.height))
        else:
            pygame.draw.rect(screen,(0,255,0),(self.x,self.y,self.width,self.height))

def panel(remaining_time,health,score,id,owner_id,indent):
    pygame.draw.line(screen,(255,255,255),(840,0),(840,600),4)
    font1 = pygame.font.SysFont('Arial', 25)
    textsurface = font1.render('Remainig time: {0}'.format(remaining_time), True, (255, 255, 255))
    textrect = textsurface.get_rect()
    textrect.center = (970, 580)
    screen.blit(textsurface, textrect)
    pygame.draw.line(screen, (255, 255, 255), (840, 70), (1100, 70), 4)
    if id == owner_id:
        header=font1.render('Your',True,(255,0,0))
        screen.blit(header,(970,10))
        textsurface_owner = font1.render('Id:{0} Health: {1} Score:{2}'.format(id, health, score), True,(255, 0, 0))
        textrect_owner=textsurface_owner.get_rect()
        textrect_owner.center=(970,50)
        screen.blit(textsurface_owner,textrect_owner)
    else:
        oponent_header=font1.render('Opponents',True,(255,255,255))
        screen.blit(oponent_header,(970,90))
        textsurface_health = font1.render('Id:{0} Health: {1} Score:{2}'.format(id, health, score), True, (255, 255, 255))
        textrect_health = textsurface_health.get_rect()
        textrect_health.center = (970,indent)
        screen.blit(textsurface_health,textrect_health)
def game_multiplayer():
    mixer.music.load('back.wav')
    mixer.music.play(-1)
    mainloop = True
    client = TankRpcClient()
    i = 30
    while i != 0:
        check = client.obtain_token('room-' + str(i))
        if check == True:
            event_client = TankConsumerClient('room-' + str(i))
            event_client.daemon = True
            event_client.start()
            i = 0
        else:
            i = i - 1
    while mainloop:
        screen.fill((0,0,0))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                mainloop=False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    mainloop=False
                    event_client.daemon = True
                if event.key in MOVE_KEYS:
                    client.turn_tank(client.token, MOVE_KEYS[event.key])
                if event.key ==pygame.K_SPACE:
                    client.fire_bullet(client.token)
                    ShootSound.play()
        img=1
        indent=90

        tanks = event_client.response['gameField']['tanks']
        bullets = event_client.response['gameField']['bullets']
        kicked=event_client.response['kicked']
        winners=event_client.response['winners']
        losers=event_client.response['losers']
        tanks = sorted(tanks, key=lambda k: k['score'], reverse=True)

        for bullet in bullets:
            shoot=Bullet(bullet['owner'],bullet['x'],bullet['y'],bullet['width'],bullet['height'],bullet['direction'],client.tank_id)
            shoot.draw()
        for tank in kicked:
            if tank['tankId']==client.tank_id:
                finish('kicked',tank['score'])
        for tank in losers:
            if tank['tankId']==client.tank_id:
                finish('loser',tank['score'])
        for tank in winners:
            if tank['tankId']==client.tank_id:
                finish('winner',tank['score'])
        remaining_time = event_client.response['remainingTime']
        for tank in tanks:
            if tank['id']==client.tank_id:
                sprite=Tank(tank['id'],tank['x'],tank['y'],tank['width'],tank['height'],tank['direction'],tank['health'],tank['score'],0)
            else:
                sprite=Tank(tank['id'],tank['x'],tank['y'],tank['width'],tank['height'],tank['direction'],tank['health'],tank['score'],img)
            sprite.draw()
            img=img+1
            if tank['id']!=client.tank_id:
                indent=indent+30
            panel(remaining_time,tank['health'],tank['score'],tank['id'],client.tank_id,indent)
        pygame.display.flip()
    client.connection.close()
    pygame.quit()
def finish(status,score):
    kick_loop=True
    while kick_loop:
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                kick_loop=False
                pygame.quit()
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:
                    kick_loop==False
                if event.key==pygame.K_r:
                    kick_loop=False
        screen.fill((0, 0, 0))
        if status=='kicked':
            header = font.render("You are kicked!", 1, (255, 0, 0))
        if status=='loser':
            header= font.render("You lost!",1, (255,0,0))
        if status=='winner':
            header=font.render("You are winner",1, (255,0,0))
        points=font.render('Your score: {0}'.format(score),1,(255,0,0))
        restart=font.render('Press "R" to restart the game',1,(255,0,0))
        screen.blit(header,(500,250))
        screen.blit(points,(500,300))
        screen.blit(restart,(500,350))
        pygame.display.flip()
    game_multiplayer()

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
###############           --------------------------CODE FOR SINGLE PALYER ----------------------------------------###################
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


class Tank_single:
    def __init__(self,id , x, y, speed, img, direction, d_right=pygame.K_RIGHT, d_left=pygame.K_LEFT, d_up=pygame.K_UP,
                 d_down=pygame.K_DOWN, shooting=pygame.K_SPACE):
        self.id = id
        self.x = x
        self.y = y
        self.speed = speed
        self.direction = direction
        self.KEY = {d_right: Direction.RIGHT, d_left: Direction.LEFT,
                    d_up: Direction.UP, d_down: Direction.DOWN}
        self.lives = 3
        self.icon = pygame.image.load(str(img) +'.png').convert_alpha()
        self.icon.set_colorkey((0, 0, 0))
        self.status = True
        self.width=31
        self.height=31
        self.rect = pygame.Surface((31, 31))
        self.rect.set_colorkey((0, 0, 0))
        self.rect.blit(self.icon, (0, 0))
        self.rot_rect = self.rect.get_rect()
        self.shoot = shooting
        self.health = 3
        self.color = (255,0,0)
        self.live=3
        self.bullet_speed=4

    def move(self,seconds):
        if self.direction == Direction.RIGHT:
            self.rect = pygame.transform.rotate(self.icon, -90)
            self.x = self.x + self.speed * seconds
            if self.x > width:
                self.x = -self.rect.__sizeof__() + self.speed * seconds
        if self.direction == Direction.LEFT:
            self.rect = pygame.transform.rotate(self.icon, 90)
            self.x = self.x - self.speed * seconds
            if self.x < -self.rect.__sizeof__():
                self.x = width + -self.speed * seconds
        if self.direction == Direction.UP:
            self.rect = pygame.transform.rotate(self.icon, 0)
            self.y = self.y - self.speed * seconds
            if self.y < -self.rect.__sizeof__():
                self.y = height - self.speed * seconds
        if self.direction == Direction.DOWN:
            self.rect = pygame.transform.rotate(self.icon, 180)
            self.y = self.y + self.speed * seconds
            if self.y > height:
                self.y = -self.rect.__sizeof__() + self.speed * seconds
        self.draw()
    def draw(self):
        if self.status:
            screen.blit(self.rect,(self.x, self.y))
    def change_direction(self, direction):
        self.direction = direction

    def score(self, live):
        self.live = live
        self.live = self.live - 1
class Direction(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    STAY_RIGHT=5
    STAY_LEFT=6
class Shoot(Tank):
    def __init__(self,id, x, y, color, direction,speed):
        self.id=id
        self.x = x
        self.y = y
        self.color = color
        self.speed = speed
        self.direction = direction
        self.status = True
        self.distance = 0
        self.width=15
        self.height=5
    def move(self):
        if self.direction == Direction.LEFT:
            self.x =self.x - self.speed
        if self.direction == Direction.RIGHT:
            self.x = self.x + self.speed
        if self.direction == Direction.UP:
            self.width,self.height=5,15
            self.y = self.y - self.speed
        if self.direction == Direction.DOWN:
            self.width,self.height=5,15
            self.y =self.y + self.speed
        self.distance = self.distance + 1
        if self.distance > (2 * 100):
            self.status = False
        self.draw()

    def draw(self):
        if self.status:
            pygame.draw.rect(screen,(self.color),(self.x,self.y,self.width,self.height))
class Food():
    def __init__(self,x,y,radius=3):
        self.x=x
        self.y=y
        self.status=True
        self.radius=radius
        self.color=(0,255,0)
    def draw(self):
        if self.status:
            pygame.draw.circle(screen,(self.color), (self.x, self.y), self.radius)
class Wall():
    def __init__(self,x,y):
        self.x=x
        self.y=y
        self.width=30
        self.height=30
        self.img=pygame.image.load('wall.png')
        self.status=True
    def draw(self):
        if self.status:
            screen.blit(self.img,(self.x,self.y))


def give_coordinates(tank):
    if tank.direction == Direction.RIGHT:
        x = tank.x + tank.width + int(tank.width / 2)
        y = tank.y + int(tank.width / 2)

    if tank.direction == Direction.LEFT:
        x = tank.x - int(tank.width / 2)
        y = tank.y + int(tank.width / 2)

    if tank.direction == Direction.UP:
        x = tank.x + int(tank.width / 2)
        y = tank.y - int(tank.width / 2)

    if tank.direction == Direction.DOWN:
        x = tank.x + int(tank.width / 2)
        y = tank.y + tank.width + int(tank.width / 2)
    if tank.direction == Direction.STAY_RIGHT:
        x = tank.x + tank.width + int(tank.width / 2)
        y = tank.y + int(tank.width / 2)
        tank.direction=Direction.RIGHT
    if tank.direction == Direction.STAY_LEFT:
        x = tank.x - int(tank.width / 2)
        y = tank.y + int(tank.width / 2)
        tank.direction=Direction.LEFT

    if tank.id==1:
        bul = Shoot(1,x, y, (255,0,0), tank.direction,tank.bullet_speed)
    else:
        bul = Shoot(2, x, y, (0, 0, 255), tank.direction, tank.bullet_speed)
    bullets.append(bul)
def collision():
    for bul in bullets:
        for tank in tanks:
            if (tank.x + tank.width + bul.width > bul.x > tank.x - bul.width) and (
            (tank.y + tank.width + bul.width > bul.y > tank.y - bul.width)) and bul.status == True:
                vzryvSound.play()
                bul.color = (0, 0, 0)
                tank.score(tank.live)
                bul.status = False

                tank.x = random.randint(50, width - 70)
                tank.y = random.randint(50, height - 70)


    for bul in bullets:
        if bul.x < 0:
            bul.x = 0
            bul.direction=Direction.RIGHT
        if bul.x > width:
            bul.x = width
            bul.direction=Direction.LEFT
        if bul.y > height:
            bul.y = height
            bul.direction=Direction.UP
        if bul.y < 0:
            bul.y = 0
            bul.direction=Direction.DOWN

    for tank in tanks:
        for wall in walls:
            if (wall.x  + tank.width > tank.x > wall.x - tank.width) and (
                    (wall.y + wall.width  > tank.y > wall.y - tank.width)) and wall.status == True and tank.status==True:
                vzryvSound.play()
                wall.status=False
                walls.remove(wall)
                tank.live=tank.live-1

    for bul in bullets:
        for wall in walls:
            if (wall.x + wall.width + bul.width > bul.x > wall.x - bul.width) and (
            (wall.y + wall.width + bul.height > bul.y > wall.y - bul.height)) and bul.status == True:
                wall.status = False
                walls.remove(wall)
                vzryvSound.play()
                bul.color = (0, 0, 0)
                bul.status = False
def superpower():
    for superpower in food:
        for tank in tanks:
            if (tank.x + tank.width + superpower.radius > superpower.x > tank.x - superpower.radius) and (
            (tank.y + tank.width + superpower.radius > superpower.y > tank.y - superpower.radius)) and superpower.status == True:
                superpower.color = (0, 0, 0)
                superpower.status = False
                change_speed(tank.id)
def show ():
    score1=font.render( str(tank1.live),1,tank1.color)
    score2=font.render(str(tank2.live),1,tank2.color)
    screen.blit(score1, (20,20))
    screen.blit(score2, (1000,20))
    if tank1.live==0:
        res = font.render('Game Over', True, (255, 123, 0))
        result=font.render('Second player WIN',1,tank2.color)
        screen.blit(result,(500,400))
        screen.blit(res, (500,200))
        pygame.display.update()
        time.sleep(5)
        pygame.quit()
    if tank2.live==0:
        res = font.render('Game Over', True, (255, 123, 0))
        result=font.render('First player WIN',1,tank1.color)
        screen.blit(res,(500,300))
        screen.blit(result, (500, 500))
        pygame.display.update()
        time.sleep(5)
        pygame.quit()
def call_food():
    thread1=threading.Timer(5.0, call_food).start()
    x=Food(random.randint(50,width-50),random.randint(50,height-50),3)
    food.append(x)
def change_speed (id):
    for tank in tanks:
        if tank.id==id:
            tank.speed=160
            tank.bullet_speed=8
            time.sleep(5)
            tank.speed=80
            tank.bullet_speed=4
def wall_give_coordinates():
    for i in range(10):
        x=random.randint(50,width)
        y=random.randint(50,height)
        t=x,y
        wall_coordinates.append(t)
    for i in wall_coordinates:
        if i[0] == 100 and i[1] == 100:
            break
        elif i[0] == 600 and i[1] == 600:
            break
        brick = Wall(i[0], i[1])
        for tank in tanks:
            for wall in walls:
                if (wall.x + tank.width > tank.x > wall.x - tank.width) and (
                        (wall.y + wall.width > tank.y > wall.y - tank.width)) and wall.status == True:
                    wall.status = False
                    walls.remove(wall)
        walls.append(brick)

tank1 = Tank_single(1,100, 100, 80, 5, Direction.STAY_RIGHT, pygame.K_RIGHT, pygame.K_LEFT,pygame.K_UP, pygame.K_DOWN, pygame.K_RETURN)
tank2 = Tank_single(2,600, 500, 80, 2, Direction.STAY_LEFT, pygame.K_d, pygame.K_a, pygame.K_w,pygame.K_s, pygame.K_SPACE)
ShootSound=pygame.mixer.Sound('bullet.wav')
vzryvSound=pygame.mixer.Sound('vzryv.wav')
tanks = [tank1, tank2]
walls=[]
wall_coordinates=[]
wall_give_coordinates()
bullets = []
food=[]
fps=30
clock = pygame.time.Clock()
def game_single():
    mixer.music.load('back.wav')
    mixer.music.play(-1)
    running=True
    call_food()
    while running:
        thread3=threading.Thread(target=superpower,daemon=True)
        thread3.start()
        milliseconds = clock.tick(fps)
        seconds = milliseconds / 1000.0
        screen.fill((0, 0, 0))
        collision()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                pressed = pygame.key.get_pressed()
                for tank in tanks:
                    if event.key in tank.KEY.keys():
                        tank.change_direction(tank.KEY[event.key])
                    if event.key in tank.KEY.keys():
                        tank.move(seconds)
                    if pressed[tank.shoot]:
                        ShootSound.play()
                        give_coordinates(tank)

        show()
        for tank in tanks:
            tank.move(seconds)
        for bul in bullets:
            bul.move()
        for xp in food:
            xp.draw()
        for wall in walls:
            wall.draw()


        pygame.display.flip()
    pygame.quit()



# ______-------------------------------------------------AI ______---------------------------------




def Ai_multiplayer():
    mainloop=True
    client = TankRpcClient()
    i=30
    while i!=0:
        check=client.obtain_token('room-' + str(i))
        if check==True:
            event_client = TankConsumerClient('room-' + str(i))
            event_client.daemon = True
            event_client.start()
            i=0
        else:
            i=i-1
    tank_target_id = 0
    while mainloop:
        screen.fill((0,0,0))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                mainloop=False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    mainloop=False
        img=1
        indent=90
        tanks = event_client.response['gameField']['tanks']
        bullets = event_client.response['gameField']['bullets']
        kicked = event_client.response['kicked']
        winners = event_client.response['winners']
        losers = event_client.response['losers']
        tanks = sorted(tanks, key=lambda k: k['score'], reverse=True)
        target_tanks=sorted(tanks, key=lambda k:['health'], reverse=True)
        if tank_target_id == 0:
            for tank in target_tanks:
                if tank['id']==client.tank_id:
                    target_tanks.remove(tank)
                else:
                    tank_target_id=tank['id']
        print(target_tanks)
        print(tank_target_id)

        for tank in kicked:
            if tank_target_id==tank['tankId']:
                tank_target_id=0
            if tank['tankId']==client.tank_id:
                finish_AI('kicked',tank['score'])
        for tank in losers:
            if tank_target_id==tank['tankId']:
                tank_target_id = 0
            if tank['tankId']==client.tank_id:
                finish_AI('loser',tank['score'])
        for tank in winners:
            if tank_target_id==tank['tankId']:
                tank_target_id = 0
            if tank['tankId']==client.tank_id:
                finish_AI('winner',tank['score'])
        for tank in tanks:
            if tank['id']==client.tank_id:
                sprite=Tank_AI(tank['id'],tank['x'],tank['y'],tank['width'],tank['height'],tank['direction'],tank['health'],tank['score'],0)
                for tank_target in target_tanks:
                    if tank_target_id==tank_target['id']:
                        if len(bullets)>=1:
                            for bullet in bullets:
                                if bullet['owner'] != client.tank_id:
                                    move=attack_target(tank_target['x'],tank_target['y'],tank['x'],tank['y'],tank_target['direction'],tank['direction'],bullet['x'],bullet['y'],bullet['direction'])
                                    if move:
                                        client.turn_tank(client.token,move)
                        else:
                            move=attack(tank_target['x'],tank_target['y'],tank['x'],tank['y'],tank_target['direction'],tank['direction'])
                            if move:
                                client.turn_tank(client.token, move)
                        fire=AI_fire(tank_target['x'],tank_target['y'],tank['x'],tank['y'],tank_target['direction'],tank['direction'])
                        if fire == 'fire':
                            client.fire_bullet(client.token)
            else:
                sprite=Tank_AI(tank['id'],tank['x'],tank['y'],tank['width'],tank['height'],tank['direction'],tank['health'],tank['score'],img)
            sprite.draw()
            img=img+1
            if tank['id']!=client.tank_id:
                indent=indent+30
            remaining_time = event_client.response['remainingTime']
            panel(remaining_time,tank['health'],tank['score'],tank['id'],client.tank_id,indent)
        for bullet in bullets:
            shoot = Bullet(bullet['owner'], bullet['x'], bullet['y'], bullet['width'], bullet['height'], bullet['direction'], client.tank_id)
            shoot.draw()
        pygame.display.flip()
    pygame.quit()
class Tank_AI:
    def __init__(self, id, x, y, width, height, direction, health, score, img):
        self.id = id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.directon = direction
        self.helth = health
        self.score = score
        self.icon = pygame.image.load(str(img) + '.png').convert_alpha()
        self.icon.set_colorkey((0, 0, 0))
        self.rect = pygame.Surface((self.width, self.height))
        self.rect.set_colorkey((0, 0, 0))
        self.rect.blit(self.icon, (0, 0))

    def draw(self):
        if self.directon == 'UP':
            self.rect = pygame.transform.rotate(self.icon, 0)
        if self.directon == 'RIGHT':
            self.rect = pygame.transform.rotate(self.icon, -90)
        if self.directon == 'LEFT':
            self.rect = pygame.transform.rotate(self.icon, 90)
        if self.directon == 'DOWN':
            self.rect = pygame.transform.rotate(self.icon, 180)
        screen.blit(self.rect, (self.x, self.y))
class Bullet_AI:
    def __init__(self, owner, x, y, width, height, direction, id):
        self.owner = owner
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.direction = direction
        self.id = id

    def draw(self):
        if self.owner != self.id:
            pygame.draw.rect(screen, (255, 0, 0), (self.x, self.y, self.width, self.height))
        else:
            pygame.draw.rect(screen, (0, 255, 0), (self.x, self.y, self.width, self.height))

def AI_fire(x_target,y_target,x_tank,y_tank,direction_target,direction_tank):
    tank_width=31
    tank_height=31
    if (y_target+tank_height/2-tank_height<=y_tank+tank_height/2<=y_target+tank_height/2+tank_height) and (direction_target=='LEFT' or direction_target=="RIGHT"):
        return 'fire'
    if (x_target + tank_width /2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and (direction_target == 'DOWN' or direction_target == "UP"):
        return 'fire'
def dodge(x_bullet,y_bullet,direction_bullet,tank_direction,x_tank,y_tank):

    tank_height=31
    tank_width=31
    bullet_width=15
    bullet_height=5
    if direction_bullet=="RIGHT" and y_tank<=y_bullet+bullet_height<=y_tank+tank_height:
        return "DOWN"

    if direction_bullet=="LEFT" and y_tank<=y_bullet+bullet_height<=y_tank+tank_height:
        return "UP"

    if direction_bullet=="UP" and x_tank<=x_bullet+bullet_height<=x_tank+tank_width:
        return "RIGHT"

    if direction_bullet=="DOWN" and x_tank<=x_bullet+bullet_height<=x_tank+tank_width:
        return "LEFT"

def attack_target(x_target,y_target,x_tank,y_tank,direction_target,direction_tank,x_bullet,y_bullet,direction_bullet):
    tank_width=31
    tank_width=31
    if x_target<x_tank:
        request = dodge(x_bullet, y_bullet, direction_bullet, direction_tank, x_tank, y_tank)
        if request:
            return request
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target > y_tank:
            return "DOWN"
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target < y_tank:
            return 'UP'
        else:
             return "LEFT"
    if x_target>x_tank:
        request = dodge(x_bullet, y_bullet, direction_bullet, direction_tank, x_tank, y_tank)
        if request:
            return request
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target > y_tank:
            return "DOWN"
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target < y_tank:
            return 'UP'
        else:
            return "RIGHT"
def attack(x_target,y_target,x_tank,y_tank,direction_target,direction_tank):
    tank_width = 31
    tank_width = 31
    if x_target < x_tank:
        if(x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target > y_tank:
            return "DOWN"
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target < y_tank:
            return 'UP'
        else:
            return "LEFT"

    if x_target > x_tank:
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target > y_tank:
            return "DOWN"
        if (x_target + tank_width / 2 - tank_width <= x_tank + tank_width / 2 <= x_target + tank_width / 2 + tank_width) and y_target < y_tank:
            return 'UP'
        else:
            return "RIGHT"
def finish_AI(status,score):
    font = pygame.font.SysFont('Arial', 40)
    kick_loop=True
    while kick_loop:
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                kick_loop=False
                pygame.quit()
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:
                    kick_loop==False
                if event.key==pygame.K_r:
                    kick_loop=False
        screen.fill((0, 0, 0))
        if status=='kicked':
            header = font.render("You are kicked!", 1, (255, 0, 0))
        if status=='loser':
            header= font.render("You lost!", 1, (255,0,0))
        if status=='winner':
            header=font.render("You are winner",1, (255,0,0))
        points=font.render('Your score: {0}'.format(score),1,(255,0,0))
        restart=font.render('Press "R" to restart the game',1,(255,0,0))
        screen.blit(header,(500,250))
        screen.blit(points,(500,300))
        screen.blit(restart,(500,350))
        pygame.display.flip()
    Ai_multiplayer()

x_my_tank=0
y_my_tank=0
distance=[]
game_menu()



#game_start()