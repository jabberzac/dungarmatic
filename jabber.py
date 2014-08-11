import xmpp
import random
import re
import inspect
import Queue
import threading
import time
import sys
import traceback
import gettext
import xmpp.simplexml as simplexml

class ServerConnection (object):
    def __init__( self, jid, password, res = "Jabberbot", debug = False ):
        """Initializes the connection."""
        self.jid = xmpp.JID( jid)
        
        self.logOnTime = None
        
        self.channels = {}
        self.sendQueue = []
        self.loops = {}
        self.roster = []
        self.debug = debug
        self.conn = None
        self.__finished = False
        self.timeOnline = 0
        self.messageQueue = Queue.Queue(0)
        numthreads = 10
        for i in range(numthreads):
            worker = threading.Thread(target = self.messageLoop)
            worker.setName('Worker thread '+str(i))
            worker.setDaemon(True)
            worker.start()
        
        self.threads = ThreadManager()
        
        self.res = res
        self.password = password

        self.serverData = {}
        
        self.connect()
        
    def joinChannel(self,channelName,bot,channelpass = None):
        """pass a jabberbot object to join a channel"""

        self.log('Joining channel %s' % channelName)
            
        if self.conn:            
            presence = xmpp.protocol.Presence(to='%s/%s'%(channelName,bot.resource))            
            presence.setTag('x',namespace=xmpp.protocol.NS_MUC).setTagData('password',channelpass)
            presence.getTag('x').addChild('history',{'maxchars':'0','maxstanzas':'0'})
            self.conn.send(presence)
            
            channel = Channel(presence,bot)
            channel.bot.conn = self
            channel.bot.channel = channelName
            self.channels[channelName] = channel
    
    def log( self, s, ob = None):
        """Logging facility"""
        if s and self.debug:
            if ob:
                className = ob.__class__.__name__
            else:
                className = self.__class__.__name__
                
            print '%s: %s' % ( className, s.encode("utf-8"), )
      
    def connect( self):
        if not self.conn:
            conn = xmpp.Client( self.jid.getDomain(), debug = [])
            
            if not conn.connect():
                self.log( 'Unable to connect to server.')
                return None
            
            if not conn.auth( self.jid.getNode(), self.password, self.res):
                self.log( 'Unable to authorize with server.')
                return None
            
            conn.RegisterHandler( 'message', self.messageCallback)
            conn.RegisterHandler( 'presence', self.presenceCallback)
            conn.sendInitPresence()
            self.logOnTime = time.time()
            self.conn = conn

        return self.conn
    
    def addLoop(self, name, callback):        
        self.loops[name] = callback
    
    def queueSend (self, user,text,delay,in_reply_to = None ):
        """delays a message"""
        mess = xmpp.Message( user, text)
        if in_reply_to:
            mess.setThread( in_reply_to.getThread())
            mess.setType( in_reply_to.getType())
        object = {'mess': mess, 'delay': delay, 'timer': 0}
        self.sendQueue.append(object)
        
        if user in self.channels.keys():
            channel = self.channels[user]
            bot = channel.bot
            ob = bot
        else:
            ob = self
            
        self.log(text, ob)
        
    def sendMess (self, mess):
        """sends a pre-formatted xmpp.Message"""
        text = mess.getBody()
        user = mess.getTo()
        if user in self.channels.keys():
            channel = self.channels[user]
            bot = channel.bot
            ob = bot
        else:
            ob = self
            
        self.conn.send( mess)
        
    def send( self, user, text, in_reply_to = None):
        """Sends a simple message to the specified user."""
        mess = xmpp.Message( user, text)
        if user in self.channels.keys():
            channel = self.channels[user]
            bot = channel.bot
            ob = bot
        else:
            ob = self        
        
        self.log(text, ob)
        if in_reply_to:
            mess.setThread( in_reply_to.getThread())
            mess.setType( in_reply_to.getType())
            
        self.conn.send( mess)
        
    def quit (self):
        self.__finished = True
        
    def randomDelay(self, reply, min=2,mul=3):
        if len(reply) > 1:
            delay = (random.random() * mul) + min
        else:
            delay = min
        return delay
    
    def presenceCallback (self, sess, pres):
        person=pres.getFrom().getStripped()
        if self.channels.has_key(person):
            channel = self.channels[person]
            bot = channel.bot
            roster = bot.channelRoster
            nick=pres.getFrom().getResource()
            if pres.getRole() == 'none':                
                self.log(nick + ' has left ' + person)
                if nick in roster:
                    del roster[nick]
                if nick in bot.channelModerators:
                    bot.channelModerators.remove(nick)
            else:
                if pres.getNick():
                    self.log('%s is now known as %s'%(nick,pres.getNick()))
                    if nick in roster:
                        del roster[nick]
                    if nick in bot.channelModerators:
                        bot.channelModerators.remove(nick)
                    nick = pres.getNick()
                self.log(nick + ' has joined ' + person)
                if nick not in roster:
                    if self.timeOnline > 5 and len(bot.messhistory) > 0:
                        reply = None
                        for name in bot.onjoins.keys():
                            match = name.search(nick)
                            if match:                                    
                                reply = bot.onjoins[name](pres)
                            if reply:                                    
                                delay = self.randomDelay(reply)
                                self.queueSend( person, reply, delay, bot.messhistory[0])
                            reply = None                                        
                        
                    if pres.getJid():
                        jid = xmpp.protocol.JID(pres.getJid())
                        roster[nick]=jid
            if pres.getRole() == 'moderator':
                bot.channelModerators.add(nick)
            else:
                if nick in bot.channelModerators:
                    bot.channelModerators.remove(nick)
        else:
            roster = self.roster
            nick=pres.getFrom().getNode()

            if pres.getType()=='unavailable':                
                self.log(nick + ' has logged off the server')
                if nick in roster:
                    roster.remove(nick)
            else:                
                self.log(nick + ' has logged on to the server')
                if nick not in roster:                
                    roster.append(nick)
    
    def messageCallback(self, conn, mess):
        self.messageQueue.put(mess)

    def messageLoop(self):
        while True:
            try:
                mess = self.messageQueue.get()
                text = mess.getBody()
                if not text:
                    print threading.currentThread().getName()+" message has no text"
                    continue

                channelName = mess.getFrom().getStripped()
                channel = None
                if self.channels.has_key(channelName):
                    channel = self.channels[channelName]

                if channel:
                    res = mess.getFrom().getResource()            
                    bot = channel.bot
                    self.log('%s/%s: %s' % (channelName,res,text),bot)
                    if mess.getType() == "groupchat":
                        bot.timeSinceLastMessage = 0
                        if res == bot.resource:
                            bot.timeSinceLastOwnMessage = 0
                        sendTo = channelName

                        if len(channel.bot.messhistory) >= 10:
                            channel.bot.messhistory.pop()
                        channel.bot.messhistory.insert(0,mess)

                        if len(channel.bot.history) >= 10:
                            channel.bot.history.pop()
                        channel.bot.history.insert(0,text)
                    else:
                        sendTo = mess.getFrom()

                    if not sendTo:
                        print threading.currentThread().getName()+" no sendTo"
                        continue

                    reply = None

                    if ' ' in text:
                        command, args = text.split(' ',1)
                    else:
                        command, args = text,''

                    cmd = command.lower()

                    if bot.commands.has_key(cmd):
                        reply = bot.commands[cmd]( mess, args)

                    if not reply:
                        for handler in bot.handlers.keys():
                            match = handler.search(text)
                            if match:
                                reply = bot.handlers[handler]( mess, match )
                                if reply:
                                    break

                    if not reply:               
                        for proc in bot.processors:
                            reply = proc(mess)
                            if reply:
                                break

                    if reply:
                        delay = self.randomDelay(reply)
                        self.queueSend(sendTo, reply, delay, mess)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                traceback.print_exc()

    def serveForever(self):        
        for channelName in self.channels.keys():
            channel = self.channels[channelName]
            bot = channel.bot            
            if bot.initBot:
                bot.initBot()
            
        while not self.__finished:
            try:                            
                if self.conn.Process(1) == 0:
                    print 'disconnected from %s, reconnecting'%self.jid
                    self.conn.reconnectAndReauth()
                    print 'reconnected to %s'%self.jid
                t = time.time()
                self.timeOnline = t - self.logOnTime                
                presenceCutoff = t - 300
                for channelName in self.channels.keys():
                    channel = self.channels[channelName]
                    bot = channel.bot
                    bot.timeSinceLastMessage += 1    
                    bot.timeSinceLastOwnMessage += 1
                    if channel.lastPresence <= presenceCutoff or channel.lastPresence == 0:
                        channel.lastPresence = t                        
                        self.log('Sending presence for %s' % channelName)                        
                        self.conn.send(channel.presence)                        
                    
                    for loopName in self.loops.keys():
                        self.threads.start(loopName, self.loops[loopName])         
                    
                    for item in self.sendQueue:
                        if item['timer'] >= item['delay']:
                            mess = item['mess']
                            self.sendMess(mess)
                            self.sendQueue.remove(item)
                        item['timer'] += 1
                    
                    if len(bot.messhistory) > 0:
                        for loop in bot.loops:
                            reply = loop()
                            if reply:
                                self.send(channelName, reply, bot.messhistory[0])
                    
                        
            except KeyboardInterrupt:
                self.log('Bot stopped by user request. Shutting down.')
                exit(0)
            
class ThreadManager (object):
    def __init__(self):
        self.threads = {}
    
    def start(self, name, func):
        if self.threads.has_key(name):
            thread = self.threads[name]
            if thread.isAlive():
                return
                    
        thread = threading.Thread()
        thread.run = func
        thread.setDaemon(True)
        self.threads[name] = thread
        thread.start()        

class Channel (object):
    def __init__(self,presence,bot):
        self.presence = presence
        self.bot = bot
        self.lastPresence = 0
        
class Bot (object):
    command_prefix = 'bot_'
    def __init__(self, nick = None, language = gettext.NullTranslations()):
        if not nick:
            nick = self.__class__.__name__
        self.presence = {}
        self.conn = None
        self.channelRoster = {}
        self.channelModerators = set()
        self.handlers = {}
        self.processors = []
        self.commands = {}
        self.loops = []
        self.debug= True
        self.onjoins = {}
        
        self.history = []
        self.messhistory = []
        
        self.timeSinceLastMessage = 0
        self.timeSinceLastOwnMessage = 0   
        
        self.resource = nick
        self.lang = language
        
        for (name, value) in inspect.getmembers( self):
            if inspect.ismethod( value) and name.startswith( self.command_prefix):
                self.commands[name[len(self.command_prefix):]] = value     
        
    def log(self,s):
        self.conn.log(s,self)
        
    def addHandler(self, phrases, callback):
        for phrase in phrases:
            self.handlers[re.compile(phrase, re.IGNORECASE)] = callback
    
    def addProcessor(self,callback):
        self.processors.append(callback)
    
    def addLoop(self,callback):
        self.loops.append(callback)
        
    def addServerLoop(self,name,callback):
        self.conn.addLoop(name,callback)
        
    def addOnJoin(self, nicks, callback):
        for nick in nicks:
            self.onjoins[re.compile(nick, re.IGNORECASE)] = callback
        
    def calculateChance(self, chance):
        """chance should be a dictionary with the keys being a number like 0.25
            and the value a string to return, the keys should sum to a maximum 
            of <= 1.0"""
        random.seed()
        rnd = random.random()
        t = 0
        for message in chance.keys():
            c = chance[message];
            m = t
            t = t + c
            if rnd < t and rnd >= m:
                return message
        return None

    def kick(self, nick, reason=None):
        kick_item = simplexml.Node(tag='item',attrs={'nick':nick,'role':'none'})
        reason_node=simplexml.Node(tag='reason')
        if reason:
            reason_node.setData(reason)
        else:
            reason_node.setData('fuck you')
        kick_item.addChild(node=reason_node)
        iq = xmpp.protocol.Iq(typ='set', queryNS='http://jabber.org/protocol/muc#admin',to=self.channel,frm=self.conn.jid,payload=[kick_item])
        self.conn.conn.send(iq)
