# -*- coding: utf-8 -*-

#
#  This code is due to Andreas Maier and licensed under the MIT License http://opensource.org/licenses/MIT
#   http://code.activestate.com/recipes/576507-sort-strings-containing-german-umlauts-in-correct-/
#

import codecs
import time
import threading
from types import *

STAMPFORMAT = '(%d.%m.%Y - %H:%M:%S) '

class ProfileSettings:
   """ Container class for keeping settings saved to or loaded from a profile file """ 
   def __init__(self):
      # None values are unknown yet
      self.iconSize = None
      self.numEntries = None
      self.windowSize = None
      self.windowPos  = None
      self.toolsVisible = None
      self.sortMode = None
      self.steamId = None
      #self.entries = []
      
   @staticmethod
   def Default():
      d = ProfileSettings()
      d.iconSize = 128
      d.numEntries = 0
      d.windowSize = (800,600)
      d.windowPos = (0,0)
      d.toolsVisible = 1
      d.sortMode = "manual"
      d.steamId = '0'
      return d

class EntrySettings:
   """ Container class for keeping settings specific to a single entry """
   def __init__(self):
      self.filename = None
      self.workingDir = None
      self.label = None
      self.cmdLineArgs = None
      self.iconPath = None
      self.preferredIcon = None
      self.position = None
      self.totalTime = None
      
   @staticmethod
   def Default():
      d = EntrySettings()
      d.filename = ""
      d.workingDir = ""
      d.label = "Unknown entry"
      d.cmdLineArgs = ""
      d.iconPath = ""
      d.preferredIcon = -1
      d.position = 0
      d.totalTime = 0.
      return d

class LogHandler:
   """ Abstract base class for an object with logging capabilities.
     Logs are written to a logfile specified when creating the object, writing operations are done by a
     separate thread in regular intervals, so don't be afraid to log often and much, the main program will not
     be delayed by this.
      
     When subclassing this class, make sure to call LogHandler.__del__ in the new destructor, otherwise
     the logging thread might not exit correctly. Look for 'Stopping logger thread.' lines in the logfile,
     if these are not present, the thread was probably killed too soon. """
   def __init__(self, logEnabled = True, logFile = None):
      self.logEnabled = logEnabled
      self.logCodepage= 'utf-8'
      self.logFile = logFile
      
      self._logsToWrite = []
      
      self._runLoggerThread = True
      self._loggerThread = threading.Thread(target=self._LoggerLoop)
      self._loggerThread.daemon = True # killed automatically on closing the program.
      self._loggerThread.start()
      
   def __del__(self):
      # stop logger thread
      self._Log("Stopping logger thread.")
      self._runLoggerThread = False
      self._loggerThread.join(timeout=5) # wait for logger thread to finish
      if self._loggerThread.isAlive():
         raise Exception('Failed to terminate logger thread. Please kill the program manually. Log files might be corrupt.')
      
   def _Log(self, text):
      """ Add text to log file, if logging is enabled. """
      if self.logEnabled:
         timestamp = time.strftime(STAMPFORMAT)
         self._logsToWrite.append(timestamp + text + '\n') # append is thread safe
            
   def _LoggerLoop(self):
      self._Log("Logger thread running.")
      while self._runLoggerThread:
         while len(self._logsToWrite) > 0:
            newLog = self._logsToWrite.pop(0)
            if not self.logFile:
               raise IOError('No logfile specified for log handler class!', self)
            with codecs.open(self.logFile, 'a', self.logCodepage) as f:
               f.write(newLog)
         time.sleep(0.3)
      
      # write remaining logs and then quit
      while len(self._logsToWrite) > 0:
         newLog = self._logsToWrite.pop(0)
         if not self.logFile:
            raise IOError('No logfile specified for log handler class!', self)
         with codecs.open(self.logFile, 'a', self.logCodepage) as f:
            f.write(newLog)

class FileParser(LogHandler):
   # dictionary with main profile format specifiers, accessed by format version
   profileFormats = {
    '0.1a': [ ('iconSize', int),
              ('numEntries', int),
              ('windowSize', (int,int)),
              ('windowPos', (int,int)),
              ('toolsVisible', int) ] ,
              
    '0.1b': [ ('iconSize', int),
              ('numEntries', int),
              ('windowSize', (int,int)),
              ('windowPos', (int,int)),
              ('toolsVisible', int),
              ('sortMode', str) ] ,
              
    '0.1c': [ ('iconSize', int),
              ('numEntries', int),
              ('windowSize', (int,int)),
              ('windowPos', (int,int)),
              ('toolsVisible', int),
              ('sortMode', str),
              ('steamId', str) ] }
   
   # dictionary with entry format specifiers, accessed by format version
   entryFormats = {
    '0.1a': [ ('filename', unicode),
              ('workingDir', unicode),
              ('label', unicode),
              ('cmdLineArgs', unicode),
              ('iconPath', unicode),
              ('preferredIcon', int),
              ('position', int),
              ('totalTime', float) ] }
   
   def __init__(self, logEnabled = True):
      LogHandler.__init__(self, logEnabled, 'parser.log')
      
      if logEnabled:
         self._Log("Creating file parser object.")
         
   def __del__(self):
      LogHandler.__del__(self)
         
   def CompleteEntry(self, handler, version):
      """ Fills all entry parameters which still are None with their default values. This should be called after loading an
         entry to have consistent data in it. Returns the number of modified variables. """
      count = 0
      
      try: fmt = FileParser.entryFormats[version]
      except KeyError:
         raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse entry.' % version)
         return 0
      
      #self._Log("Completing entry with default values according to version %s." % version)
      for var, type in fmt:
         if getattr(handler, var) is None:
            setattr(handler, var, getattr(EntrySettings.Default(), var))
            count += 1
            
      self._Log("Completed entry by setting %i variables to their default values.\n" % count)
      return count
         
   def CompleteProfile(self, handler, version):
      """ Fills all profile parameters which still are None with their default values. This should be called after loading a
         profile to have consistent data in it. Returns the number of modified entries. """
      count = 0
      
      try: fmt = FileParser.profileFormats[version]
      except KeyError:
         raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse profile.' % version)
         return 0
      
      #self._Log("Completing profile with default values according to version %s." % version)
      for var, type in fmt:
         if getattr(handler, var) == None:
            setattr(handler, var, getattr(ProfileSettings.Default(), var))
            count += 1
      
      self._Log("Completed profile by setting %i variables to their default values.\n" % count)
      return count
   
   def ParseByVersion(self, file, handler, version, type):
      """ Calls parse with the correct format specifier determind by version string (e.g. '0.1a') and type, which must be either
         'profile' or 'entry' to parse profile or entry settings, respectively. """
      self._Log("Requesting file format specifier for version '%s' (%s)." % (version, type))
      if type == 'profile':
         try: fmt = FileParser.profileFormats[version]
         except KeyError:
            raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse profile.' % version)
            return
      elif type == 'entry':
         try: fmt = FileParser.entryFormats[version]
         except KeyError:
            raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse entry.' % version)
            return
      else:
         raise ValueError('FileParser error: Invalid type argument for ParseByVersion: \'%s\' - must be \'profile\' or \'entry\'!' % type)
         return
      
      return self.Parse(file, handler, fmt)
      
   def Parse(self, file, handler, format):
      """ Parse file 'file' according to format specifier 'format' and store results in the object 'handler' via setattr.
          
          'file'    - handle to a file, already opened for reading, preferably with codecs.open to ensure the right codepage is used.
          
          'handler' - an arbitrary object, where parsing results will be stored via setattr, using the variable names specified
                      in 'format'.
                      
          'format'  - a list of (var, datatype) tuples which specify
                 var:             the variable name to store in handler
                 datatype:        function pointer to a casting function converting the input string to the desired data type
                                  (e.g. int, float).
                                  Can be a one-dimensional tuple (e.g. (int, int)), one line is read per tuple entry.
                                  DO NOT USE bool as datatype, use int instead!
                                  Be careful when using unicode-Strings in tuples, this might be bugged.
          If you want to use a specific file version format known to the FileParser class, use ParseByVersion instead! """
      for (var, datatype) in format:
         # check if datatype is a tuple
         if type(datatype) is TupleType:
            varList = []
            for subType in datatype:
               line = file.readline()
               self._Log("Parsed line: %s" % line.strip())
               try:
                  value = subType(line)
               except ValueError:
                  raise ValueError("Profile loading error:\nUnable to convert"\
                                    + " input line '%s' (%s) to type %s!\n" % (line, var, str(subType))\
                                    + "Profile might be corrupted.")
               if subType in (StringType, UnicodeType):
                  value = value.strip() # strip newline
               varList.append(value)
               
            setattr(handler, var, tuple(varList))
            self._Log("Set handler member variable '%s' to '" % var+ str(tuple(varList))+ "'.")
         else:
            line = file.readline()
            self._Log("Parsed line: %s" % line.strip())
            try:
               value = datatype(line)
            except ValueError:
               raise ValueError("Profile loading error:\nUnable to convert"\
                                 + " input line '%s' (%s) to type %s!\n" % (line, var, str(datatype))\
                                 + "Profile might be corrupted.")
            if datatype in (StringType, UnicodeType):
               value = value.strip() # strip newline

            setattr(handler, var, value)
            svalue = str(value) if datatype not in (StringType, UnicodeType) else value
            self._Log("Set handler member variable '%s' to '" % var+ svalue + "'.")
            
      self._Log("Finished parsing.\n")

   def WriteByVersion(self, file, handler, version, type):
      """ Calls write with the correct format specifier determind by version string (e.g. '0.1a') and type, which must be either
          'profile' or 'entry' to parse profile or entry settings, respectively. """
      self._Log("Requesting file format specifier for version '%s' (%s)." % (version, type))
      if type == 'profile':
         try: fmt = FileParser.profileFormats[version]
         except KeyError:
            raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse profile.' % version)
            return
      elif type == 'entry':
         try: fmt = FileParser.entryFormats[version]
         except KeyError:
            raise ValueError('FileParser error: Unknown file version specifier \'%s\'. Unable to parse entry.' % version)
            return
      else:
         raise ValueError('FileParser error: Invalid type argument for ParseByVersion: \'%s\' - must be \'profile\' or \'entry\'!' % type)
         return
      
      return self.Write(file, handler, fmt)
            
   def Write(self, file, handler, format):
      """ Write to file 'file' according to format specifier 'format' and attributes of the object 'handler' via getattr.
          
          'file'    - handle to a file, already opened for writing, preferably with codecs.open to ensure the right codepage is used.
          
          'handler' - an object storing all data that must be written in its member variables. 
                      
          'format'  - a list of (var, datatype) tuples which specify
                 var:             the handler's member variable name to access
                 datatype:        type of exported data, values might be casted into this type to prevent load/save issues.
                                  Can be a one-dimensional tuple (e.g. (int, int)), one line is written per tuple entry.
                                  DO NOT USE bool as datatype, use int instead!
          If you want to use a specific file version format known to the FileParser class, use WriteByVersion instead! """
      for (var, datatype) in format:
         try: v = getattr(handler, var)
         except NameError:
            raise NameError("FileParser error: Handler object has no member variable named '%s'!" % var)
            return
               
         # check if datatype is a tuple
         if type(datatype) is TupleType:
            for i in range(len(datatype)):
               try: vi = v[i]
               except IndexError:
                  raise IndexError("FileParser error: Handler object's tuple member variable '%s' has only %i entries, " % (var, len(v))\
                                   +" but index number %i was accessed." % i)
                  return
               
               try: cvi = datatype[i](vi) # cast to correct type, especially convert True/False to 1/0
               except ValueError, TypeError:
                  raise ValueError("FileParser error: Handler object's member variable '%s' can not be converted to " % var\
                                   +"its specified data type %s" % datatype[i])
                  return
               
               scvi = str(cvi) if datatype[i] not in (UnicodeType, StringType) else cvi
               scvis = scvi.strip()
               
               file.write(scvis)
               file.write('\n')
               
               self._Log("Wrote handler member variable '%s' as '" % var + scvis + "'.")
         else:
            try: cv = datatype(v) # cast to correct type, especially convert True/False to 1/0
            except ValueError, TypeError:
               raise ValueError("FileParser error: Handler object's member variable '%s' can not be converted to " % var\
                                +"its specified data type %s" % datatype)
               return
            
            scv = str(cv) if datatype not in (UnicodeType, StringType) else cv
            scvs = scv.strip()

            file.write(scvs)
            file.write('\n')
            self._Log("Wrote handler member variable '%s' as '" % var + scvs + "'.")
            
      self._Log("Finished writing.\n")
               
def flushLogfiles(list, codepage):
   for file in list:
      with codecs.open(file, 'w', codepage) as f:
         f.write("# -*- coding: %s -*-\n" % codepage)
         f.write(time.strftime(STAMPFORMAT) + "... *** Starting program, old logfile erased *** ...\n")
         f.write("\n")
         
def formatTime(time):
   """ Format a specified time (in seconds) into a nice printing format. """
   if time < 60.: return "< 1m"
   elif time < 20.*60: return "%im %is" % (time//60, time%60)
   elif time < 60.*60: return "%im" % (time//60)
   elif time < 20.*60*60: return "%ih %im" %  (time//3600, (time%3600)//60)
   elif time < 200.*60*60: return "%ih" % (time//3600)
   else: return "%id %ih" % (time//86400, (time%86400)//3600)

def din5007(input):
   """ This function implements sort keys for the german language according to 
   DIN 5007."""
   
   # key1: compare words lowercase and replace umlauts according to DIN 5007
   key1=input.lower()
   key1=key1.replace(u'\x84', "a")
   key1=key1.replace(u'\x94', "o")
   key1=key1.replace(u'\x81', "u")
   key1=key1.replace(u'\xE1', "ss")
   
   # key2: sort the lowercase word before the uppercase word and sort
   # the word with umlaut after the word without umlaut
   key2=input.swapcase()
   
   # in case two words are the same according to key1, sort the words
   # according to key2. 
   return (key1, key2)