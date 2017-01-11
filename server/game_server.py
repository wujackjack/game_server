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
    _name2id = {}
    _id2client = {}
    _id_states = {}
    _player_data = {}
    _room_info = {}
    _curid = 0
    _todos = []
    _new_todos = []
    _state2func = {}
    _command2func = {}


    _WAIT = 0
    _WAIT_SIGNIN = 1 # wait_signin -> success 
    _SUCCESS = 3
    _WAIT_SIGNUP = 4 # wait_signup -> success
    _EVENT_NEW_CLIENT = 7
    _EVENT_INFO = 8
    _EVENT_PLAYER_OUT = 9

    def __init__(self, host="0.0.0.0", port=23, timeout=2):
        self._curid = 0

        self.load_data()
        self._room_info["lobby"] = {}
        self._state2func = self.func_init()
        self._command2func = self.command_init()
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
        state2func[self._SUCCESS] = self.routine
        return state2func

    def command_init(self):
        command2func = {}
        command2func["help"] = self.help
        command2func["exit"] = self.exitt
        command2func["history"] = self.history
        command2func["leave"] = self.leave
        command2func["list"] = self.listt
        command2func["enter"] = self.enter
        command2func["create"] = self.create
        command2func["chat"] = self.chat
        command2func["chatroom"] = self.chatroom
        command2func["chatall"] = self.chatall
        return command2func

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
            tmp_name = self._id2client[tmp_id].name
            room_name = self._id2client[tmp_id].room 
            if room_name != None:
                del(self._room_info[room_name][tmp_id])
                self._id2client[tmp_id].room = None
            # self._id2client[tmp_id].quit_time = time.time()
            last_time = time.time() - self._id2client[tmp_id].login_time
            self._player_data[self._id2client[tmp_id].name]["last_time"] = \
                last_time
            self._player_data[self._id2client[tmp_id].name]["total_time"] += \
                last_time

            self.update_file()
            del(self._name2id[tmp_name])
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
            self.send(tmp_id, 'Signin Name: \n\r')

        # choose to signin
        elif content == "signup":
            self._id2client[tmp_id].state = self._WAIT_SIGNUP
            self.send(tmp_id, \
                'Please enter new user name.\n\r')
            self.send(tmp_id, 'Signup Name: \n\r')

        # invalid command
        elif content:
            self.send(tmp_id, "Invalid command\n")
            self.print_wait(tmp_id)
   
    def wait_signin(self, tmp_id, content):
        # prev_state: wait
        # cur_state: wait_signin
        # next_state: success

        name, pw = (content.split("\t", 1) + ["", ""])[0:2]
        if name not in self._player_data:
            self.send(tmp_id, \
                'Username does not exist in database.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        if name in self._name2id:
            self.send(tmp_id, \
                'User has login on other client.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        self._id2client[tmp_id].name = name
        if self._player_data[self._id2client[tmp_id].name]["pw"] != \
                pw:
            self.send(tmp_id, \
                'Wrong password. Please re-login or create new account\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None

        self.send(tmp_id, \
            'You have successfully login. You are in game lobby.\n\r')
        self.send(tmp_id, \
            'Type "help" to see command lists\n\r')
        self._id2client[tmp_id].room = "lobby"
        self.announce_in(self._id2client[tmp_id].name)
        self._id2client[tmp_id].login_time = time.time()
        self._id2names[tmp_id] = self._id2client[tmp_id].name
        self._name2id[name] = tmp_id
        self._room_info["lobby"][tmp_id] = name
        self._id2client[tmp_id].state = self._SUCCESS

    def wait_signup(self, tmp_id, content):
        # prev_state: wait
        # cur_state: wait_signup
        # next_state: success

        name, pw1, pw2 = (content.split("\t", 2) + ["", "", ""])[0:3]
        if name in self._player_data:
            self.send(tmp_id, \
                'Username already exists in database.\n\r')
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return None
        self._id2client[tmp_id].new_name = name
        if pw1 != pw2:
            self.send(tmp_id, 'Password aren\'t consistent.\n\r')
            self._id2client[tmp_id].new_name = None 
            self._id2client[tmp_id].pw1 = None 
            self.print_wait(tmp_id)
            self._id2client[tmp_id].state = self._WAIT
            return 
        new_player = {"total_time" : 0, \
                      "pw" : pw1, \
                      "last_time" : 0}
        self._id2client[tmp_id].room = "lobby" 
        self._player_data[self._id2client[tmp_id].new_name] = new_player
        self.update_file()
        self._id2client[tmp_id].name = self._id2client[tmp_id].new_name
        self.send(tmp_id, \
            'You have successfully created an account and login. \
            You are in game lobby.\n\r')
        self.send(tmp_id, \
            'Type "help" to see command lists\n\r')
        self.announce_in(self._id2client[tmp_id].name)
        self._id2client[tmp_id].login_time = time.time()
        self._id2names[tmp_id] = self._id2client[tmp_id].name
        self._name2id[name] = tmp_id
        self._room_info["lobby"][tmp_id] = name
        self._id2client[tmp_id].state = self._SUCCESS    
   
    def help(self, tmp_id, para):
        # print help information
        self.send(tmp_id, \
            "Commands:\n\r")
        self.send(tmp_id, \
            "  chatall <something> - say something and everyone can see\n\r")
        self.send(tmp_id, \
            "  chatroom <something> - say something and player in the same room can see\n\r")
        self.send(tmp_id, \
            "  chat <playername> <something> - say something to a certain player if he/she is online\n\r")
        self.send(tmp_id, \
            "  create <roomname> - create a new room\n\r")
        self.send(tmp_id, \
            "  enter <roomname> - enter a room\n\r")
        self.send(tmp_id, \
            "  leave - leave a room\n\r")   
        self.send(tmp_id, \
            "  list - list all the rooms and show corresponding playername\n\r")
        self.send(tmp_id, \
            "  history - check history_info\n\r")
        self.send(tmp_id, \
            "  exit - exit the game\n\r")
        self.send(tmp_id, \
            "  help - help lists\n\r")

    def chatall(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        if para == "":
            self.send(tmp_id, \
                "chat content can not be null.\n\r")
            return
        for tmp_id in self._id2names.keys():
            self.send(tmp_id, \
                "To everyone, %s says %s\n\r"%(tmp_name, para))
        return

    def chatroom(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        room_name = self._id2client[tmp_id].room 
        if room_name == "lobby":
            self.send(tmp_id, "You are currently not in a room.\n\r")
            return
        if para == "":
            self.send(tmp_id, \
                "chat content can not be null.\n\r")
            return
        for tmp_id in self._room_info[room_name].keys():
            self.send(tmp_id, \
                "In room %s, %s says %s.\n\r"%(room_name, tmp_name, para))
        return 

    def chat(self, tmp_id, para):
        to_player_name, content = (para.split(" ", 1) + ["", ""])[0:2]
        tmp_name = self._id2client[tmp_id].name 
        if to_player_name not in self._name2id:
            self.send(tmp_id, \
                "Player %s is not online or does not exists.\n\r"%(to_player_name))
            return
        if content == "":
            self.send(tmp_id, \
                "chat content can not be null.\n\r")
            return
        to_id = self._name2id[to_player_name]
        self.send(to_id, \
                "Privately to you, %s says %s\n\r"%(tmp_name, content))
        return

    def listt(self, tmp_id, para):
        v = self._room_info["lobby"]
        if len(v):
            self.send(tmp_id, "Player in %s: \n\r"%("lobby"))
            for user_name in v.values():
                self.send(tmp_id, "\t%s\n\r"%(user_name))
        else:
            self.send(tmp_id, "No player in %s.\n\r"%("lobby"))

        for k, v in self._room_info.items():
            if k != "lobby":
                if len(v):
                    self.send(tmp_id, "Player in room %s: \n\r"%(k))
                    for user_name in v.values():
                        self.send(tmp_id, "\t%s\n\r"%(user_name))
                else:
                    self.send(tmp_id, "No player in room %s.\n\r"%(k))
        return

    def create(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        room_name = self._id2client[tmp_id].room 
        if room_name != "lobby":
            self.send(tmp_id, \
                "You are currently in room %s, can not create a new room. Please leave first.\n\r"%(room_name))
            return
        if para in self._room_info:
            self.send(tmp_id, \
                "Room %s already exists, can not re-create.\n\r"%(para))
            return
        tmp_dic = {}
        tmp_dic[tmp_id] = tmp_name
        del(self._room_info["lobby"][tmp_id]) 
        self._room_info[para] = tmp_dic
        self._id2client[tmp_id].room = para
        self.send(tmp_id, \
            "You have successfully created room %s and entered it.\n\r"%(para))
        return

    def enter(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        room_name = self._id2client[tmp_id].room 
        if room_name != "lobby":
            self.send(tmp_id, \
                "You are currently in room %s, please leave first.\n\r"%(room_name))
            return
        if para == "lobby":
            self.send(tmp_id, \
                "You are currently in lobby.\n\r")
            return
        if para not in self._room_info:
            self. send(tmp_id, \
                "Room %s does not exist, please create first.\n\r"%(para))
            return
        self.announce_room_in(para, tmp_name)
        self._id2client[tmp_id].room = para
        self.send(tmp_id, \
            "You enter room %s.\n\r"%(para))
        del(self._room_info["lobby"][tmp_id]) 
        self._room_info[para][tmp_id] = tmp_name
        return

    def leave(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        room_name = self._id2client[tmp_id].room 
        if room_name == "lobby":
            self.send(tmp_id, "You are currently not in a room\n\r")
            return
        del(self._room_info[room_name][tmp_id])
        self._room_info["lobby"][tmp_id] = tmp_name
        self.announce_room_out(room_name, tmp_name)
        self._id2client[tmp_id].room = "lobby"
        self.send(tmp_id, \
            "You left room %s and you are now in game lobby\n\r"%(room_name))
        return

    def exitt(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        self.update_data(tmp_id)
        self._id2client[tmp_id].name = None
        self.send(tmp_id, \
            "You have successfully logout.\n\r")
        self.print_wait(tmp_id)
        self._new_todos.append((self._EVENT_PLAYER_OUT, tmp_id, tmp_name))
        self._id2client[tmp_id].state = self._WAIT
        return

    def history(self, tmp_id, para):
        tmp_name = self._id2client[tmp_id].name 
        self.send(tmp_id, \
            " %s has been online for totally %d seconds, "%
            (tmp_name, self._player_data[tmp_name]["total_time"]) )
        self.send(tmp_id, \
            "last time for %d seconds.\n\r"%
            (self._player_data[tmp_name]["last_time"]))


    def routine(self, tmp_id, content):
        # cur_state: success, to handle chat, history and exit

        tmp_name = self._id2names[tmp_id]
        command, para = (content.split(' ', 1) + ["", ""])[0:2]


        if command in self._command2func:
            self._command2func[command](tmp_id, para)
        else:
            self.send(tmp_id, "Invalid command\n\r")

    def announce_out(self, tmp_name):
        for tmp_id in self._id2names.keys():
            self.send(tmp_id, \
                "%s left the game.\n\r"%(tmp_name))

    def announce_room_in(self, room_name, tmp_name):
        for tmp_id in self._room_info[room_name].keys():
            self.send(tmp_id, \
                "%s enter room %s.\n\r"%(tmp_name, room_name))

    def announce_room_out(self, room_name, tmp_name):
        for tmp_id in self._room_info[room_name].keys():
            self.send(tmp_id, \
                "%s left room %s.\n\r"%(tmp_name, room_name))

    def announce_in(self, tmp_name):
        for tmp_id in self._id2names.keys():
            self.send(tmp_id, \
                "%s enters the game lobby\n\r"%(tmp_name))

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
    room = None

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
        self.room = None
    def __str__(self):
        return str(self.name) + ' ' + str(self.state)
