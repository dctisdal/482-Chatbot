from irc import *
import os
import random
from nltk import word_tokenize

## IRC Config
server = "irc.freenode.net"
channel = "#CPE482"
botnick = "spicy-bot"
irc = IRC()
irc.connect(server, channel, botnick)


def main():
    all_msg = []
    while True:
        text = irc.get_response()

        if botnick + ":" in text and channel in text:
            text = text.split(':', 3)
            nick = text[1].split('!')[0]
            recv_msg = text[3].lstrip(" ").rstrip("\r\n")
            all_msg.append(word_tokenize(recv_msg))
            print(recv_msg)

            if "hello" in recv_msg:
                irc.send(channel, nick, "Hello right back at you " + nick)

            if "forget" == recv_msg:
                all_msg = []
                irc.send(channel, nick, "Forget what? And who are you?")

            if "die" == recv_msg:
                irc.send(channel, nick, "So long and thanks for all the phish...")
                irc.die(channel)
                return

            if "name all" == recv_msg:
                all = irc.name_all(channel)
                irc.send(channel, nick, "Here's all of them: " + str(all))






if __name__ == "__main__":
    main()