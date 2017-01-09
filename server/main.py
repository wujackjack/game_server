'''
Main.py for running game server
Author: Zhongjun Wu
Email: wuzhongjun1992@126.com
'''

import time
from game_server import Server

if __name__ == "__main__":
    ms = Server()
  #  print ms._player_data
    try:
        while True:
            time.sleep(0.2)
            ms.run()
    
            # go through new players
            for tmp_id in ms.get_new_players():
                ms.send(tmp_id, \
                    'Type "signin" to login or "signup" to create an account\n\r')
    
            # go through disconnected players
            for tmp_id, tmp_name in ms.get_disconnection():
                ms.announce_out(tmp_name)
    
            # go through any commands
            for tmp_id, content in ms.get_commands():
                ms._state2func[ms._id2client[tmp_id].state](tmp_id, content)
    except Exception:
        print "server_close"
        ms.server_close()

    except KeyboardInterrupt:
        print "server_close"
        ms.server_close()

