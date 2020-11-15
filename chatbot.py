from irc import *
import os
import random
import datetime
from nltk import word_tokenize

class State:
    START               = 1 # if we get a message here, we're speaking second
    SENT_OUTREACH       = 2 # if we get a message here, we're speaking first
    SENT_OUTREACH_TWICE = 3 #                  or here
    SENT_OUTREACH_REPLY = 4
    SENT_INQUIRY        = 5
    SENT_INQUIRY_REPLY  = 6

def time_of_day():
    hour = datetime.datetime.now().time().hour
    if hour <= 11:
        return "morning"
    if hour <= 17:
        return "afternoon"
    else:
        return "evening"

class ChatBot:
    def __init__(self, server="irc.freenode.net", channel="#CPE482A", nick="spicy-bot", timeout=30):
        self.nick = nick
        self.channel = channel
        self.server = server
        self.state = State.START
        self.sent_history = []
        self.recv_history = []
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
        elif self.state == State.SENT_OUTREACH or self.state == State.SENT_OUTREACH_TWICE:
            # We sent an outreach, and got a reply back.
            # We're speaking FIRST.
            self.inquiry()
        elif self.state == State.SENT_INQUIRY:
            self.inquiry_reply()
        elif self.state == State.SENT_OUTREACH_REPLY:
            self.inquiry_reinquiry()
        elif self.state == State.SENT_INQUIRY_REPLY:
            self.end()

    def forget(self, user):
        self.sent_history = []
        self.recv_history = []
        self.state = State.START
        self.irc.send(self.channel, user, "Forget what? And who are you?")

    def send_message(self, user, msg):
        self.irc.send(self.channel, user, msg)
        self.sent_history.append(msg)

    def end(self):
        time.sleep(1)
        self.history = []
        self.state = State.START

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
        response = random.choice(responses)
        #self.irc.send(self.channel, None, response)
        self.send_message(None, response)
        self.state = State.SENT_OUTREACH

    def secondary_outreach(self):
        # > Hello!
        # > Is anyone there?
        responses = [
            "Are you still there?",
            "Is anyone out theeere?"
        ]
        response = random.choice(responses)
        #self.irc.send(self.channel, None, response)
        self.send_message(None, response)
        self.state = State.SENT_OUTREACH_TWICE

    def outreach_reply(self):
        # SPEAKING SECOND.
        # Reach this from State START
        response = "outreach reply (You spoke first)"
        #self.irc.send(self.channel, None, response)
        # this None needs to get changed... (AND THE ONES BELOW)
        self.send_message(None, response)
        self.state = State.SENT_OUTREACH_REPLY

    def inquiry(self):
        response = "inquiry (You spoke second)"
        #self.irc.send(self.channel, None, response)
        self.send_message(None, response)
        self.state = State.SENT_INQUIRY

    def inquiry_reply(self):
        response = "inquiry reply (You spoke second)"
        #self.irc.send(self.channel, None, response)
        self.send_message(None, response)
        self.end()

    def inquiry_reinquiry(self):
        response = "inquiry reply + inquiry (You spoke first)"
        #self.irc.send(self.channel, None, response)
        self.send_message(None, response)
        self.state = State.SENT_INQUIRY_REPLY

    def handle_timeout(self):
        if self.state == State.START:
            self.initial_outreach()
        elif self.state == State.SENT_OUTREACH:
            self.secondary_outreach()
        # giveups
        elif (
            self.state == State.SENT_OUTREACH_TWICE or
            self.state == State.SENT_OUTREACH_REPLY or
            self.state == State.SENT_REPLY
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
                self.recv_history.append(recv_msg)
                print("Received:", recv_msg)

                # 3 builtins: forget, die, name all
                # these won't use self.send_message because we don't actually want to log these
                if "forget" == recv_msg:
                    self.forget(user)
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
    bot = ChatBot(timeout=8)
    bot.run()
    pass

if __name__ == "__main__":
    main()