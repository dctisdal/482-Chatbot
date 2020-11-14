from irc import *
import os
import random

## IRC Config
server = "irc.freenode.net"
channel = "#CPE482"
botnick = "spicyboi-bot"
irc = IRC()
irc.connect(server, channel, botnick)

while True:
    text = irc.get_response()

    if botnick + ":" in text and channel in text:
        text = text.split(':', 3)
        nick = text[1].split('!')[0]
        recv_msg = text[3]

        if "hello" in recv_msg:
            irc.send(channel, nick, "HELLO")