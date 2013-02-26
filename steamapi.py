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
from PyQt4 import QtGui, QtCore


username = 'hasustyle'

class PlayerSummary(object):
   def __init__(self):
      pass

class SteamApi(LogHandler):
   
   ERR_INVALID_USER = 1
   
   auth_key = '383C363E19CFA9A8B5C0A576CE8E253D'
   
   def __init__(self, logEnabled = True):
      LogHandler.__init__(self, logEnabled)
      self.logFile    = 'steamapi.log'
      
      if logEnabled:
         self._Log("Creating Steam API object.")
         
   def GetPlayerSummary(self, steamid):
      self._Log("Requesting player summary for steam ID %i" % steamid)
      res = self.GetPlayerSummaries((steamid,))
      if len(res) > 0:
         return res[0]
      else:
         return None 
         
   def GetPlayerSummaries(self, steamids):
      if len(steamids) < 1: return
      elif len(steamids) > 100:
         raise ValueError("GetPlayerSummaries called with a list of %i steam IDs, maximum of 100 IDs is supported!" % len(steamids))
      request = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=%s&steamids=' % SteamApi.auth_key
      
      for id in steamids:
         request += '%s,' % str(id)
      request = request[:-1] # cut the last comma
      
      self._Log("Player summaries query: %s" % request)
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
         
      self._Log("Received %i player summaries." % len(playerSummaries))
      
      # for invalid steam id, this list will be empty!
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
      
      try:
         id_unicode = xmlString.getElementsByTagName('steamID64')[0].firstChild.wholeText
      except IndexError: # steamID64 not found
         self._Log("Invalid profile, response does not contain 'steamID64' (username: %s)" % username)
         return SteamApi.ERR_INVALID_USER
      
      id = int(id_unicode)
      self._Log("Received profile ID %i after %.2f seconds." % (id, time.clock()-startTime))
      
      return id