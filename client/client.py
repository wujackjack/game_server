'''
client.py as client for game_server
Author: Zhongjun Wu
Email: wuzhongjun1992@126.com
'''

import socket, select
import sys, threading, signal
import getpass

def receive(client, address):
    while True:
        command = raw_input('')
        try:
            client.send(command + '\n')
        except socket.error:
            break
        except socket.timeout:
            break
        except Exception:
            break

def quit(signum, frame):
    print 'Has used ctrl-c to stop.'   
    sys.exit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: python client.py ip_address"
        exit()
    pw_flag = False
    host = sys.argv[1]
    port = 23
    addr = (host, port)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(addr)
    client.settimeout(5000) 
    # use threading to separate send and receive function
    
    thread = threading.Thread(target = receive, args = (client, addr))
    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)
    thread.setDaemon(True)
    thread.start()
    while (True):
        readlist, writelist, exceptlist = \
            select.select([client], [], [], 0)
        if client not in readlist:
            continue
        try:
            info = client.recv(2048)
            if info:
                sys.stdout.write(info)
        except socket.error:
            break
        except socket.timeout:
            break
        except KeyboardInterrupt:
            break
    
