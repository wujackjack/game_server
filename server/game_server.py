'''
A game server that supports chatting and online time record.
Author: Zhongjun Wu
Email: wuzhongjun1992@126.com 
'''

import socket
import time
import select

class Server(object):
    _socket = None
    _host = ""
    _port = 0
    _timeout = 0
    _id2names = {}
    _id2client = {}
    _id_states = {}
    _player_data = []
    _curid = 0
    _todos = []
    _new_todos = []
    _state2func = {}

    _WAIT = 0
    _WAIT_SIGNIN = 1 # wait_signin -> wait_pw -> success 
    _WAIT_PW = 2
    _SUCCESS = 3
    _WAIT_SIGNUP = 4 # wait_signup -> wait_pw1 -> wait_pw2 -> success
    _WAIT_PW1 = 5
    _WAIT_PW2 = 6
    _EVENT_NEW_CLIENT = 7
    _EVENT_INFO = 8
    _EVENT_PLAYER_OUT = 9

    def __init__(self, host="0.0.0.0", port=23, timeout=2):
        self._curid = 0

        self.load_data()
        self._state2func = self.func_init()
        self._host = host
        self._port = port
        self._timeout = timeout
        # tcp socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(False)
        # set io reuse
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # bind and listen 
        self._socket.bind((self._host, self._port))
        self._socket.listen(1)

    def load_data(self):
        """
        load account data and history record
        """
        f = open("data", 'r')
        self._player_data = eval(f.read())
        f.close()
        return
    
    def func_init(self):
        state2func = {}
        state2func[self._WAIT] = self.wait
        state2func[self._WAIT_SIGNIN] = self.wait_signin
        state2func[self._WAIT_SIGNUP] = self.wait_signup
        state2func[self._WAIT_PW] = self.wait_pw
        state2func[self._WAIT_PW1] = self.wait_pw1
        state2func[self._WAIT_PW2] = self.wait_pw2
        state2func[self._SUCCESS] = self.routine
        return state2func

    def run(self):
        """
        for main loop, check for new connections, informations and disconnections
        """
        self.check_new_connection()
        self.check_disconnection()
        self.check_new_information()
        
        self._todos = list(self._new_todos)
        self._new_todos = []

    def check_new_connection(self):
        
        readlist, writelist, exceptlist = \
            select.select([self._socket], [], [], 0)
        # no connection
        if self._socket not in readlist:
            return

        connected_socket, addr = self._socket.accept()
        self._id2client[self._curid] = \
            _client(connected_socket, addr[0], time.time(), self._WAIT)
        self._new_todos.append((self._EVENT_NEW_CLIENT, self._curid))
        self._curid = self._curid + 1

    def check_new_information(self):

        for tmp_id, tmp_client in list(self._id2client.items()):
            readlist, writelist, exceptlist = \
                select.select([tmp_client.inner_socket], [], [], 0)
            # no new information from this client
            if tmp_client.inner_socket not in readlist:
                continue
            try:
                ori_info = tmp_client.inner_socket.recv(2048)
                info = ori_info
                # info = self._process_sent_data(ori_info)
                
                info = info.strip()
                self._new_todos.append((self._EVENT_INFO, tmp_id, info))
            except socket.error:
                self.handle_disconnect(tmp_id)
    
    def check_disconnection(self):
        # check if any client is out
        for tmp_id, tmp_client in list(self._id2client.items()):
            if time.time() - tmp_client.tic < 2.0:
                continue
            try:
                tmp_client.inner_socket.sendall("\x00")
                tmp_client.tic = time.time()
            except socket.error:
                self.handle_disconnect(tmp_id)

    def server_close(self):
        # close relevant socket
        for tmp_client in self._id2client.values():
            tmp_client.inner_socket.close()
        self._socket.close()
    
    def handle_disconnect(self, tmp_id):
        if self._id2client[tmp_id].state == self._SUCCESS:
            tmp_name = self._id2names[tmp_id]
            self._new_todos.append((self._EVENT_PLAYER_OUT, tmp_id, tmp_name))
        # update login time data and write to file
        self.update_data(tmp_id) 
        del(self._id2client[tmp_id])

    def get_new_players(self):
        # get the id of new players
        res_id = []
        for x in self._todos:
            if x[0] == self._EVENT_NEW_CLIENT:
                res_id.append(x[1])
        return res_id

    def get_commands(self):
        # get the id and content of new commands
        res_id_and_content = []
        for x in self._todos:
            if x[0] == self._EVENT_INFO:
                res_id_and_content.append((x[1], x[2]))
        return res_id_and_content

    def get_disconnection(self):
        # get the id of disconnect players
        res_id = []
        for x in self._todos:
            if x[0] == self._EVENT_PLAYER_OUT:
                res_id.append((x[1], x[2]))
        return res_id

    def send(self, tmp_id, data):
        # try to send information and error occurs means the player is out
        try:
            self._id2client[tmp_id].inner_socket.sendall(data)
        except KeyError: 
            pass
        except socket.error:
            self.handle_disconnect(tmp_id)

    def update_data(self, tmp_id):
        # update the data of disconnected player
        if self._id2client[tmp_id].state == self._SUCCESS:
            # self._id2client[tmp_id].quit_time = time.time()
            last_time = time.time() - self._id2client[tmp_id].login_time
            self._player_data[self._id2client[tmp_id].name]["last_time"] = \
                last_time
            self._player_data[self._id2client[tmp_id].name]["total_time"] += \
                last_time

            self.update_file()
            del(self._id2names[tmp_id])
    
    def update_file(self):
        # update file
        f = open("data", 'w')
        f.write(str(self._player_data))
        f.close()

    def print_wait(self, tmp_id):
        self.send(tmp_id, \
            'Type "signin" to login or "signup" to create an account.\n\r')
    
    def wait(self, tmp_id, content):
        # cur_state: wait
        # next_state: signin or signup
        
        if not content:
            return
        # choose to signin
        if content == "signin":
            self._id2client[tmp_id].state = self._WAIT_SIGNIN
            self.send(tmp_id, \
                'Please enter user name.\n\r')
            self.send(tmp_id, 'Name: \n\r')

        # choose to signin
        elif content == "signup":
            self._id2client[tmp_id].state = self._WAIT_SIGNUP
            self.send(tmp_id, \
                'Please enter new user name.\n\r')
            self.send(tmp_id, 'Name: \n\r')

        # invalid command
        elif content:
            self.send(tmp_id, "Invalid command\n")
            self.print_wait(tmp_id)
    
    def wait_signin(self, tmp_id, content):
        # prev_state: wait
        # cur_state: wait_signin , to input user_name
        # next_state: wait_pw

        if not content:
            self.send(tmp_id, \
                'Username can not be null. Please re-enter.\n\r')
            self.send(tmp_id, "Name: \n\r")
            return

        if content not in self._player_data:
            self.send(tmp_id, \
                'Username does not exist in database.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        '''
        if tmp_id in self._id2names:
            self.send(tmp_id, \
                'User has login on other client.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        '''
        self._id2client[tmp_id].name = content
        self.send(tmp_id, \
                'Please enter password.\n\r')
        self.send(tmp_id, 'Password:\n\r')
        self._id2client[tmp_id].state = self._WAIT_PW
        return content

    def wait_signup(self, tmp_id, content):
        # prev_state: wait
        # cur_state: wait_signup , to input user name
        # next_state: wait_pw1

        if not content:
            self.send(tmp_id, \
                'Username can not be null. Please re-enter.\n\r')
            self.send(tmp_id, "Name: \n\r")
            return

        if content in self._player_data:
            self.send(tmp_id, \
                'Username already exists in database.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        self._id2client[tmp_id].new_name = content
        self.send(tmp_id, \
                'Please enter new password.\n\r')
        self.send(tmp_id, 'Password: \n\r')
        self._id2client[tmp_id].state = self._WAIT_PW1
        return content

    def wait_pw(self, tmp_id, content):
        # prev_state: wait_signin
        # cur_state: wait_pw , to input password
        # next_state: success
        
        if not content:
            self.send(tmp_id, \
                'Password can not be null. Please re-enter.\n\r')
            self.send(tmp_id, "Password: \n\r")
            return

        if self._player_data[self._id2client[tmp_id].name]["pw"] == \
                content:
            self.send(tmp_id, \
                'You have successfully login.\n\r')
            self.send(tmp_id, \
                'Type "help" to see command lists\n\r')
            self.announce_in(self._id2client[tmp_id].name)
            self._id2client[tmp_id].login_time = time.time()
            self._id2names[tmp_id] = self._id2client[tmp_id].name
            self._id2client[tmp_id].state = self._SUCCESS
        else:
            self.send(tmp_id, \
                'Wrong password. Please re-login or create new account\n\r')
            self._id2client[tmp_id].name = None
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT

    def wait_pw1(self, tmp_id, content):
        # prev_state: wait_signup
        # cur_state: wait_pw1 , to input password first time
        # next_state: wait_pw2

        if not content:
            self.send(tmp_id, \
                'Password can not be null. Please re-enter.\n\r')
            self.send(tmp_id, "Password: \n\r")
            return

        self._id2client[tmp_id].pw1 = content
        self.send(tmp_id, \
                'Please enter new password again.\n\r')
        self.send(tmp_id, 'Password: \n\r')
        self._id2client[tmp_id].state = self._WAIT_PW2

    def wait_pw2(self, tmp_id, content):
        # prev_state: wait_pw1
        # cur_state: wait_pw2 , to input password second time
        # next_state: success

        if not content:
            self.send(tmp_id, \
                'Password can not be null. Please re-enter.\n\r')
            self.send(tmp_id, "Password: \n\r")
            return

        if self._id2client[tmp_id].pw1 != content:
            self.send(tmp_id, 'Password aren\'t consistent.\n\r')
            self._id2client[tmp_id].new_name = None 
            self._id2client[tmp_id].pw1 = None 
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return 
        new_player = {"total_time" : 0, \
                      "pw" : self._id2client[tmp_id].pw1, \
                      "last_time" : 0}
        self._player_data[self._id2client[tmp_id].new_name] = new_player
        self.update_file()
        self._id2client[tmp_id].name = self._id2client[tmp_id].new_name
        self.send(tmp_id, \
            'You have successfully created an account and login.\n\r')
        self.send(tmp_id, \
            'Type "help" to see command lists\n\r')
        self.announce_in(self._id2client[tmp_id].name)
        self._id2client[tmp_id].login_time = time.time()
        self._id2names[tmp_id] = self._id2client[tmp_id].name
        self._id2client[tmp_id].state = self._SUCCESS

    def routine(self, tmp_id, content):
        # cur_state: success, to handle chat, history and exit

        tmp_name = self._id2names[tmp_id]
        if content == "help":
            self.send(tmp_id, \
                "Commands:\n\r")
            self.send(tmp_id, \
                "  chat <something> - say something and others can see\n\r")
            self.send(tmp_id, \
                "  history          - check history_info\n\r")
            self.send(tmp_id, \
                "  exit             - exit the game\n\r")
            self.send(tmp_id, \
                "  help             - help lists\n\r")
        elif content == "history":
            self.send(tmp_id, \
                " %s has been online for totally %d seconds, "%
                (tmp_name, self._player_data[tmp_name]["total_time"]) )
            self.send(tmp_id, \
                "last time for %d seconds.\n\r"%
                (self._player_data[tmp_name]["last_time"]))

        elif content == "exit":
            tmp_name = self._id2client[tmp_id].name 
            self.update_data(tmp_id)
            self._id2client[tmp_id].name = None
            self.send(tmp_id, \
                "You have successfully logout.\n\r")
            self.print_wait(tmp_id)
            self._new_todos.append((self._EVENT_PLAYER_OUT, tmp_id, tmp_name))
            self._id2client[tmp_id].state = self._WAIT

        else:
            if not content:
                return
            command, para = (content.split(" ", 1) + ["", ""])[0:2]
            if command == "chat":
                if para == "":
                    self.send(tmp_id, \
                        "chat content can\'t be null.\n\r")
                    return
                for tmp_id in self._id2names.keys():
                    self.send(tmp_id, \
                        "%s says %s\n\r"%(tmp_name, para))
            else:
                self.send(tmp_id, "Invalid command\n\r")

    def announce_out(self, tmp_name):
        for tmp_id in self._id2names.keys():
            self.send(tmp_id, \
                "%s left the game\n\r"%(tmp_name))

    def announce_in(self, tmp_name):
        for tmp_id in self._id2names.keys():
            self.send(tmp_id, \
                "%s enters the game\n\r"%(tmp_name))

class _client(object):
    
    inner_socket = None
    address = ""
    tic = 0
    name = None
    new_name = None
    pw1 = None
    pw2 = None
    login_time = 0
    quit_time = 0
    state = None

    def __init__(self, socket, address, tic, state):
        self.inner_socket = socket
        self.address = address
        self.tic = tic
        self.state = state
        self.name = None
        self.new_name = None
        self.pw1 = None
        self.pw2 = None
        self.login_time = 0
        self.quit_time = 0
    def __str__(self):
        return str(self.name) + ' ' + str(self.state)
