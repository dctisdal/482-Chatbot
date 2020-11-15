from irc import *
import os
import random
import datetime
from nltk import word_tokenize

class State:
    START               = 1
    SENT_OUTREACH       = 2
    SENT_OUTREACH_TWICE = 3
    SENT_OUTREACH_REPLY = 4
    SENT_REPLY          = 5

def time_of_day():
    hour = datetime.datetime.now().time().hour
    if hour <= 11:
        return "morning"
    if hour <= 17:
        return "afternoon"
    else:
        return "evening"

class ChatBot:
    def __init__(self, server="irc.freenode.net", channel="#CPE482A", nick="spicy-bot", timeout=5):
        self.nick = nick
        self.channel = channel
        self.server = server
        state = State.START
        self.history = []
        self.wants_answer = False
        self.irc = IRC(timeout=timeout)
        self.connect(server, channel, nick)

    def connect(self, server, channel, nick):
        self.irc.connect(server, channel, nick)

    def respond(self, user, recv_msg):
        if self.state == State.START:
            # We got an outreach from our starting state.
            # We're speaking SECOND.
            self.outreach_reply()
        elif self.state == State.SENT_OUTREACH or state == State.SENT_OUTREACH_TWICE:
            # We sent an outreach, and got a reply back.
            # We're speaking FIRST.
            self.first_reply()
        elif self.state == State.SENT_REPLY:
            self.second_reply()

    def end(self):
        time.sleep(5)
        self.history = []
        state = State.START

    def giveup(self):
        responses = [
            "Nevermind, then.",
            "Forget it.",
            "Whatever.",
            "I guess it wasn't important."
        ]

        self.irc.send(self.channel, None, random.choice(responses))
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
        state = State.SENT_OUTREACH

    def secondary_outreach(self):
        # > Hello!
        # > Is anyone there?
        responses = [
            "Are you still there?",
            "Is anyone out theeere?"
        ]
        self.irc.send(self.channel, None, random.choice(responses))
        state = State.SENT_OUTREACH_TWICE

    def outreach_reply(self):
        # SPEAKING SECOND.
        # Reach this from State START
        state = State.SENT_OUTREACH_REPLY

    def first_reply(self):

        state = State.SENT_REPLY

    def second_reply(self):

        self.end()

    def handle_timeout(self):
        if state == State.START:
            self.initial_outreach()
        elif state == State.SENT_OUTREACH:
            self.secondary_outreach()
        # giveups
        elif (
            state == State.SENT_OUTREACH_TWICE or
            state == State.SENT_OUTREACH_REPLY or
            state == State.SENT_REPLY
        ):
            self.giveup()
            

    def get_response_timeout(self):
        try:
            return self.irc.get_response()
        except socket.timeout:
            self.handle_timeout()

    def run(self):
        self.history = []
        while True:
            text = self.get_response_timeout()

            # respond to user, if we were prompted by something.
            if text is not None and self.nick + ":" in text and self.channel in text:
                text = text.split(':', 3)
                user = text[1].split('!')[0]
                recv_msg = text[3].lstrip(" ").rstrip("\r\n")
                self.history.append(word_tokenize(recv_msg))
                print(recv_msg)

                # 3 builtins: forget, die, name all
                if "forget" == recv_msg:
                    responses = []
                    self.history = []
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
    #bot = ChatBot()
    #bot.run()
    pass



if __name__ == "__main__":
    main()