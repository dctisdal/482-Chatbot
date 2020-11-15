import os
import json
import queue
import random
import datetime
import threading

from nlp import *
from irc import *
from nltk import word_tokenize

class State:
    START               = 1 # if we get a message here, we're speaking second
    SENT_OUTREACH       = 2 # if we get a message here, we're speaking first
    SENT_OUTREACH_TWICE = 3 #                  or here
    SENT_OUTREACH_REPLY = 4
    SENT_INQUIRY        = 5
    SENT_INQUIRY_REPLY  = 6

class PacketID:
    NAME_REPLY          = "353"

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
        self.user = None
        self.channel = channel
        self.server = server
        self.state = State.START
        self.sent_history = []
        self.recv_history = []
        self.timer = 10000000000000 #
        self.timeout = timeout
        self.cooldown = 2
        self.joined = False
        self.running = False
        self.wants_answer = None
        
        self.packet_queue = queue.Queue()

        # Connect to server
        self.irc = IRC()
        self.connect(server, channel, nick)

        # Start a daemon thread to listen for packets
        self.packet_thread = threading.Thread(target = self.receive_packet, daemon = True)

        sents = json.load(open("sentiments.json", 'r'))
        self.sentiments = {x: set(sents[x]) for x in sents}
        

    def connect(self, server, channel, nick):
        self.irc.connect(server, channel, nick)

    def respond(self, user, recv_msg):
        if self.state == State.START:
            # We got an outreach from our starting state.
            # We're speaking SECOND.
            self.wants_answer = False
            self.outreach_reply(user)

        elif self.state == State.SENT_OUTREACH or self.state == State.SENT_OUTREACH_TWICE:
            # We sent an outreach, and got a reply back.
            # We're speaking FIRST.
            # handled by the timeout function
            self.inquiry(user)

        elif self.state == State.SENT_INQUIRY:
            # bot sent inquiry, we responded, we inquired
            if self.wants_answer == False:
                self.inquiry_reply(user)
            else:
                self.wants_answer = False

        elif self.state == State.SENT_OUTREACH_REPLY:
            # bot will reply, then inquire
            self.inquiry_reinquiry(user)

        elif self.state == State.SENT_INQUIRY_REPLY:
            self.end()

    def forget(self, user):

        self.sent_history = []
        self.recv_history = []
        self.wants_answer = None
        self.state = State.START
        self.irc.send(self.channel, user, "Forget what? And who are you?")

    def send_message(self, user, msg):
        """
        Send a packet to the IRC server.
        """

        self.irc.send(self.channel, user, msg)
        self.sent_history.append(msg)

    def end(self):
        """
        After we hit end, we force bot to start again.
        Set bot states to default.
        """
        # self.sent_history = []
        # self.recv_history = []
        self.wants_answer = None
        self.state = State.START

    def giveup(self, user):
        responses = [
            "Nevermind, then.",
            "Forget it.",
            "Whatever.",
            "I guess it wasn't important."
        ]
        self.send_message(user, random.choice(responses))
        self.end()

    def initial_outreach(self, user):
        responses = [
            "Hello!",
            "Hi.",
            "Hey there!",
            "Good " + time_of_day() + ".",
            "Good " + time_of_day() + "!"
        ]
        response = random.choice(responses)
        #self.irc.send(self.channel, None, response)
        self.send_message(user, response)
        self.state = State.SENT_OUTREACH

    def secondary_outreach(self, user):
        # > Hello!
        # > Is anyone there?
        responses = [
            "Are you still there?",
            "Is anyone out theeere?"
        ]
        response = random.choice(responses)
        #self.irc.send(self.channel, None, response)
        self.send_message(user, response)
        self.state = State.SENT_OUTREACH_TWICE

    def outreach_reply(self, user):
        # as the bot, we speak second
        # Reach this from State START
        response = ['Hi!', "Howdy!", "Greetings.", "Hello!"]
        if time_of_day() == 'morning':
            response.append("Top of the morning to ya!")
        self.send_message(user, random.choice(response))
        self.state = State.SENT_OUTREACH_REPLY

    def inquiry(self, user):
        response = ["How are you doing?",
                    "How is everything?",
                    "How is your day going?"]
        self.send_message(user, random.choice(response))
        self.state = State.SENT_INQUIRY

    def inquiry_reply(self, user):
        response = inquiry_reply_parser(self.recv_history[-1] + " " + self.recv_history[-2], self.sentiments)
        self.send_message(user, response)
        self.end()

    def inquiry_reinquiry(self, user):
        replies = ['Not bad at all.', "Pretty good.", "Life could be better."]
        inquiries = ['How about you?', "How about yourself?"]
        self.send_message(user, random.choice(replies))
        self.send_message(user, random.choice(inquiries))
        self.state = State.SENT_INQUIRY_REPLY

    def handle_timeout(self, user):
        """
        This function handles state transitions after timeouts.
        """

        # bot becomes first speaker here
        if self.state == State.START:
            self.initial_outreach(user)
            self.timer = datetime.datetime.now().timestamp()
            # awaits one answer in inquiry reply
            self.wants_answer = True

        # if bot already sent an outreach
        elif self.state == State.SENT_OUTREACH:
            self.secondary_outreach(user)
            self.timer = datetime.datetime.now().timestamp()

        # giveups
        # note that our bot can be either 1 or 2. this handles both cases
        elif (
            self.state == State.SENT_OUTREACH_TWICE or  # bot pinged us twice
            self.state == State.SENT_OUTREACH_REPLY or  # bot responded to our first msg
            self.state == State.SENT_INQUIRY        or  # bot, as speaker 1, asked us a question
            self.state == State.SENT_INQUIRY_REPLY      # bot, as speaker 2, asked us a question
        ):
            self.giveup(user)
            self.timer = datetime.datetime.now().timestamp()
            

    def receive_packet(self):
        """
        This function is meant to be called as a thread to recieve packets.
        Necessary because if we try receiving in the main client loop, it hangs as IRC 
        only sends packets upon new text, ping, or file
        """
        while self.running:
            self.packet_queue.put(self.irc.get_response())

    def kill_client(self, user):
        """
        Kill the client and close the socket.
        """

        self.running = False
        self.irc.send(self.channel, user, "So long and thanks for all the phish...")
        self.irc.die(self.channel)

    def handle_packet(self, text):
        """
        Upon receiving a text packet, this function handles how to respond.
        """



        # bot realizes it has joined
        if (not self.joined and self.channel in text):
            self.joined = True
            self.timer = datetime.datetime.now().timestamp()
            return

        # deal with certain packet ID's
        if PacketID.NAME_REPLY in text and self.recv_history:
            text = text.split(':')[2]
            self.send_message(self.user, "Here's all of them: " + str(text))
            return

        # starting up, set user to a random person in the channel
        elif PacketID.NAME_REPLY in text and not self.recv_history:
            # remove self name
            user = text.split(":")[2].strip().split(" ")
            user.remove(self.nick)
            self.user = random.choice(user)
            return

        # if spec asked for other packet id's they'd go here

        # from here on out, all packets are user input cases
        user = text.split(':', 3)[1].split('!')[0]
        self.user = user

        # respond to user, if we were prompted by specific user input
        if text is not None and self.nick + ":" in text and self.channel in text:

            # if there hasn't been 2 seconds before last msg, ignore
            if datetime.datetime.now().timestamp() - self.timer < self.cooldown:
                self.send_message(user, "Give me a moment. I need {} seconds to collect my thoughts.".format(self.cooldown))
            else:
                # store time of last message.
                self.timer = datetime.datetime.now().timestamp()
                self.respond_command(user, text)


    def respond_command(self, user, text):
        """
        Responds to user commands.
        """
        text = text.split(':', 3)
        recv_msg = text[3].lstrip(" ").rstrip("\r\n").lower()
        self.recv_history.append(recv_msg)

        # 3 builtins: forget, die, name all
        # these won't use self.send_message because we don't actually want to log these
        if "forget" == recv_msg:
            self.forget(user)
        elif "die" == recv_msg:
            self.kill_client(user)
            return
        # if we had a lot of commands, we'd take care of them here
        elif "name all" == recv_msg:
            # send names query
            self.irc.name_all(self.channel, user)
            # will be handled downstream by handle_packet
        elif "set timer" in recv_msg:
            new_cooldown = -1
            
            while True:
                try:
                    new_cooldown = float(recv_msg.split()[2].strip())
                    self.send_message(user, "New time between utterances set to {} seconds.".format(new_cooldown))
                    self.cooldown = new_cooldown
                    break
                except ValueError:
                    self.send_message(user, "Valid floats only please. Usage: set timer <float>")
                    break

        else:
            self.respond(user, recv_msg)

    def run(self):
        """
        Abstraction of running client.
        The client already connected to IRC before this.
        """
        self.running = True
        initiate = random.random()

        # receive packets in a separate thread
        self.packet_thread.start()

        while self.running:

            try:

                # the spec said we need to have bot initiate contact sometimes.
                # set it to 20% of the time.
                if initiate <= .2:
                    # pick a random user TODO
                    self.initial_outreach(self.user)
                    initiate = 1

                # handle timeout
                if datetime.datetime.now().timestamp() - self.timer > max(self.timeout, self.cooldown):
                    self.handle_timeout(self.user)

                # if we got a packet, dequeue it
                if not self.packet_queue.empty():
                    text = self.packet_queue.get()

                    # now we need to handle certain events once we see certain packets
                    self.handle_packet(text)

                # Sleeping is fine since packets received are handled by a daemon
                # the client doesn't need to poll for packets
                time.sleep(0.0001)

                # if this was a game, this is where the GUI calls would be

            except KeyboardInterrupt:
                print("Received KeyboardInterrupt. Shutting down...")
                self.kill_client(self.nick)
                return

def main():
    bot = ChatBot(timeout=10)
    bot.run()
    pass

if __name__ == "__main__":
    main()