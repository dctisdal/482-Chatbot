from irc import *
import os
import random
import datetime
from nltk import word_tokenize

class Phase:
    START                = 1
    INITIAL_OUTREACH_1   = 2
    SECONDARY_OUTREACH_1 = 3
    GIVEUP_FRUSTRATED    = 4
    INQUIRY_1            = 5
    INQUIRY_REPLY_1      = 6
    OUTREACH_REPLY_2     = 7
    INQUIRY_2            = 8
    INQUIRY_REPLY_2      = 10
    END                  = 11


def time_of_day():
    hour = datetime.datetime.now().time().hour
    if hour <= 11:
        return "morning"
    if hour <= 17:
        return "afternoon"
    else:
        return "evening"


class ChatBot:
    def __init__(self, server="irc.freenode.net", channel="#CPE482", nick="spicy-bot", timeout=5):
        self.nick = nick
        self.channel = channel
        self.server = server
        self.phase = Phase.START
        self.all_msg = []
        self.irc = IRC(timeout=timeout)
        self.connect(server, channel, nick)

    def connect(self, server, channel, nick):
        self.irc.connect(server, channel, nick)

    def respond(self, user, recv_msg):
        if "hello" in recv_msg:
            self.irc.send(self.channel, user, "Hello right back at you " + user)

    def end(self):
        time.sleep(5)
        self.phase = Phase.START

    def giveup(self):
        responses = [
            "Nevermind, then.",
            "Forget it.",
            "Whatever.",
            "I guess it wasn't important."
        ]

        self.irc.send(self.channel, None, random.choice(responses))
        self.phase = Phase.END
        self.end()

    def initial_outreach(self):
        responses = [
            "Hello!",
            "Hi.",
            "Hey there!",
            "Good " + time_of_day() + ".",
            "Good " + time_of_day() + "!"
        ]
        self.irc.send(self.channel, None, random.choice(responses))


    def handle_timeout(self):
        if self.phase == Phase.START:
            #self.phase = Phase.INITIAL_OUTREACH_1
            self.initial_outreach()
        elif self.phase == Phase.INITIAL_OUTREACH_1:
            self.phase = Phase.SECONDARY_OUTREACH_1
        # giveups
        elif (
            self.phase == Phase.SECONDARY_OUTREACH_1 or
            self.phase == Phase.OUTREACH_REPLY_2 or
            self.phase == Phase.INQUIRY_1 or
            self.phase == Phase.INQUIRY_2
        ):
            self.phase = Phase.GIVEUP_FRUSTRATED
            self.giveup()
            

    def get_response_timeout(self):
        try:
            return self.irc.get_response()
        except socket.timeout:
            self.handle_timeout()

    def run(self):
        self.all_msg = []
        while True:
            text = self.get_response_timeout()

            # respond to user, if we were prompted by something.
            if text is not None and self.nick + ":" in text and self.channel in text:
                text = text.split(':', 3)
                user = text[1].split('!')[0]
                recv_msg = text[3].lstrip(" ").rstrip("\r\n")
                self.all_msg.append(word_tokenize(recv_msg))
                print(recv_msg)

                # 3 builtins: forget, die, name all
                if "forget" == recv_msg:
                    responses = []
                    self.all_msg = []
                    self.irc.send(self.channel, user, "Forget what? And who are you?")
                elif "die" == recv_msg:
                    self.irc.send(self.channel, user, "So long and thanks for all the phish...")
                    self.irc.die(self.channel)
                    return
                elif "name all" == recv_msg:
                    all = self.irc.name_all(self.channel)
                    self.irc.send(self.channel, user, "Here's all of them: " + str(all))
                else:
                    self.respond(user, recv_msg)

def main():
    bot = ChatBot()
    bot.run()
    pass



if __name__ == "__main__":
    main()