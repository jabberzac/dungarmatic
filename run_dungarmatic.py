import dungarmatic_config as config
import gettext
from Jabberzac import MarkovBot
import jabber
import traceback
import time

username = config.config['username']
password = config.config['password']
devMode = config.config['dev']

# debug mode outputs verbose info to the console
#parameter = nickname for that channel.. use different nicknames if you need multiple dungars in one channel
lang_en = gettext.translation('dungarmatic', '.', languages=['en'])
#lang_ru = gettext.translation('dungarmatic', '.', languages=['ru'])
bots = []
if(devMode == False):
    debug = False
    resource = 'Dungarmatic'
    bot = MarkovBot('Dungarmatic', lang_en)
    bot.debugMode = True
    bots.append( ('jabberzac@conference.jabberzac.org',bot,None) )

#    bot2 = MarkovBot('Mifrrriiiilll', lang_ru)
#    bot2.debugMode = True
#    bots.append( ('eve_oeg@conference.oeg.su',bot2,'nexus') )
else:
    resource = 'DungarmaticTest'
    debug = False
    
    bot = MarkovBot('Testmatic', lang_en)
    bot.debugMode = True
    bots.append( ('testchat@conference.jabberzac.org',bot,None) )

#    bot2 = MarkovBot('Mifrrriiiilll-Test', lang_ru)
#    bot2.debugMode = True
#    bots.append( ('eve_oeg@conference.oeg.su',bot2,'nexus') )

while True:
    try:
        conn = jabber.ServerConnection(username,password,resource,debug)
        for channel, bot, password in bots:
            conn.joinChannel(channel,bot, password)
        conn.serveForever()
    except IOError, e:
        traceback.print_exc()
        time.sleep(60)
