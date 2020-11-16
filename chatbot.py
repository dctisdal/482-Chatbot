import os
import json
import time
import queue
import random
import datetime
import threading

from nlp import *
from irc import *
from lyrics import *
from requests import get
from nltk import word_tokenize, sent_tokenize

class State:
    START               = 1 # if we get a message here, we're speaking second
    SENT_OUTREACH       = 2 # if we get a message here, we're speaking first
    SENT_OUTREACH_TWICE = 3 #                  or here
    SENT_OUTREACH_REPLY = 4
    SENT_INQUIRY        = 5
    SENT_INQUIRY_REPLY  = 6
    SENT_NAME_REQUEST   = 7 # optional feature

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
    def __init__(self, server="irc.freenode.net", channel="#CPE482", nick="spicy-bot", timeout=30):
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
        self.last_msg_time = 0

        self.sa = SentimentAnalyzer()
        
        self.packet_queue = queue.Queue()

        # extra features?
        self.names = dict()

        # Connect to server
        self.irc = IRC()
        self.connect(server, channel, nick)

        # Start a daemon thread to listen for packets
        self.packet_thread = threading.Thread(target = self.receive_packet, daemon = True)

    def connect(self, server, channel, nick):
        self.irc.connect(server, channel, nick)

    def check_preposition(self, text):
        if text in ['to', 'for']:
            return True

    def inquiry_reinquiry_lyric(self, user, recv_msg):
        """message is like Can i get lyrics to ___ by ___"""
        remove_these = ["to the song", "the song", ' song']

        # remove the song phrase 
        try:
            for i in remove_these:
                recv_msg = re.sub(i, "", recv_msg)
        except TypeError:
            self.send_message(user, "Make sure your query includes the phrase 'lyrics to <song_name> by <song_author>.'")
            self.recv_history = self.recv_history[:-1]
            return

        # split on lyrics, right hand should be song name
        recv_msg = recv_msg.lower().split("lyrics")[1].strip().split()
        # remove the preposition
        if self.check_preposition(recv_msg[0]):
            recv_msg = recv_msg[1:]

        print("lyrics msg: ", recv_msg)

        lyric_link, lyrics = get_lyrics(" ".join(recv_msg))
        if lyric_link == "":
            self.send_message(user, "Unfortunately, I could not find the song you requested. Ask me again!")
            self.send_message(user, "Make sure your query includes the phrase 'lyrics to <song_name> by <song_author>.'")
            self.recv_history = self.recv_history[:-1]
            return
        # the good case
        else:
            response = "Sure, I'll find those lyrics for you."
            self.send_message(user, response)
            lyrics = lyrics.split('\n')
            self.send_message(user, "Here are the first fifteen lines.")
            time.sleep(0.5)
            self.send_message(user, " | ".join(lyrics[:15]) + ".....")
            time.sleep(0.5)
            self.send_message(user, "You can find the rest of the lyrics at {}. Is this what you were looking for?".format("https://genius.com" + lyric_link))

        self.state = State.SENT_INQUIRY_REPLY

    def inquiry_reinquiry_time(self, user, recv_msg):
        """message format: ___ time I/you said ____"""

        try:
            # find subject
            time_msg = recv_msg.rstrip("?")
            time_msg = time_msg.split("time")[1]
            time_msg_list = time_msg.split("said")
            subject = time_msg_list[0].strip(" ").lower()
            p = time_msg_list[1].strip(" ")
            found = False

            print("time msg: {} | subject: {} | phrase: {}".format(time_msg, subject, p))
            if subject == "i":
                for phrase, timestamp in self.recv_history[:-1]:
                    if p in phrase:
                        readable = time.ctime(timestamp)
                        time.sleep(0.5)
                        self.send_message(user, 'I remember you said "{}" on {}'.format(p, readable))
                        self.send_message(user, "Was this the one you were thinking of, or another time?")
                        found = True
                        break
                if not found:
                    #time.sleep(0.5)
                    self.send_message(user, 'Sorry, but I do not have any record of you saying "{}"'.format(p))
                    self.send_message(user, "Was there something else?")

            elif subject == "you":
                for phrase, timestamp in self.sent_history:
                    if p in phrase:
                        readable = time.ctime(timestamp)
                        time.sleep(0.5)
                        self.send_message(user, 'I remember I said "{}" on {}'.format(p, readable))
                        self.send_message(user, "Was that what you were thinking of?")
                        found = True
                        break
                if not found:
                    time.sleep(0.5)
                    self.send_message(user, 'Sorry, but I do not have any record of me saying "{}"'.format(p))
                    self.send_message(user, "Was there something else?")
            else:
                raise ValueError
        except:
            self.send_message(user, "Please use the format: time <I/you> said <phrase>")
            return
        self.send_message(user, "Anyways, how were you doing to day?")
        self.state = State.SENT_INQUIRY_REPLY

    def respond(self, user, recv_msg):
        if self.state == State.START:
            # We got an outreach from our starting state.
            # We're speaking SECOND.
            self.wants_answer = False
            self.outreach_reply(user, recv_msg)

        elif self.state == State.SENT_OUTREACH or self.state == State.SENT_OUTREACH_TWICE:
            # We sent an outreach, and got a reply back.
            # We're speaking FIRST.
            # handled by the timeout function
            if random.randint(0, 1) == 1 or user in self.names.keys():
                self.inquiry(user, recv_msg)
            else:
                self.ask_name(user, recv_msg)
        
        elif self.state == State.SENT_NAME_REQUEST:
            self.name_reply(user, recv_msg)

        elif self.state == State.SENT_INQUIRY:
            # bot sent inquiry, we responded, we inquired
            if self.wants_answer == False:
                self.inquiry_reply(user, recv_msg)
            else:
                parsed = self.analyze(recv_msg)
                self.wants_answer = False
                # to deal with one-sentence replies
                if parsed is not None and parsed["is_question"] and "," in parsed["words"]:
                    # pad so we don't consider an extra sentence in sentiment analysis
                    self.recv_history.append("")
                    self.inquiry_reply(user, recv_msg)

        elif self.state == State.SENT_OUTREACH_REPLY:
            # bot will reply, then inquire
            if "lyric" in recv_msg and "to" in recv_msg and "by" in recv_msg:
                self.inquiry_reinquiry_lyric(user, recv_msg)
            elif "time" in recv_msg and "said" in recv_msg:
                self.inquiry_reinquiry_time(user, recv_msg)
            else:
                self.inquiry_reinquiry(user, recv_msg)

        elif self.state == State.SENT_INQUIRY_REPLY:
            self.end(user)

    def forget(self, user):
        self.sent_history = []
        self.recv_history = []
        self.wants_answer = None
        self.state = State.START
        self.irc.send(self.channel, user, "Forget what? And who are you?")
        self.user = None
        self.names = dict()

    def analyze(self, msg):
        # for now, we just look at the last sentence, which is most likely to be talking to the bot
        # this COULD change, though.
        try:
            sent = sent_tokenize(msg)[-1].lower()
            words = word_tokenize(sent)
            sentiment = self.sa.sentiment(sent)
            return {"sentence": sent, "words": words, "is_question": words[-1] == "?", "all_sents": sent_tokenize(msg), "sentiment": sentiment}
        except IndexError:
            return None

    def send_message(self, user, msg):
        """
        Send a packet to the IRC server.
        """
        if "-bot: die" in msg.lower():
            # Asimov, I.
            return

        if datetime.datetime.now().timestamp() - self.last_msg_time < self.cooldown:
            time.sleep(self.cooldown)

        self.last_msg_time = datetime.datetime.now().timestamp()
        self.irc.send(self.channel, user, msg)
        self.sent_history.append((msg, datetime.datetime.now().timestamp()))

    def end(self, user):
        """
        After we hit end, we force bot to start again.
        Set bot states to default.
        """
        # self.sent_history = []
        # self.recv_history = []
        self.send_message(user, "See you later.")
        self.user = None
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
        self.end(user)

    def initial_outreach(self, user):
        responses = [
            "Hello",
            "Hi",
            "Hey there",
            "Good " + time_of_day()
        ]
        response = random.choice(responses) + random.choice([".", "!"])
        self.send_message(user, response)
        self.state = State.SENT_OUTREACH

    def secondary_outreach(self, user):
        # > Hello!
        # > Is anyone there?
        responses = [
            "Are you still there?",
            "Is anyone out there?",
            "I know you're out there!",
            "Anyone?",
            "Hellooooooo!",
            "You know, I can see the member list. Talk to me!"
        ]
        response = random.choice(responses)
        self.send_message(user, response)
        self.state = State.SENT_OUTREACH_TWICE

    def outreach_reply(self, user, recv_msg):
        # as the bot, we speak second
        # Reach this from State START
        responses = [
            'Hi',
            "Howdy",
            "Greetings",
            "Hello"
        ]

        respond_to = set([
            "hi", "hello", "good morning", "good afternoon", "good evening",
            "what's up", "hey", "greeting", "sup", "yo", "hai"
        ])

        parsed = self.analyze(recv_msg)

        if parsed is None or len(respond_to.intersection(set(parsed["words"]))) == 0:
            self.send_message(user, "Not sure I understand that; maybe it's a dialect thing. Could you try again?")
            self.recv_history = self.recv_history[:-1]
            return

        initial_responses = list(responses)
        for resp in initial_responses:
            if resp.lower() in parsed["words"]:
                responses.append(resp.lower() + " back to you")

        if time_of_day() == 'morning':
            responses.append("Top of the morning to ya")

        if random.randint(0, 1) == 0:
            # 1/2 chance of being completely random
            response = random.choice(responses)
        else:
            # 1/2 chance of being whatever is the most similar via a naive metric
            response = max(responses, key=lambda r: word_overlap(r, recv_msg))

        ### optional
        # this right here will trigger a bug, patched it. modules would be ideal here as functions are running into each other
        name = None
        print(user, self.names)
        if user not in self.names:
            name = self.parse_name(recv_msg, assume_one_word_is_name=False)
        if name is not None:
            self.names[user] = name
            response += ", {}".format(name)
        ### end optional

        response +=  random.choice([".", "!"])

        self.send_message(user, response)
        self.state = State.SENT_OUTREACH_REPLY

    ### optional feature: name use ###
    def parse_name(self, recv_msg, assume_one_word_is_name=False):
        intros = [
            "name is",
            "name's",
            "i am",
            "i'm"
        ]
        parsed = self.analyze(recv_msg)
        if parsed is None:
            return None

        name = None

        # bug, saves name when you enter one word
        if len(parsed["words"]) == 1 and assume_one_word_is_name:
            name = parsed["words"][0].capitalize()
        else:
            lowered = recv_msg.lower()
            print(lowered)
            for intro in intros:
                if intro in lowered:
                    split = lowered.split(intro, 2)[1]
                    toked = word_tokenize(split)
                    name = toked[0].capitalize()
        return name

    def ask_name(self, user, recv_msg):
        responses = [
            "Hi! What's your name?",
            "What's your name, stranger?",
            "How are you, uh... what's your name, again?",
            "Hi, uhh... could you tell me your name, please?"
        ]
        response = random.choice(responses)
        self.send_message(user, response)
        self.state = State.SENT_NAME_REQUEST

    def name_reply(self, user, recv_msg):
        # this needs to parse and add it...
        name = self.parse_name(recv_msg, assume_one_word_is_name=True)

        if name == None:
            self.send_message(user, "I didn't understand that. Could you try responding in a simpler way?")
            self.recv_history = self.recv_history[:-1]
            return

        responses = [
            "Nice to meet you, {}!",
            "A pleasure to make your acquaintance, {}!"
        ]
        self.names[user] = name
        response = random.choice(responses).format(name)
        self.send_message(user, response)
        # this may need to be a diff message...
        self.inquiry(user, recv_msg)
    ### end optional feature part  ###

    def inquiry(self, user, recv_msg):
        responses = ["How are you doing{}?",
                    "How is everything{}?",
                    "How is your day going{}?",
                    "How are things{}?"]
        name = ""
        if user in self.names.keys():
            name = ", " + self.names[user]

        response = random.choice(responses).format(name)
        self.send_message(user, response)
        self.state = State.SENT_INQUIRY

    def get_loc_weather(self):
        info = get("https://geolocation-db.com/json/{}&position=true".format(None)).json()
        forecast = get('http://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid=b4a2c2b82fad9f62191b9237ea6a07e7'.format(info['latitude'],
                                                                                                       info['longitude'])).json()
        weather = forecast['weather'][0]['main'].lower()
        if weather == "thunderstorm":
            weather = weather + 's'
        elif weather == "clear":
            weather = "clear skies"
        return info['state'], weather

    def generate_reply(self):
        negative_responses = ["Hopefully things get better for you.", "Sorry to hear about that.", 
                            "I hope your situation will improve soon."]
        positive_responses = ["I'm glad you're doing well!", 
                                "Awesome!",
                                "Wow! Glad to hear :)"]
        neutral_responses = ["I am doing fine.", 
                                "Pretty good for me."]
        
        considered = self.recv_history[-2][0]
        sentiment = self.sa.sentiment(considered)

        if self.user in self.names.keys():
            name = self.names[self.user]
            negative_responses = [
                "Don't worry, {}! I'm sure things will get better.".format(name),
                "I'm sorry to hear that, {}. Stay strong!".format(name),
                "It'll pass in time, {}, I'm sure!".format(name)
            ]
            positive_responses = [
                "Wow, awesome! I'm glad to hear that, {}.".format(name),
                "That's great, {}!".format(name),
                "Amazing! So glad, {}!".format(name)
            ]
            
        if sentiment == "neg":
            return random.choice(negative_responses) + " " + random.choice(neutral_responses)
        elif sentiment == "pos":
            return random.choice(positive_responses) + " " + random.choice(neutral_responses)
        else:
            return random.choice(neutral_responses)

    def inquiry_reply(self, user, recv_msg):
        # this is only ever inquiry_reply 1, otherwise we would be calling inquiry_reinquiry
        parsed = self.analyze(recv_msg)
        if parsed is None or not parsed["is_question"]:
            self.send_message(user, "I'm not sure I understand the question. Could you repeat that?")
            self.recv_history = self.recv_history[:-1]
            return

        #response = inquiry_reply_parser(self.recv_history[-1] + " " + self.recv_history[-2], self.sentiments)
        response = self.generate_reply() # implicitly received the recv_history
        loc, weather = self.get_loc_weather()
        random.choice([response, response + " Afterall, I do like {}.".format(weather)])
        self.send_message(user, response)
        self.end(user)

    def inquiry_reinquiry(self, user, recv_msg):
        parsed = self.analyze(recv_msg)
        if parsed is None or not parsed["is_question"]:
            self.send_message(user, "I'm not sure I understand the question. Could you repeat that?")
            self.recv_history = self.recv_history[:-1]
            return

        loc, weather = self.get_loc_weather()
        replies = [
            "I kind of like {} here in {}. So not bad at all.".format(weather, loc),
            "I love {}. So great!".format(loc),
            "A bit too {} here for my tastes. Life could be better.".format(weather),
            "Still living life as bits, you know. The usual."
        ]
        inquiries = [
            'How about you?',
            "How about yourself?",
            "How are you doing today?"
        ]
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
            #self.user = random.choice(user)
            return

        # if spec asked for other packet id's they'd go here

        # from here on out, all packets are user input cases
        user = text.split(':', 3)[1].split('!')[0]
        #self.user = user

        # respond to user, if we were prompted by specific user input
        if text is not None and self.nick + ":" in text and self.channel in text:
            if self.state == State.START or self.state == State.SENT_OUTREACH or self.state == State.SENT_OUTREACH_TWICE:
                self.user = user

            # if there hasn't been 2 seconds before last msg, ignore
            if datetime.datetime.now().timestamp() - self.timer < self.cooldown:
                self.send_message(user, "Give me a moment. I need {} seconds to collect my thoughts.".format(self.cooldown))
                self.recv_history = self.recv_history[:-1]
            else:
                if self.user != user:
                    self.send_message(user, "Please don't interrupt the conversation! I'll talk to you in a second, okay?")
                    self.recv_history = self.recv_history[:-1]
                    return
                # store time of last message.
                self.timer = datetime.datetime.now().timestamp()
                self.respond_command(user, text)


    def respond_command(self, user, text):
        """
        Responds to user commands.
        """
        text = text.split(':', 3)
        recv_msg = text[3].lstrip(" ").rstrip("\r\n").lower()
        self.recv_history.append((recv_msg, datetime.datetime.now().timestamp()))

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
    bot = ChatBot(nick="s-bot", channel="#CPE482B", timeout=20)
    bot.run()
    pass

if __name__ == "__main__":
    main()
