# -*- coding: utf-8 -*-
'''
Created on 03.01.2013

@author: heller
'''

import time, os
import json
import urllib2
import xml.dom.minidom
import xml.parsers.expat
from util import LogHandler, formatTime
from PyQt4 import QtGui, QtCore


username = 'hasustyle'

class PlayerSummary(object):
   def __init__(self):
      pass
   
class SteamEntry(QtCore.QObject):
   def __init__(self, parentWidget=None):
      self.icon = None
      self.loadedIconSize = 32
      self.iconFile = ""
      self.label = u"Unknown Steam application"
      self.totalTime = 0.
      
   def LoadIcon(self, iconSize=32):
      iconPath = os.path.join("cache", "steam", "%s" % self.iconFile)
      
      if not os.path.isfile(iconPath):
         self.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
      else:
         self.icon=QtGui.QIcon(iconPath)
   
class SteamGameStats:
   def __init__(self, appid, name, playtime, iconUrl=None, logoUrl=None):
      self.appid = appid
      self.name = name
      self.playtime = playtime
      self.iconUrl = iconUrl
      self.logoUrl = logoUrl

class SteamApi(LogHandler):
   ERR_INVALID_USER = 1
   auth_key = '383C363E19CFA9A8B5C0A576CE8E253D'
   
   def __init__(self, logEnabled = True):
      LogHandler.__init__(self, logEnabled, 'steamapi.log')
      
      if logEnabled:
         self._Log("Creating Steam API object.")
         
   def __del__(self):
      LogHandler.__del__(self)
         
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
      try:
         f = urllib2.urlopen(request, timeout=10)
      except urllib2.URLError: # timeout
         self._Log("Timeout, no connection to Steam.")
         return []
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
   
   def GetGameNamesByAppId(self, appids, steamid):
      if len(appids) < 1: return
      #elif len(appids) > 100:
      #   raise ValueError("GetGameNamesByAppId called with a list of %i app IDs, maximum of 100 IDs is supported!" % len(appids))
      
      names = []
      nameById = {}
      for appid in appids:
         request = 'http://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/?appid=%s&key=%s&steamid=%s' % (appid, SteamApi.auth_key, steamid)
      
         self._Log("User stats for game query: %s" % request)
         # fetch result
         try:
            f = urllib2.urlopen(request, timeout=10)
         except urllib2.URLError: # timeout
            self._Log("Timeout, no connection to Steam.")
            break
         
         response = json.load(f, encoding='utf-8')
         f.close()
         
         name = response["playerstats"]["gameName"]
         names.append(name)
         nameById[appid] = name
      
      return names, nameById
   
   def GetOwnedGames(self, steamid):
      request = 'http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=%s&steamid=%s&include_appinfo=1&include_played_free_games=1&format=json' % (SteamApi.auth_key, steamid)
      
      self._Log("Owned games query: %s" % request)
      # fetch result
      try:
         f = urllib2.urlopen(request, timeout=10)
      except urllib2.URLError: # timeout
         self._Log("Timeout, no connection to Steam.")
         return []
      
      response = json.load(f, encoding='utf-8')["response"]
      f.close()
      
      self._Log("Received %i owned games (game count: %i)" % (len(response["games"]), response["game_count"]))
      return response["games"]
   
   def GetSteamIdByUsername(self, username):
      # try to fetch xml profile, this might take several tries
      xmlString = None
      
      request = 'http://steamcommunity.com/id/%s/?xml=1' % username
      self._Log("Trying to fetch Steam profile by username: %s" % request)

      startTime = time.clock()
         
      try:
         f = urllib2.urlopen(request, timeout=10)
      except urllib2.URLError: # timeout
         self._Log("Timeout, no connection to Steam.")
         return None
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
   
   
# a = SteamApi()
# games = a.GetOwnedGames("76561197968959644")
# 
# gameObjs = []
# for g in games:
#    if "playtime_forever" in g and g["playtime_forever"] > 0:
#       gameObj = SteamGameStats(g["appid"], g["name"], g["playtime_forever"], g["img_icon_url"], g["img_logo_url"])
#       gameObjs.append(gameObj)
#       
# for g in gameObjs:
#    print "%s: %s" % (g.name, formatTime(60.*g.playtime))
#    print "http://media.steampowered.com/steamcommunity/public/images/apps/%s/%s.jpg" % (g.appid, g.logoUrl)