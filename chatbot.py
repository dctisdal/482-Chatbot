import os
import queue
import random
import datetime
import threading

from irc import *
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
        self.timer = 10000000000000 #
        self.timeout = timeout
        self.joined = False
        self.running = False
        self.packet_queue = queue.Queue()
        self.wants_answer = False

        # Connect to server
        self.irc = IRC()
        self.connect(server, channel, nick)

        # Start a thread to listen for packets
        self.packet_thread = threading.Thread(target = self.receive_packet)
        

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
        self.send_message(self.nick, random.choice(responses))
        #self.irc.send(self.channel, None, random.choice(responses))
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
        self.send_message(self.nick, response)
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
        self.send_message(self.nick, response)
        self.state = State.SENT_OUTREACH_TWICE

    def outreach_reply(self):
        # SPEAKING SECOND.
        # Reach this from State START
        response = "outreach reply (You spoke first)"
        #self.irc.send(self.channel, None, response)
        # this None needs to get changed... (AND THE ONES BELOW)
        self.send_message(self.nick, response)
        self.state = State.SENT_OUTREACH_REPLY

    def inquiry(self):
        response = "inquiry (You spoke second)"
        #self.irc.send(self.channel, None, response)
        self.send_message(self.nick, response)
        self.state = State.SENT_INQUIRY

    def inquiry_reply(self):
        response = "inquiry reply (You spoke second)"
        #self.irc.send(self.channel, None, response)
        self.send_message(self.nick, response)
        self.end()

    def inquiry_reinquiry(self):
        response = "inquiry reply + inquiry (You spoke first)"
        #self.irc.send(self.channel, None, response)
        self.send_message(self.nick, response)
        self.state = State.SENT_INQUIRY_REPLY

    def handle_timeout(self):
        # if you stayed slient for `timeout` amount of time
        if self.state == State.START:
            self.initial_outreach()
            self.timer = datetime.datetime.now().timestamp()


        elif self.state == State.SENT_OUTREACH:
            self.secondary_outreach()
            self.timer = datetime.datetime.now().timestamp()

        # giveups
        elif (
            self.state == State.SENT_OUTREACH_TWICE or
            self.state == State.SENT_OUTREACH_REPLY or
            self.state == State.SENT_REPLY
        ):
            self.giveup()
            self.timer = datetime.datetime.now().timestamp()
            

    def receive_packet(self):
        
        # continously receive packets
        while self.running:
            print('getting response from irc')
            self.packet_queue.put(self.irc.get_response())

    def kill_client(self):

        self.running = False

        self.send_message(self.nick, "So long and thanks for all the phish...")

        # kill packet listening thread
        self.packet_thread.join()

        # kill socket
        self.irc.die(self.channel)


    # abstraction of running client.
    # at this point, we already connected.
    def run(self):

        self.running = True
        self.history = []

        # receive packets in a separate thread
        print('beginning to receive packets')
        self.packet_thread.start()

        # lower abstraction of client running
        while self.running:

            # handle timeout outside packet receiver
            try:
                if 1 <= int(datetime.datetime.now().timestamp() - self.timer) <= 1.01:
                    print(datetime.datetime.now().timestamp() - self.timer)

                if datetime.datetime.now().timestamp() - self.timer > self.timeout:
                    self.handle_timeout()

                # if we got a packet, dequeue it
                if not self.packet_queue.empty():
                    text = self.packet_queue.get()
                    print("dequeued a packet", text)


                    # now we need to handle all the packet cases.

                    # bot realizes it has joined
                    if (not self.joined and self.channel in text):
                        self.joined = True
                        self.timer = datetime.datetime.now().timestamp()
                        print("We have joined the channel. Time is", self.timer)
                    

                    # respond to user, if we were prompted by something.
                    if text is not None and self.nick + ":" in text and self.channel in text:
                        print(self.state)

                        # store time of last message.
                        self.timer = datetime.datetime.now().timestamp()

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
                            self.kill_client()

                        elif "name all" == recv_msg:
                            all = self.irc.name_all(self.channel)
                            self.irc.send(self.channel, user, "Here's all of them: " + str(all))

                        else:
                            self.respond(user, recv_msg)

            except KeyboardInterrupt:
                self.kill_client()

            time.sleep(0.0005)

def main():
    bot = ChatBot(timeout=5)
    bot.run()
    pass

if __name__ == "__main__":
    main()