from irc import *
import os
import random
from nltk import word_tokenize

class Phase:
    START               = 1
    INITIAL_OUTREACH    = 2
    SECONDARY_OUTREACH  = 3
    GIVEUP_FRUSTRATED   = 4
    INQUIRY             = 5
    INQUIRY_REPLY       = 6
    OUTREACH_REPLY      = 7
    INQUIRY_2           = 8
    GIVEUP_FRUSTRATED_2 = 9
    INQUIRY_REPLY       = 10
    END                 = 11

class ChatBot:
    def __init__(self, server="irc.freenode.net", channel="#CPE482A", nick="nlp-bot"):
        self.nick = nick
        self.channel = channel
        self.server = server
        self.phase = Phase.START
        self.irc = IRC()
        self.connect(server, channel, nick)

    def connect(self, server, channel, nick):
        self.irc.connect(server, channel, nick)

    def run(self):
        all_msg = []
        while True:
            text = self.irc.get_response()

            if self.nick + ":" in text and self.channel in text:
                text = text.split(':', 3)
                nick = text[1].split('!')[0]
                recv_msg = text[3].lstrip(" ").rstrip("\r\n")
                all_msg.append(word_tokenize(recv_msg))
                print(recv_msg)

                if "hello" in recv_msg:
                    self.irc.send(self.channel, nick, "Hello right back at you " + nick)

                if "forget" == recv_msg:
                    all_msg = []
                    self.irc.send(self.channel, nick, "Forget what? And who are you?")

                if "die" == recv_msg:
                    self.irc.send(self.channel, nick, "So long and thanks for all the phish...")
                    self.irc.die(self.channel)
                    return

                if "name all" == recv_msg:
                    all = self.irc.name_all(self.channel)
                    self.irc.send(self.channel, nick, "Here's all of them: " + str(all))

def main():
    bot = ChatBot()
    bot.run()



if __name__ == "__main__":
    main()