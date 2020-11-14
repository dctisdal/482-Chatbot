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
        self.irc.send(bytes("PRIVMSG " + channel + " :" + nick + ": " + msg + "\n", "UTF-8"))

    def connect(self, server, channel, botnick):
        # Connect to the server
        print("Connecting to: " + server)
        self.irc.connect((server, 6667))

        # Perform user authentication
        self.irc.send(bytes("USER " + botnick + " " + botnick + " " + botnick + " :This is a fun bot!\n", "UTF-8"))  # user authentication
        self.irc.send(bytes("NICK " + botnick + "\n", "UTF-8"))
        time.sleep(5)

        # join the channel
        self.irc.send(bytes("JOIN " + channel + "\n", "UTF-8"))

    def get_response(self):
        time.sleep(1)
        # Get the response
        resp = self.irc.recv(2040).decode("UTF-8")
        print(resp)

        if resp.find('PING') != -1:
            self.irc.send(bytes('PONG ' + resp.split()[1] + '\r\n', "UTF-8"))

        return resp