import socket
import threading
import fcntl
import struct
import RPi.GPIO as GPIO
import sched, time

audioEnabled = False

def broadcast_server_IP(addr): 
    while True:
        #print("[+] Sending {0}:{1}" .format(UDP_BROADCAST_ADDR, UDP_BROADCAST_PORT))
        broadcastSocket.sendto((BROADCAST_SERVER_IP_COMMAND).to_bytes(1, byteorder='big') + bytes(addr, 'utf-8'), (UDP_BROADCAST_ADDR, UDP_BROADCAST_PORT))
        time.sleep(2)

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])

def handle_client(clientSocket, addr, socketList):
    while clientSocket != None:
        try:
            data = clientSocket.recv(1) # receive 1 byte as the identifier for the type of message
            if data:
                print(data)
                global audioEnabled
                global users
                # identify the type of request : register user, request audio, terminate audio
                if data[0] == REGISTER_USER_COMMAND:
                    print("[+] Data Received: Register User")
                    userID = clientSocket.recv(MAX_USER_NAME_LENGTH)
                    users[clientSocket] = userID;
                    print("[+] Registered user: %s" % (userID))
                    clientSocket.send("Registered\n".encode())
                elif data[0] == REQUEST_AUDIO_COMMAND:
                    print("[+] Data Received: Request Audio")
                    if not audioEnabled:
                        print("[+] AudioEnabled = True")
                        audioEnabled = True # Acknowledge, broadcast to all users
                        clientSocket.send(GRANT_AUDIO_ACCESS_COMMAND.encode());
                        try:
                            for client in socketList:
                                client.send(users[clientSocket] + " transmitting\n".encode()) # grant access message
                        except Exception as e:
                            print(e.args)
                        GPIO.output(AUDIO_PTT_PIN, False);    
                    else:
                        clientSocket.send("Channel in use\n".encode())
                elif data[0] == TERMINATE_AUDIO_COMMAND:
                    print("[+] Data Received: Terminate Audio")
                    audioEnabled = False
                    GPIO.output(AUDIO_PTT_PIN, True)
                    for client in socketList:
                        client.send((TERMINATE_AUDIO_COMMAND).to_bytes(1, byteorder='big') + "\n".encode()) # broadcast terminate audio message
        except Exception as e:
            pass
            #print(e.args)

# Constants
REGISTER_USER_COMMAND = 0x7E
REQUEST_AUDIO_COMMAND = 0x8E
GRANT_AUDIO_ACCESS_COMMAND = "Granted\n"
TERMINATE_AUDIO_COMMAND = 0xAE
BROADCAST_SERVER_IP_COMMAND = 0xFE

LOCAL_IP = get_ip_address('eth0')
TCP_PORT = 1880
UDP_BROADCAST_PORT = 8018
UDP_BROADCAST_ADDR = "255.255.255.255"
UDP_BROADCAST_DELAY = 1
MAX_NO_OF_CONNECTIONS = 20  
SOCKET_READ_TIMEOUT = 0.5
MAX_USER_NAME_LENGTH = 10 # bytes
AUDIO_ON_PIN = 3
AUDIO_PTT_PIN = 5

# Variables
socketList = []
users = dict()

# Initializations
# GPIO for controller SA818
GPIO.setmode(GPIO.BOARD)
GPIO.setup(AUDIO_ON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(AUDIO_PTT_PIN, GPIO.OUT)
GPIO.output(AUDIO_PTT_PIN, True)
# TCP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((LOCAL_IP, TCP_PORT))
server.listen(MAX_NO_OF_CONNECTIONS)
print("[+] Listening on {0}:{1}" .format(LOCAL_IP, TCP_PORT))
# UDP socket and periodic function
broadcastSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
broadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
threading.Thread(target=broadcast_server_IP, args=(LOCAL_IP,)).start()
# broadcast_server_IP_scheduler = sched.scheduler(time.time, time.sleep)
# broadcast_server_IP_scheduler.enter(UDP_BROADCAST_DELAY, 1, broadcast_server_IP, (LOCAL_IP,))
# broadcast_server_IP_scheduler.run(blocking=False)

# Blocking process for listenning to incoming TCP connections
while True:
    clientSocket, clientIP = server.accept()
    print("[+] Accepting a connection from: {0}:" .format(clientIP))

    clientSocket.settimeout(SOCKET_READ_TIMEOUT)
    socketList.append(clientSocket)
    threading.Thread(target=handle_client, args=(clientSocket, clientIP, socketList)).start()
