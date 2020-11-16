import socket
import sys
import time


class IRC:
    irc = socket.socket()

    def __init__(self):
        # Define the socket
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def send(self, channel, nick, msg):
        # Transfer data
        if nick == None:
            self.irc.send(bytes("PRIVMSG " + channel + " :" + msg + "\n", "UTF-8"))
        else:
            self.irc.send(bytes("PRIVMSG " + channel + " :" + nick + ": " + msg + "\n", "UTF-8"))

    def connect(self, server, channel, botnick):
        # Connect to the server
        self.irc.connect((server, 6667))

        # Perform user authentication
        self.irc.send(bytes("USER " + botnick + " " + botnick + " " + botnick + " :This is a fun bot!\n", "UTF-8"))  # user authentication
        self.irc.send(bytes("NICK " + botnick + "\n", "UTF-8"))

        # join the channel
        self.irc.send(bytes("JOIN " + channel + "\n", "UTF-8"))

    # Receive one packet
    # really, we should write an interface that inherits many packet types
    def get_response(self):

        resp = self.irc.recv(2040).decode("UTF-8")
        print(resp)

        # If server pinged us, respond with pong
        if resp.find('PING') != -1:
            self.irc.send(bytes('PONG ' + resp.split()[1] + '\r\n', "UTF-8"))
        return resp

    # send quit and close the socket
    def die(self, channel):
        self.irc.send(bytes("QUIT " + channel + "\n", "UTF-8"))
        # wait for IRC to accept quit
        time.sleep(2)
        self.irc.close()
        return

    # send names packet
    def name_all(self, channel, nick):
        self.irc.send(bytes("NAMES " + channel + " :" + nick + ": \n", "UTF-8"))


