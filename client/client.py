'''
client.py as client for game_server
Author: Zhongjun Wu
Email: wuzhongjun1992@126.com
'''

import socket, select
import sys, threading, signal, time
import getpass

_NORMAL = 0
_SIGNIN = 1
_SIGNUP = 2
mode = _NORMAL

def receive(client, address):

    global mode
    while (True):
    # mainloop for information from server
        time.sleep(0.01)
        readlist, writelist, exceptlist = \
            select.select([client], [], [], 0)
        if client not in readlist:
            continue
        try:
            info = client.recv(2048)
            if info:
                sys.stdout.write(info)
                if "Signin" in info:
                    mode = _SIGNIN
                elif "Signup" in info:
                    mode = _SIGNUP
        except socket.error:
            break
        except socket.timeout:
            break

def quit(signum, frame):
    print 'Has used ctrl-c to stop.'   
    client.close()
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

    # use threading to separate send and receive function
    thread = threading.Thread(target = receive, args = (client, addr))
    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)
    thread.setDaemon(True)
    thread.start()

    # main loop that handle client input 
    # three states include normal, signin, signup
    while (True):
        time.sleep(0.01)
        command = ""
        try:
            if mode == _NORMAL:
                command = raw_input('')
            if mode == _SIGNIN:
                name = command
                while not name:
                    print "Username can not be null. Please re-enter.\nSignin Name:",
                    name = raw_input('')
                print "Please enter password."
                pw = getpass.getpass()
                while not pw:
                    print "Password can not be null. Please re-enter.\n"
                    pw = getpass.getpass()
                command = name + "\t" + pw
                mode  = _NORMAL
            if mode == _SIGNUP:
                name = command
                while not name:
                    print "Username can not be null. Please re-enter.\nSignup Name:",
                    name = raw_input('')
                print "Please enter new password."
                pw1 = getpass.getpass()
                while not pw1:
                    print "Password can not be null. Please re-enter.\n"
                    pw1 = getpass.getpass()
                print "Please enter new password again."
                pw2 = getpass.getpass()
                while not pw2:
                    print "Password can not be null. Please re-enter.\n"
                    pw2 = getpass.getpass()
    
                command = name + "\t" + pw1 + '\t' + pw2
                mode = _NORMAL
            client.send(command + '\n')
        except socket.error:
            break
        except socket.timeout:
            break
    
    client.close()
