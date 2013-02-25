# -*- coding: utf-8 -*-
'''
Created on 03.01.2013

@author: heller
'''

import time
import json
import urllib
import xml.dom.minidom
import xml.parsers.expat
from util import LogHandler

username = 'hasustyle'

class PlayerSummary:
   def __init__(self):
      pass

class SteamApi(LogHandler):
   auth_key = '383C363E19CFA9A8B5C0A576CE8E253D'
   
   def __init__(self, logEnabled = True):
      LogHandler.__init__(self, logEnabled)
      self.logFile    = 'steamapi.log'
      
      if logEnabled:
         self._Log("Creating Steam API object.")
         
   def GetPlayerSummary(self, steamid):
      return self.GetPlayerSummaries((steamid,))[0]
         
   def GetPlayerSummaries(self, steamids):
      if len(steamids) < 1: return
      elif len(steamids) > 100:
         raise ValueError("GetPlayerSummaries called with a list of %i steam IDs, maximum of 100 IDs is supported!" % len(steamids))
      request = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=%s&steamids=' % SteamApi.auth_key
      
      for id in steamids:
         request += '%s,' % str(id)
      request = request[:-1] # cut the last comma
      
      self._Log("Trying to fetch player summaries: %s" % request)
      # fetch result
      f = urllib.urlopen(request)
      summaries = json.load(f, encoding='utf-8')["response"]["players"]
      f.close()
      
      playerSummaries = []
      for s in summaries:
         ps = PlayerSummary()
         for var in s.keys():
            setattr(ps, var, s[var])
         
         playerSummaries.append(ps)
         
      return playerSummaries
      
   
   def GetSteamIdByUsername(self, username):
      # try to fetch xml profile, this might take several tries
      xmlString = None
      
      request = 'http://steamcommunity.com/id/%s/?xml=1' % username
      self._Log("Trying to fetch Steam profile by username: %s" % request)

      startTime = time.clock()
         
      f = urllib.urlopen(request)
      profile = f.read()
      f.close()
         
      try:
         xmlString = xml.dom.minidom.parseString(profile.encode('utf-8'))
      except xml.parsers.expat.ExpatError:
         self._Log("Failed to fetch profile ID after %.2f seconds." % (time.clock()-startTime))
         return None
      
      id_unicode = xmlString.getElementsByTagName('steamID64')[0].firstChild.wholeText
      id = int(id_unicode)   
      self._Log("Received profile ID %i after %.2f seconds." % (id, time.clock()-startTime))
      
      return id


s = SteamApi()
#id = s.GetSteamIdByUsername('hasustyle')
id = 76561197968959644
s.GetPlayerSummaries((id,))