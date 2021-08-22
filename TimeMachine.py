#!/usr/bin/python
import os
import subprocess
import sys, getopt
import json
import datetime
import requests
from datetime import tzinfo, timedelta, datetime, date
import lzma
import time
import pathlib
import glob
import hashlib
import base64

VerboseFlag = False
ConfigObj = False
ClearFlag = False

#------------------------------------------------------------------------------
# Common Functions
#------------------------------------------------------------------------------    
def IsLinux():  
  if os.name == 'nt':
    st = False
  else:
    st = True
  return st
  
def Exec(cmd):
  global VerboseFlag
  if VerboseFlag:
    print("Exec: %s" % (cmd))
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
  (output, err) = p.communicate()
  status = p.wait()
  if VerboseFlag:
    print(output)
    print("Status=%d" % (status))
  return status, output

def WriteTextFile(fn, text):
  fp = open(fn, "w")
  fp.write(text)
  fp.close()    

def ReadTextFile(fn):
  fp = open(fn, 'r')
  data = fp.read()  
  fp.close()
  return data
  
def DeleteFile(fn):
  if os.path.isfile(fn):
    os.remove(fn)

def MakeFolder(folder):
  if not os.path.exists(folder):
    os.makedirs(folder)

def MoveFile(src, dest):
  dir = os.path.dirname (dest)
  MakeFolder(dir)
  os.rename(src, dest)

def json_encode(data):
  return json.dumps(data, sort_keys=True, indent=4)
  
def json_decode(data):
  return json.loads(data)

def isset(variable):
  st = True
  try:
    variable
  except NameError:
    st = False
  return st
  
def ReadFileToArray(fn):
  with open(fn) as f:
    lines = f.readlines()
    f.close()
  return lines

def WriteArrayToFile(fn, lines):
  fo = open(fn, "w")
  line = fo.writelines(lines)
  fo.close()

def GetFileMTime(fn):
  mtime = os.stat(fn).st_mtime
  return mtime

def SetFileMTime(fn, mtime):
  os.utime(fn, (mtime, mtime))

def GetFileExtension(fn):
  filename, file_extension = os.path.splitext(fn)
  return file_extension

def RemoveComments(lbuf):
  p = lbuf.find("#")
  if p != -1:
    lbuf = lbuf[:p]
  return lbuf

#------------------------------------------------------------------------------
# Find functions
#------------------------------------------------------------------------------
def FindFileNest(spath, sfile, base, rpath):
  result = False
  dir = os.path.join (base, rpath)
  for file in os.listdir(dir):
    full = os.path.join (dir, file)
    if (os.path.isdir(full)):
      r = FindFileNest(spath, sfile, base, os.path.join(rpath, file))
      if r != False:
        result = r
        break
    else:
      if file == sfile and spath in full:
        result = full
  return result

def GetLineByTag(fn, tag):
  result = False
  lines = ReadFileToArray(fn)
  for line in lines:
    line = line.rstrip()
    if tag in line:
      result = line
      break
  return result
    
#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
def md5(str):
  return hashlib.md5(str.encode('utf-8')).hexdigest()

def LoadConfigFile():
  global ConfigFile
  global ConfigData
  global ConfigMD5
  if os.path.isfile(ConfigFile):
    jstr = ReadTextFile(ConfigFile)
    ConfigMD5 = md5(jstr)
    ConfigData = json_decode(jstr)
  else:
    ConfigData = {}
  
def SaveConfigFile():
  global ConfigFile
  global ConfigData  
  global ConfigMD5
  jstr = json_encode(ConfigData)
  save_md5 = md5(jstr)
  if ConfigMD5 != save_md5:
    WriteTextFile(ConfigFile, jstr)
    ConfigMD5 = save_md5
  
def GetFileSize(fn):
  return os.path.getsize(fn)

def GetFileTime(fn):
  mtime = os.path.getmtime(fn)
  return mtime

#------------------------------------------------------------------------------
# Config Class
#------------------------------------------------------------------------------
class CONFIG_CLASS:  
  def __init__(self, cfg_file, flags = 0):
    self.File = False
    if flags == 0:
      result = False
      folder = os.path.dirname(os.path.realpath(__file__))
      while True:
        temp = os.path.join(folder, cfg_file)
        if os.path.isfile(temp):
          result = temp
          break
        folder = os.path.dirname(folder)
        #
        # End the search if not found
        #
        pnode = os.path.basename(folder)
        if pnode == "www" or pnode == "media" or pnode == "mnt":
          break
      if result != False:
        self.File = result
        self.Load()
    if flags & 1:
      self.File = cfg_file
      self.Load()
      
  def Load(self):
    if self.File != False:
      if os.path.isfile(self.File):
        jstr = ReadTextFile(self.File)
      else:
        jstr = "{}"
      self.MD5 = md5(jstr)
      self.Data = json_decode(jstr)
      
  def Save(self):
    if self.File != False:
      new_jstr = json_encode(self.Data)
      new_md5 = md5(new_jstr)
      if self.MD5 != new_md5:
        WriteTextFile(self.File, new_jstr)
        self.MD5 = new_md5

#------------------------------------------------------------------------------
# Storage Class
#------------------------------------------------------------------------------
class STORAGE_CLASS:  
  def __init__(self, name, cfg_data):
    self.Name = name
    self.ConfigData = cfg_data
    self.ExcludeFile = "rsync_exclude.txt"
    if "Folder" not in self.ConfigData:
      self.ConfigData["Folder"] = "."
    if "TrackList" not in self.ConfigData:
      self.ConfigData["TrackList"] = []
    
  def TouchMarker(self, folder):  
    fn = os.path.join(folder, "backup.marker")
    if not os.path.exists(folder):
      os.makedirs(folder)
    if os.path.isfile(fn) == False:
      cmd = "touch %s" % (fn)
      Exec(cmd)    
    
  def SetFolder(self, folder):
    self.ConfigData["Folder"] = folder
    
  def FindTrack(self, input_folder):
    result = False    
    index = 0
    for trk in self.ConfigData["TrackList"]:
      if trk["Input"] == input_folder:
        result = index
        break
      index = index + 1
    return result
    
  def AddTrack(self, input_folder, output_folder):
    if self.FindTrack(input_folder) == False:
      tobj = {}
      tobj["Input"] = input_folder
      tobj["Output"] = output_folder
      self.ConfigData["TrackList"].append(tobj)

  def RemoveTrack(self, input_folder):
    index = self.FindTrack(input_folder)
    if index != -1:
      del self.ConfigData["TrackList"][index]
  
  def List(self):
    print("Name   = %s" % (self.Name))
    print("Folder = %s" % (self.ConfigData["Folder"]))
    for trk in self.ConfigData["TrackList"]:
      src = trk["Input"]
      dest = os.path.join(self.ConfigData["Folder"], trk["Output"])
      print("[%s] -> [%s]" % (src, dest))
      if "Tags" in trk:
        sort_orders = sorted(trk["Tags"].items(), key=lambda x: x[1])
        for i in sort_orders:
          print("%16s = %s" % (i[0], i[1]))        
        # for key in trk["Tags"]:
          # value = trk["Tags"][key]
          # print("[%s] -> [%s]" % (key, value)) 
          
  def Push(self, tag):
    index = 0
    for trk in self.ConfigData["TrackList"]:
      src = trk["Input"]
      dest = os.path.join(self.ConfigData["Folder"], trk["Output"])
      self.TouchMarker(dest)
      print("Track: [%s]" % (src))
      cmd = "bash rsync_tmbackup.sh %s %s %s" % (src, dest, self.ExcludeFile)
      # print(cmd)
      Exec(cmd)
      latest = os.path.join(dest, "latest")
      link = os.readlink(latest)
      if "Tags" not in trk:
        trk["Tags"] = {}
      trk["Tags"][tag] = link
      print("  Tag [%s] = %s" % (tag, link))
      index = index+1

  def Pop(self):
    target_tag = False
    for trk in self.ConfigData["TrackList"]:
      src = trk["Input"]
      # print("Track [%s]:" % (src))
      if "Tags" not in trk:
        trk["Tags"] = {}
      max_time = 0
      max_tag = False
      for tag in trk["Tags"]:
        timecode = int(trk["Tags"][tag].replace("-", ""))
        if timecode > max_time:
          max_time = timecode
          max_tag = tag
        #print("  Tag [%s] = %s" % (tag, timecode))
      # print("MaxTag [%s] = %s" % (max_tag, max_time))
      if target_tag == False:
        target_tag = max_tag
      elif target_tag != max_tag:
        print("Error: Tag mismatch [%s] [%s]" % (target_tag, max_tag))
        target_tag = False
        break
    if target_tag != False:
      self.Switch(target_tag)
      for trk in self.ConfigData["TrackList"]:
        del trk["Tags"][target_tag]
        
  def Switch(self, tag):
    index = 0
    for trk in self.ConfigData["TrackList"]:
      if "Tags" not in trk:
        trk["Tags"] = {}
      timecode = False
      if tag == "latest":
        timecode = "latest"
      elif tag in trk["Tags"]:
        timecode = trk["Tags"][tag]
      if timecode != False:
        src = os.path.join(self.ConfigData["Folder"], trk["Output"], timecode)
        dest = trk["Input"]
        print("Track [%s]: Switch to [%s]" % (dest, tag))
        cmd = "rsync -aP --delete %s/ %s" % (src, dest)
        # print(cmd)
        Exec(cmd)
      else:
        print("Error: Tag [%s] not found" % (tag))
        
#------------------------------------------------------------------------------
# Main 
#------------------------------------------------------------------------------
def Usage():
  print('python3 TimeMachine.py -a -v -t')
  print('   --push      Push')
  print('   --pop       Pop')
  print('   --switch    Switch')
  print('   --tag xxxx  Specific Tag Name')
  print('   -l          List')
  print('   -a          Add track into storage')
  print('   -r          Remove track from storage')
  print('   -s          Specific Storage Name')
  print('   -i xxxx     Specific input folder')
  print('   -o xxxx     Specific output folder')  
  print('   -t          Test')
  print('   -v          Verbose')
  print('Examples:')
  print('  1.Push a snap-shot with tag name')
  print('    TimeMachine.py --push --tag xyz')
  print('  2.Switch to snap-shot with tag name')
  print('    TimeMachine.py --swutch --tag xyz')

def main(argv):
  global VerboseFlag
  global ClearFlag
  global ConfigObj
  
  TestFlag = False
  ClearFlag = False
  StateFlag = False
  VerboseFlag = False
  TagName = False
  PushFlag = False
  PopFlag = False
  SwitchFlag = False
  ListFlag = False
  StorageName = "Default"
  StorageFolder = False
  InputFolder = False
  OutputFolder = False
  AddFlag = False
  RemoveFlag = False
  result = {}
  
  #
  # Load Config
  #
  cfg_file = os.path.realpath(__file__).replace(".py", ".cfg")
  ConfigObj = CONFIG_CLASS(cfg_file, 1)
  
  try:
    opts, args = getopt.getopt(argv,"vltarc:i:o:s:f:g",["list=","push", "pop", "switch", "tag="])
  except getopt.GetoptError:
    Usage()
    sys.exit(2)
  for opt, arg in opts:
    if opt == '-h':
      Usage()
      sys.exit()
    elif opt == "--host":             # Host
      Host = arg
    elif opt == "--push":             # Push
      PushFlag = True
    elif opt == "--pop":              # Pop
      PopFlag = True
    elif opt == "--switch":           # Switch
      SwitchFlag = True
    elif opt == "--tag":              # Set Tag Name
      TagName = arg
    elif opt == "-s":                 # Storage Name
      StorageName = arg
    elif opt == "-f":                 # Storage Folder
      StorageFolder = arg
    elif opt == "-a":                 # Add Track
      AddFlag = True
    elif opt == "-r":                 # Remove Track
      RemoveFlag = True
    elif opt == "-l":                 # List Tags
      ListFlag = True
    elif opt == "-i":                 # Input Folder
      InputFolder = arg
    elif opt == "-o":                 # Output Folder
      OutputFolder = arg
    elif opt == "-t":                 # Test Code
      TestFlag = True
    elif opt == "-v":                 # Verbose Flag
      VerboseFlag = True
    else:
      print (opt, arg)
  
  if VerboseFlag:
    print("State Flag   = %d" % (StateFlag))
    print("Test Flag    = %d" % (TestFlag))

  if "StorageList" not in ConfigObj.Data:
    ConfigObj.Data["StorageList"] = {}
    
  if StorageName not in ConfigObj.Data["StorageList"]:
    ConfigObj.Data["StorageList"][StorageName] = {}
    
  sobj = STORAGE_CLASS(StorageName, ConfigObj.Data["StorageList"][StorageName])  
  if StorageFolder != False:
    sobj.SetFolder(StorageFolder)

  #
  # Prcess Route
  #
  if TestFlag != False:
    if "Test" not in ConfigObj.Data["StorageList"]:
      ConfigObj.Data["StorageList"]["Test"] = {}
    sobj = STORAGE_CLASS("Test",ConfigObj.Data["StorageList"]["Test"])
    sobj.SetFolder("Database")
    sobj.AddTrack("/var/www", "www")
    sobj.AddTrack("/home/jimmy/MyWorks", "MyWorks")
  elif AddFlag != False:
    if InputFolder == False:
      print("Error: -i xxxxx is require")
      sys.exit()
    if OutputFolder == False:
      print("Error: -o xxxxx is require")
      sys.exit()
    sobj.AddTrack(InputFolder, OutputFolder)    
  elif RemoveFlag != False:
    if InputFolder == False:
      print("Error: -i xxxxx is require")
      sys.exit()
    sobj.RemoveTrack(InputFolder)
  elif PushFlag != False:
    if TagName == False:
      print("Error: --tag xxxxx is require")
      sys.exit()
    sobj.Push(TagName)
  elif PopFlag:
    sobj.Pop()
  elif SwitchFlag != False:
    if TagName == False:
      print("Error: --tag xxxxx is require")
      sys.exit()
    sobj.Switch(TagName)
  elif ListFlag != False:
    print("-------------------------------------------------------------------------------")
    for skey in ConfigObj.Data["StorageList"]:
      scfg = ConfigObj.Data["StorageList"][skey]
      sobj = STORAGE_CLASS(skey, scfg)
      sobj.List()     
      print("-------------------------------------------------------------------------------")
  else:
    pass

  #
  # Save Config
  #
  ConfigObj.Save()
  
if __name__ == "__main__":
   main(sys.argv[1:])
 
#------------------------------------------------------------------------------
# Clean
#------------------------------------------------------------------------------
#   State : clean 
#------------------------------------------------------------------------------
# Checking
#------------------------------------------------------------------------------
#   State : active, checking 
#   Check Status : 59% complete
