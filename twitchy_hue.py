

import socket,logging
import time
import imp
import os, sys
import traceback
import re
from threading import Thread
from devices import Hue
from yaml import load, dump
import webcolors
logger = logging.getLogger("sub_alert")

def remove_nonascii(text):
    return ''.join(i for i in text if ord(i)<128)

class sub_alerter:
    def __init__(self):
        logger.info("Sub_alerter starting up")
        self.config = self._loadconfig()
        self.ircSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ircServ = 'irc.twitch.tv'
        self.ircChan = self.config['twitch_channel']
        try:
            self.hue = Hue(self.config["hue_bridge_ip"])
        except Exception, e:
            logger.critical("Error while setting up hue bridge")
            logger.critical(e.message)
            sys.exit()
        self.connected = False

    def _loadconfig(self):
        logger.info("Loading configuration from config.txt")
        config = None
        if os.path.isfile("config.txt"):
            try:
                config = load(open("config.txt",'r'))
                required_settings = ['hue_bridge_ip','twitch_username','twitch_oauth','twitch_channel','color_1','color_2','times_to_flash','flash_speed']
                for setting in required_settings:
                    if not setting in config:
                        logger.critical('%s is not present in config.txt, please put it there! check config_example.txt!' %setting)
                        sys.exit()
                    #don't allow unicode!
                    if isinstance(config[setting],unicode):
                        config[setting] = str(remove_nonascii(config[setting]))
                try:
                    config['color_1'] = webcolors.name_to_rgb(config['color_1'])
                    config['color_2'] = webcolors.name_to_rgb(config['color_2'])
                except Exception, e:
                    logger.critical("Problem interpreting your color choices, please consult http://www.cssportal.com/css3-color-names/ for valid color names")
                    logger.debug(e.message)
                    sys.exit()
            except SystemExit:
                sys.exit()
            except Exception, e:
                logger.info(e)
                logger.critical("Problem loading configuration file, try deleting config.txt and starting again")
        else:
            logger.critical("config.txt doesn't exist, please create it, refer to config_example.txt for reference")
            sys.exit()
        logger.info("Configuration loaded")
        return config

    def sendMessage(self, message):
        self.ircSock.send(str('PRIVMSG %s :%s\n' % (self.ircChan, message)).encode('UTF-8'))

    def connect(self, port):
        logger.info("Connecting to twitch irc")
        self.ircSock.connect((self.ircServ, port))
        logger.info("Connected..authenticating as %s" %self.config['twitch_username'])
        self.ircSock.send(str("Pass " + self.config['twitch_oauth'] + "\r\n").encode('UTF-8'))
        self.ircSock.send(str("NICK " + self.config['twitch_username'] + "\r\n").lower().encode('UTF-8'))
        self.ircSock.send(str("CAP REQ :twitch.tv/tags\r\n").encode('UTF-8'))
        logger.info("Joining channel %s" %self.config['twitch_channel'])
        self.ircSock.send(str("JOIN " + self.config['twitch_channel'] + "\r\n").encode('UTF-8'))

    def handle_subscriber(self):
        self.hue.flash(
                        color_1=self.config['color_1'],
                        color_2=self.config['color_2'],
                        ntimes=int(self.config['times_to_flash']),
                        interval=int(self.config['flash_speed'])
                        )

    def handleIRCMessage(self, ircMessage):
        print ircMessage
        if re.search(r":tmi.twitch.tv NOTICE \* :Error logging i.*", ircMessage):
            logger.critical("Error logging in to twitch irc, check your oauth and username are set correctly in config.txt!")
            sys.exit()
        if ircMessage.find("JOIN %s" %self.config['twitch_channel']) != -1:
            logger.info("Joined channel %s successfully... watching for new subscribers" %self.config['twitch_channel'])
        match = re.search(r":twitchnotify!twitchnotify@twitchnotify\.tmi\.twitch\.tv PRIVMSG #([^ ]*) :([^ ]*) just subscribed!", ircMessage)
        if match:
            new_subscriber = match.group(2)
            logger.info("New subscriber! %s" %new_subscriber)
        match = re.search(r":twitchnotify!twitchnotify@twitchnotify\.tmi\.twitch\.tv PRIVMSG #([^ ]*) :([^ ]*) subscribed for (.) months in a row!", ircMessage)
        if match:
            subscriber =  match.group(2)
            months = match.group(3)
            logger.info(("%s just subscribed for the %s months in a row! Yay! Flashing the lights") %(subscriber,months))
            self.handle_subscriber()
        elif ircMessage.find('PING ') != -1:
            logger.info("Responding to a ping from twitch... pong!")
            self.ircSock.send(str("PING :pong\n").encode('UTF-8'))


    def run(self):
        line_sep_exp = re.compile(b'\r?\n')
        socketBuffer = b''
        while True:
            try:
                self.connected = True
                #get messages
                socketBuffer += self.ircSock.recv(1024)
                ircMsgs = line_sep_exp.split(socketBuffer)
                socketBuffer = ircMsgs.pop()
                # Deal with them
                for ircMsg in ircMsgs:
                    msg = ircMsg.decode('utf-8')
                    self.handleIRCMessage(msg)
            except:
                raise


# 'main'
if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.DEBUG,format="%(asctime)s.%(msecs)d %(levelname)s %(name)s : %(message)s",datefmt="%H:%M:%S")
        while True:
            alerter = sub_alerter()
            try:
                alerter.connect(6667)
                alerter.run()
            except SystemExit:
                sys.exit()
            except Exception as e:
                logger.info(traceback.format_exc())

            # If we get here, try to shutdown the bot then restart in 5 seconds
            time.sleep(5)
    finally:
        raw_input("Press enter or ctrl c to finish")
