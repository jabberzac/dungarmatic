#!/usr/bin/python

# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2008 Jabberzac
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Branched from python-jabberbot by some dude at http://thpinfo.com/2007/python-jabberbot/
#


import xmpp
import inspect
import string
import random
import re
"""A completely hacked version of python-jabberbot

Copyright (c) 2008 Jabberzac
"""

class JabberBot(object):
    command_prefix = 'bot_'
    
    def __init__( self, jid, password, debug = False, res = None):
        """Initializes the jabber bot and sets up commands."""
        self.jid = xmpp.JID( jid)
        self.password = password
        self.presence = None
        self.channel = None
        self.handlers = {}
        self.processors = []
        self.debug = debug
        self.loops = []
        self.history = []
        self.sendQueue = []
        self.messhistory = []
        self.roster = []
        self.onjoins = {}
        self.channelRoster = []
        self.lastmessage = ''
        self.timeSinceLastMessage = 0
        self.timeSinceLastOwnMessage = 0
        self.timeSincePresence = 0
        self.timeOnline = 0
        self.res = (res or self.__class__.__name__)
        self.conn = None
        self.__finished = False
        
        self.commands = { 'help': self.help_callback, }
        for (name, value) in inspect.getmembers( self):
            if inspect.ismethod( value) and name.startswith( self.command_prefix):
                self.commands[name[len(self.command_prefix):]] = value

    def log( self, s):
        """Logging facility, can be overridden in subclasses to log to file, etc.."""        
        print '%s: %s' % ( self.__class__.__name__, s.encode("utf-8"), )

    def addHandler(self, phrases, callback):
        for phrase in phrases:
            self.handlers[re.compile(phrase, re.IGNORECASE)] = callback
    
    def addProcessor(self,callback):
        self.processors.append(callback)
    
    def addLoop(self,callback):
        self.loops.append(callback)
        
    def addOnJoin(self, nicks, callback):
        for nick in nicks:
            self.onjoins[nick] = callback
        
    def connect( self):
        if not self.conn:
            conn = xmpp.Client( self.jid.getDomain(), debug = [])
            
            if not conn.connect():
                self.log( 'unable to connect to server.')
                return None
            
            if not conn.auth( self.jid.getNode(), self.password, self.res):
                self.log( 'unable to authorize with server.')
                return None
            
            conn.RegisterHandler( 'message', self.callback_message)
            conn.RegisterHandler( 'presence', self.conference_presence)            
            conn.sendInitPresence()
            self.conn = conn

        return self.conn

    def quit( self):
        """Stop serving messages and exit.
        
        I find it is handy for development to run the 
        jabberbot in a 'while true' loop in the shell, so 
        whenever I make a code change to the bot, I send 
        the 'reload' command, which I have mapped to call
        self.quit(), and my shell script relaunches the 
        new version.
        """
        self.__finished = True
        
    def queueSend (self, user,text,delay,in_reply_to = None ):
        """delays a message"""
        mess = xmpp.Message( user, text)
        if in_reply_to:
            mess.setThread( in_reply_to.getThread())
            mess.setType( in_reply_to.getType())
        object = {'mess': mess, 'delay': delay, 'timer': 0}
        self.sendQueue.append(object)
        
    def sendMess (self, mess):
        """sends a pre-formatted xmpp.Message"""
        text = mess.getBody()
        if len(self.history) >= 10:
            self.history.pop()
        self.history.insert(0,text)
        if self.debug:
            self.log(self.resource + ': ' + text)
        self.timeSinceLastMessage = 0
        self.timeSinceLastOwnMessage = 0
        self.connect().send( mess)
        
    def send( self, user, text, in_reply_to = None):
        """Sends a simple message to the specified user."""
        mess = xmpp.Message( user, text)
        if len(self.history) >= 10:
            self.history.pop()
        self.history.insert(0,text)
        if self.debug:
            self.log(self.resource + ': ' + text)
        if in_reply_to:
            mess.setThread( in_reply_to.getThread())
            mess.setType( in_reply_to.getType())
            
        self.timeSinceLastMessage = 0
        self.timeSinceLastOwnMessage = 0
        self.connect().send( mess)

    def callback_message( self, conn, mess):
        """Messages sent to the bot will arrive here. Command handling + routing is done in this function."""
        nick=mess.getFrom().getResource()
        text = mess.getBody()
        if mess.getType() == "groupchat":
            sendTo = self.channel
            if len(self.messhistory) >= 10:
                self.messhistory.pop()
            self.messhistory.insert(0,mess)
        else:
            sendTo = mess.getFrom()
        #Only fire stuff if we actually have a message, and it's not from the bot
        if text and text != self.lastmessage and nick != self.resource:
            if self.debug:
                self.log(nick + ': ' + text)
            
            if len(self.history) >= 10:
                self.history.pop()
            self.history.insert(0,text)
            
            
            
            self.lastmessage = text
            self.timeSinceLastMessage = 0
            # If a message format is not supported (eg. encrypted), txt will be None
            if not text:
                return
    
            if ' ' in text:
                command, args = text.split(' ',1)
            else:
                command, args = text,''
        
            cmd = command.lower()
        
            if self.commands.has_key(cmd):
                reply = self.commands[cmd]( mess, args)
            else:            
                reply = None
            
            if reply == None: 
                for handler in self.handlers.keys():
                        match = handler.search(text)            
                        if match:
                            reply = self.handlers[handler]( mess, match )
                            if reply:
                                break
            
            if reply == None:
                for proc in self.processors:
                    reply = proc(mess)
                    if reply:
                        break
            
            if reply:
                self.log(reply)
                if(self.channel):
                    if len(reply) > 1:
                        delay = (random.random() * 3) + 2
                    else:
                        delay = 1
                    
                    self.queueSend( sendTo, reply, delay, mess)
                else:
                    self.send( sendTo, reply, mess)
            
    def calculateChance(self, chance):
        """chance should be a dictionary with the keys being a number like 0.25
            and the value a string to return, the keys should sum to a maximum 
            of <= 1.0"""
        random.seed()
        rnd = random.random()
        #if self.debug:
            #self.log('Random number generated: ' + str(rnd))
        t = 0
        for message in chance.keys():
            c = chance[message];
            m = t
            t = t + c
            if rnd < t and rnd >= m:
                return message
        return None
    
    def conference_presence (self, sess,pres):
        person=pres.getFrom().getStripped()
        if person == self.channel:
            roster = self.channelRoster
            nick=pres.getFrom().getResource()
            if nick != self.resource:
                if pres.getRole() == 'none':
                    if self.debug:
                        self.log(nick + ' has left the channel')
                    if nick in roster:
                        roster.remove(nick)
                else:
                    if self.debug:
                        self.log(nick + ' has joined the channel')
                    if nick not in roster:
                        #someone has joined the channel, call all onjoin events
                        #first, check that we have been online for a while, as not to
                        #trigger when the bot joins the channel
                        if self.timeOnline > 5 and len(self.messhistory) > 0:
                            reply = None
                            for name in self.onjoins.keys():                                
                                if nick == name:                                    
                                    reply = self.onjoins[name](pres)
                                if reply:                                    
                                    delay = (random.random() * 3) + 2
                                    self.queueSend( self.channel, reply, delay, self.messhistory[0])
                                reply = None                                        
                            
                        roster.append(nick)
        else:
            roster = self.roster
            nick=pres.getFrom().getNode()

            if pres.getType()=='unavailable':
                if self.debug:
                    self.log(nick + ' has logged off the server')
                if nick in roster:
                    roster.remove(nick)
            else:
                if self.debug:
                    self.log(nick + ' has logged on to the server')
                if nick not in roster:                
                    roster.append(nick)
    
    def unknown_command( self, mess, cmd, args):
        """Default handler for unknown commands

        Override this method in derived class if you 
        want to trap some unrecognized commands.  If 
        'cmd' is handled, you must return some non-false 
        value, else some helpful text will be sent back
        to the sender.
        """
        return None

    def help_callback( self, mess, args):
        """Returns a help string listing available options. Automatically assigned to the "help" command."""
        usage = '\n'.join( [ '%s: %s' % ( name, command.__doc__ or '(undocumented)' ) for ( name, command ) in self.commands.items() if name != 'help' ])

        if self.__doc__:
            description = self.__doc__.strip()
        else:
            description = 'Available commands:'

        return '%s\n\n%s' % ( description, usage, )

    def idle_proc( self):
        """This function will be called in the main loop."""
        
        pass

    def serve_forever( self, channel = None, channelpass = None, resource = None, connect_callback = None, disconnect_callback = None):
        """Connects to the server and handles messages."""
        conn = self.connect()
        
        if self.addHandlers:
            self.addHandlers()
            
        if conn:
            self.log('bot connected. serving forever.')
        else:
            self.log('could not connect to server - aborting.')
            return

        if connect_callback:
            connect_callback()
            
        if channel:            
            self.channel = channel
            self.resource = resource            
            self.presence=xmpp.protocol.Presence(to='%s/%s'%(channel,resource))
            self.presence.setTag('x',namespace=xmpp.protocol.NS_MUC).setTagData('password',channelpass)
            self.presence.getTag('x').addChild('history',{'maxchars':'0','maxstanzas':'0'})
            conn.send(self.presence)

        while not self.__finished:
            try:                            
                conn.Process(1)
                self.timeSinceLastMessage += 1
                self.timeSinceLastOwnMessage += 1
                self.timeSincePresence += 1
                self.timeOnline += 1
                reply = None
                if len(self.messhistory) > 0:
                    for loop in self.loops:
                        try:
                            reply = loop()
                            if reply:
                                if(self.channel):                
                                    self.send( self.channel, reply, self.messhistory[0])
                        except:
                            pass
                
                for item in self.sendQueue:
                    if item['timer'] >= item['delay']:
                        mess = item['mess']
                        self.sendMess(mess)
                        self.sendQueue.remove(item)
                    item['timer'] += 1
                
                if channel and self.timeSincePresence > 120:
                    #self.log('sending presence to server')
                    conn.send(self.presence)
                    self.timeSincePresence = 0
                                      
                
            except KeyboardInterrupt:
                self.log('bot stopped by user request. shutting down.')
                break

        if disconnect_callback:
            disconnect_callback()


