bl_info = {
    "name": "Helldivers 2 SDK: Community Edition",
    "version": (3, 4, 0),
    "blender": (4, 0, 0),
    "category": "Import-Export",
}

#region Imports

# System
import ctypes, os, tempfile, subprocess, time, webbrowser, shutil, datetime
import random as r
from copy import deepcopy
import copy
from math import ceil
from pathlib import Path
import mathutils
import os
import configparser
import requests
import json
import struct
import concurrent.futures
import zipfile
import shutil
import importlib

#import pyautogui 

# Blender
import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty, PointerProperty, CollectionProperty, FloatProperty, FloatVectorProperty
from bpy.types import Panel, Operator, PropertyGroup, Scene, Menu, OperatorFileListElement, UIList

# other addon code
from .stingray import animation as animation_m
from .stingray import raw_dump as raw_dump_m
from .stingray import material as material_m
from .stingray import texture as texture_m
from .stingray import particle as particle_m
from .stingray import bones as bones_m
from .stingray import composite_unit as composite_unit_m
from .stingray import unit as unit_m
from .stingray import state_machine as state_machine_m
from .utils import slim as slim_m
from .utils import hashing as hash_m
from .utils import memoryStream as memoryStream_m
from .utils import logger as logger_m
from .utils import constants as constants_m
from .utils import hd2_baker as hd2_baker_m

importlib.reload(constants_m)
importlib.reload(hd2_baker_m)
importlib.reload(memoryStream_m)
importlib.reload(logger_m)
importlib.reload(animation_m)
importlib.reload(raw_dump_m)
importlib.reload(material_m)
importlib.reload(texture_m)
importlib.reload(particle_m)
importlib.reload(bones_m)
importlib.reload(composite_unit_m)
importlib.reload(unit_m)
importlib.reload(hash_m)
importlib.reload(slim_m)
importlib.reload(state_machine_m)

from .stingray.animation import StingrayAnimation, AnimationException
from .stingray.raw_dump import StingrayRawDump
from .stingray.material import LoadShaderVariables, StingrayMaterial
from .stingray.texture import StingrayTexture
from .stingray.particle import StingrayParticles
from .stingray.state_machine import StingrayStateMachine
from .stingray.bones import LoadBoneHashes, StingrayBones
from .stingray.composite_unit import StingrayCompositeMesh
from .stingray.unit import CreateModel, GetObjectsMeshData, GetMeshData, StingrayMeshFile
from .utils.slim import is_slim_version, load_package, get_package_toc, slim_init

from .utils.hashing import murmur64_hash
from .utils.memoryStream import MemoryStream
from .utils.logger import PrettyPrint, SetLogFile, CloseLogFile
from .utils.constants import *
from .utils.hd2_baker import HD2Baker, has_hd2_shader, find_hd2_shader_node

#endregion

#region Global Variables

AddonPath = os.path.dirname(__file__)
import platform
Global_texconvbin        = "texconv" if platform.system() == "Linux" else "texconv.exe"
Global_texconvpath       = f"{AddonPath}/deps/{Global_texconvbin}"
Global_materialpath      = f"{AddonPath}/materials"
Global_typehashpath      = f"{AddonPath}/hashlists/typehash.txt"
Global_friendlynamespath = f"{AddonPath}/hashlists/friendlynames.txt"

Global_archivehashpath   = f"{AddonPath}/hashlists/archivehashes.json"
Global_variablespath     = f"{AddonPath}/hashlists/shadervariables.txt"
Global_bonehashpath      = f"{AddonPath}/hashlists/bonehash.txt"

Global_defaultgamepath   = "C:\Program Files (x86)\Steam\steamapps\common\Helldivers 2\data\ "
Global_defaultgamepath   = Global_defaultgamepath[:len(Global_defaultgamepath) - 1]
Global_gamepath          = ""
Global_gamepathIsValid   = False
Global_searchpath        = ""
Global_filediverpath     = ""
Global_filediverpathIsValid = False
Global_configpath        = f"{AddonPath}.ini"

Global_Foldouts = {}

Global_BoneNames = {}

Global_AnimationMapping = {}

Global_SectionHeader = "---------- Helldivers 2 ----------"

Global_randomID = ""

Global_latestVersionLink = "https://api.github.com/repos/Boxofbiscuits97/HD2SDK-CommunityEdition/releases/latest"
Global_addonUpToDate = None

Global_archieHashLink = "https://raw.githubusercontent.com/Boxofbiscuits97/HD2SDK-CommunityEdition/main/hashlists/archivehashes.json"

Global_previousRandomHash = 0

#endregion

#region Common Hashes & Lookups

TextureTypeLookup = {
    "original": (
        "PBR", 
        "", 
        "", 
        "", 
        "Bump Map", 
        "Normal", 
        "", 
        "Emission", 
        "Bump Map", 
        "Base Color", 
        "", 
        "", 
        ""
    ),
    "basic": (
        "PBR", 
        "Base Color", 
        "Normal"
    ),
    "basic+": (
        "PBR",
        "Base Color",
        "Normal"
    ),
    "emissive": (
        "Normal/AO/Roughness", 
        "Emission", 
        "Base Color/Metallic"
    ),
        "armorlut": (
        "Decal", 
        "", 
        "Pattern LUT", 
        "Normal", 
        "", 
        "", 
        "Pattern Mask", 
        "ID Mask Array", 
        "", 
        "Primary LUT", 
        "",
    ),
    "alphaclip": (
        "Normal/AO/Roughness",
        "Alpha Mask",
        "Base Color/Metallic"
    ),
    "alphaclip+": (
        "Normal/AO/Roughness",
        "Emission",
        "Base Color/Metallic",
        "Alpha Mask",
    ),
    "advanced": (
        "",
        "",
        "Normal/AO/Roughness",
        "Metallic",
        "",
        "Color/Emission Mask",
        "",
        "",
        "",
        "",
        ""
    ),
    "translucent": (
        "Normal",
    )
}

Global_Materials = (
        ("advanced", "Advanced", "A more comlpicated material, that is color, normal, emission and PBR capable which renders in the UI. Sourced from the Illuminate Overseer."),
        ("basic+", "Basic+", "A basic material with a color, normal, and PBR map which renders in the UI, Sourced from a SEAF NPC"),
        ("translucent", "Translucent", "A translucent with a solid set color and normal map. Sourced from the Terminid Larva Backpack."),
        ("alphaclip+", "Alpha Clip+", "A material that supports an alpha mask which does not render in the UI. Extra features with emission. Sourced from a bot bio processor."),
        ("alphaclip", "Alpha Clip", "A material that supports an alpha mask which does not render in the UI. Sourced from a skeleton pile"),
        ("original", "Original", "The original template used for all mods uploaded to Nexus prior to the addon's public release, which is bloated with additional unnecessary textures. Sourced from a terminid"),
        ("basic", "Basic", "A basic material with a color, normal, and PBR map. Sourced from a trash bag prop"),
        ("emissive", "Emissive", "A basic material with a color, normal, and emission map. Sourced from a vending machine"),
        ("armorlut", "Armor LUT", "An advanced material using multiple mask textures and LUTs to texture the mesh only advanced users should be using this. Sourced from the base game material on Armors"),
    )

#endregion

#region Functions: Miscellaneous

# 4.3 compatibility change
def CheckBlenderVersion():
    global OnCorrectBlenderVersion
    BlenderVersion = bpy.app.version
    OnCorrectBlenderVersion = (BlenderVersion[0] == 4 and BlenderVersion[1] <= 3)
    PrettyPrint(f"Blender Version: {BlenderVersion} Correct Version: {OnCorrectBlenderVersion}")

def CheckAddonUpToDate():
    PrettyPrint("Checking If Addon is up to date...")
    currentVersion = bl_info["version"]
    try:
        req = requests.get(Global_latestVersionLink, timeout=5)
        req.raise_for_status()  # Check if the request is successful.
        if req.status_code == requests.codes.ok:
            req = req.json()
            latestVersion = req['tag_name'].replace("v", "").replace("-", ".").split(".")
            latestVersion = (int(latestVersion[0]), int(latestVersion[1]), int(latestVersion[2]))
            
            PrettyPrint(f"Current Version: {currentVersion}")
            PrettyPrint(f"Latest Version: {latestVersion}")

            global Global_addonUpToDate
            global Global_latestAddonVersion
            if latestVersion[0] > currentVersion[0]:
                Global_addonUpToDate = False
            elif latestVersion[0] == currentVersion[0] and latestVersion[1] > currentVersion[1]:
                Global_addonUpToDate = False
            elif latestVersion[0] == currentVersion[0] and latestVersion[1] == currentVersion[1] and latestVersion[2] > currentVersion[2]:
                Global_addonUpToDate = False
            else:
                Global_addonUpToDate = True
            Global_latestAddonVersion = f"{latestVersion[0]}.{latestVersion[1]}.{latestVersion[2]}"
            if Global_addonUpToDate:
                PrettyPrint("Addon is up to date!")
            else:
                PrettyPrint("Addon is outdated!")
        else:
            PrettyPrint(f"Request Failed, Cannot check latest Version. Status: {req.status_code}", "warn")
    except requests.ConnectionError:
        PrettyPrint("Connection failed. Please check your network settings.", "warn")
    except requests.HTTPError as err:
        PrettyPrint(f"HTTP error occurred: {err}", "warn")
        
def UpdateArchiveHashes():
    try:
        req = requests.get(Global_archieHashLink)
        req.raise_for_status()  # Check if the request is successful.
        if req.status_code == requests.codes.ok:
            file = open(Global_archivehashpath, "w")
            file.write(req.text)
            PrettyPrint(f"Updated Archive Hashes File")
        else:
            PrettyPrint(f"Request Failed, Could not update Archive Hashes File", "warn")
    except requests.ConnectionError:
        PrettyPrint("Connection failed. Please check your network settings.", "warn")
    except requests.HTTPError as err:
        PrettyPrint(f"HTTP error occurred: {err}", "warn")

def EntriesFromStrings(file_id_string, type_id_string):
    FileIDs = file_id_string.split(',')
    TypeIDs = type_id_string.split(',')
    Entries = []
    for n in range(len(FileIDs)):
        if FileIDs[n] != "":
            Entries.append(Global_TocManager.GetEntry(int(FileIDs[n]), int(TypeIDs[n])))
    return Entries

def EntriesFromString(file_id_string, TypeID):
    FileIDs = file_id_string.split(',')
    Entries = []
    for n in range(len(FileIDs)):
        if FileIDs[n] != "":
            Entries.append(Global_TocManager.GetEntry(int(FileIDs[n]), int(TypeID)))
    return Entries

def IDsFromString(file_id_string):
    FileIDs = file_id_string.split(',')
    Entries = []
    for n in range(len(FileIDs)):
        if FileIDs[n] != "":
            Entries.append(int(FileIDs[n]))
    return Entries

def GetDisplayData():
    # Set display archive TODO: Global_TocManager.LastSelected Draw Index could be wrong if we switch to patch only mode, that should be fixed
    DisplayTocEntries = []
    DisplayTocTypes   = []
    DisplayArchive = Global_TocManager.ActiveArchive
    if bpy.context.scene.Hd2ToolPanelSettings.PatchOnly:
        if Global_TocManager.ActivePatch != None:
            DisplayTocEntries = []
            for entry_type, entries in Global_TocManager.ActivePatch.TocDict.items():
                DisplayTocEntries.extend([[Entry, True] for Entry in entries.values()])
            DisplayTocTypes   = Global_TocManager.ActivePatch.TocTypes
    elif Global_TocManager.ActiveArchive != None:
        DisplayTocEntries = []
        for entry_type, entries in Global_TocManager.ActiveArchive.TocDict.items():
            DisplayTocEntries.extend([[Entry, False] for Entry in entries.values()])
        DisplayTocTypes   = [Type for Type in Global_TocManager.ActiveArchive.TocTypes]
        AddedTypes   = [Type.TypeID for Type in DisplayTocTypes]
        AddedEntries = [Entry[0].FileID for Entry in DisplayTocEntries]
        if Global_TocManager.ActivePatch != None:
            for Type in Global_TocManager.ActivePatch.TocTypes:
                if Type.TypeID not in AddedTypes:
                    AddedTypes.append(Type.TypeID)
                    DisplayTocTypes.append(Type)
            for entry_type, entries in Global_TocManager.ActivePatch.TocDict.items(): # this seems wrong
                for Entry in entries.values():
                    if Entry.FileID not in AddedEntries:
                        AddedEntries.append(Entry.FileID)
                        DisplayTocEntries.append([Entry, True])
    return [DisplayTocEntries, DisplayTocTypes]

def SaveUnsavedEntries(self):
    for entries in list(Global_TocManager.ActivePatch.TocDict.values()):
        for entry in list(entries.values()):
            if not entry.IsModified:
                Global_TocManager.Save(int(entry.FileID), entry.TypeID)
                PrettyPrint(f"Saved {int(entry.FileID)}")

def RandomHash16():
    global Global_previousRandomHash
    hash = Global_previousRandomHash
    while hash == Global_previousRandomHash:
        r.seed(datetime.datetime.now().timestamp())
        hash = r.randint(1, 0xffffffffffffffff)
    Global_previousRandomHash = hash
    PrettyPrint(f"Generated hash: {hash}")
    return hash
#endregion

#region Functions: Stingray Hashing

def GetTypeNameFromID(ID):
    for hash_info in Global_TypeHashes:
        if int(ID) == hash_info[0]:
            return hash_info[1]
    return "unknown"

def GetIDFromTypeName(Name):
    for hash_info in Global_TypeHashes:
        if hash_info[1] == Name:
            return int(hash_info[0])
    return None

def GetFriendlyNameFromID(ID):
    for hash_info in Global_NameHashes:
        if int(ID) == hash_info[0]:
            if hash_info[1] != "":
                return hash_info[1]
    return str(ID)

def GetArchiveNameFromID(EntryID):
    for hash in Global_ArchiveHashes:
        if hash[0] == EntryID:
            return hash[1]
    return ""

def GetArchiveIDFromName(Name):
    for hash in Global_ArchiveHashes:
        if hash[1] == Name:
            return hash[0]
    return ""

def HasFriendlyName(ID):
    for hash_info in Global_NameHashes:
        if int(ID) == hash_info[0]:
            return True
    return False

def AddFriendlyName(ID, Name):
    Global_TocManager.SavedFriendlyNames = []
    Global_TocManager.SavedFriendlyNameIDs = []
    for hash_info in Global_NameHashes:
        if int(ID) == hash_info[0]:
            hash_info[1] = str(Name)
            return
    Global_NameHashes.append([int(ID), str(Name)])
    SaveFriendlyNames()

def SaveFriendlyNames():
    with open(Global_friendlynamespath, 'w') as f:
        for hash_info in Global_NameHashes:
            if hash_info[1] != "":
                string = str(hash_info[0]) + " " + str(hash_info[1])
                f.writelines(string+"\n")

#endregion

#region Functions: Initialization

Global_TypeHashes = []
def LoadTypeHashes():
    with open(Global_typehashpath, 'r') as f:
        for line in f.readlines():
            parts = line.split(" ")
            Global_TypeHashes.append([int(parts[0], 16), parts[1].replace("\n", "")])

Global_NameHashes = []
def LoadNameHashes():
    Loaded = []
    with open(Global_friendlynamespath, 'r') as f:
        for line in f.readlines():
            parts = line.split(" ", 1)
            if int(parts[0]) not in Loaded:
                Global_NameHashes.append([int(parts[0]), parts[1].replace("\n", "")])
                Loaded.append(int(parts[0]))

Global_ArchiveHashes = []
def LoadHash(path, title):
    with open(path, 'r') as f:
        for line in f.readlines():
            parts = line.split(" ", 1)
            Global_ArchiveHashes.append([parts[0], title + parts[1].replace("\n", "")])
                
def LoadArchiveHashes():
    file = open(Global_archivehashpath, "r")
    data = json.load(file)

    for title in data:
        for innerKey in data[title]:
            Global_ArchiveHashes.append([innerKey, title + ": " + data[title][innerKey]])

    Global_ArchiveHashes.append([BaseArchiveHexID, "SDK: Base Patch Archive"])

def GetEntryParentMaterialID(entry):
    if entry.TypeID == MaterialID:
        f = MemoryStream(entry.TocData)
        for i in range(6):
            f.uint32(0)
        parentID = f.uint64(0)
        return parentID
    else:
        raise Exception(f"Entry: {entry.FileID} is not a material")

#endregion

#region Temp Folder Helper

def get_temp_folder():
    """Get the temp folder using Blender's temp directory."""
    temp_folder = os.path.join(bpy.app.tempdir, "HD2SDK")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    return temp_folder

#endregion

#region Configuration

def InitializeConfig():
    global Global_gamepath, Global_searchpath, Global_configpath, Global_gamepathIsValid
    global Global_filediverpath, Global_filediverpathIsValid
    if os.path.exists(Global_configpath):
        config = configparser.ConfigParser()
        config.read(Global_configpath, encoding='utf-8')
        try:
            Global_gamepath = config['DEFAULT']['filepath']
            Global_searchpath = config['DEFAULT']['searchpath']
        except:
            UpdateConfig()
        try:
            Global_filediverpath = config['DEFAULT'].get('filediverpath', '')
        except:
            pass
        if os.path.exists(Global_gamepath):
            PrettyPrint(f"Loaded Data Folder: {Global_gamepath}")
            slim_init(Global_gamepath)
            Global_gamepathIsValid = True
        else:
            PrettyPrint(f"Game path: {Global_gamepath} is not a valid directory", 'ERROR')
            Global_gamepathIsValid = False
        # Validate filediver path
        filediver_exe = os.path.join(Global_filediverpath, "filediver.exe")
        if Global_filediverpath and os.path.exists(filediver_exe):
            PrettyPrint(f"Loaded Filediver Path: {Global_filediverpath}")
            Global_filediverpathIsValid = True
        else:
            Global_filediverpathIsValid = False

    else:
        UpdateConfig()

def UpdateConfig():
    global Global_gamepath, Global_searchpath, Global_defaultgamepath, Global_gamepathIsValid
    global Global_filediverpath
    if Global_gamepath == "":
        Global_gamepath = Global_defaultgamepath
    if Global_gamepathIsValid:
        slim_init(Global_gamepath)
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'filepath': Global_gamepath,
        'searchpath': Global_searchpath,
        'filediverpath': Global_filediverpath
    }
    with open(Global_configpath, 'w') as configfile:
        config.write(configfile)
    
#endregion

#region Classes and Functions: Stingray Archives

class TocEntry:

    def __init__(self):
        self.FileID = self.TypeID = self.TocDataOffset = self.Unknown1 = self.GpuResourceOffset = self.Unknown2 = self.TocDataSize = self.GpuResourceSize = self.EntryIndex = self.StreamSize = self.StreamOffset = 0
        self.Unknown3 = 16
        self.Unknown4 = 64

        self.TocData =  self.TocData_OLD = b""
        self.GpuData =  self.GpuData_OLD = b""
        self.StreamData =  self.StreamData_OLD = b""

        # Custom Dev stuff
        self.LoadedData = None
        self.IsLoaded   = False
        self.IsModified = False
        self.IsCreated  = False # custom created, can be removed from archive
        self.IsSelected = False
        self.MaterialTemplate = None # for determining tuple to use for labeling textures in the material editor
        self.DEV_DrawIndex = -1

    # -- Serialize TocEntry -- #
    def Serialize(self, TocFile: MemoryStream, Index=0):
        self.FileID             = TocFile.uint64(self.FileID)
        self.TypeID             = TocFile.uint64(self.TypeID)
        self.TocDataOffset      = TocFile.uint64(self.TocDataOffset)
        self.StreamOffset       = TocFile.uint64(self.StreamOffset)
        self.GpuResourceOffset  = TocFile.uint64(self.GpuResourceOffset)
        self.Unknown1           = TocFile.uint64(self.Unknown1)
        self.Unknown2           = TocFile.uint64(self.Unknown2)
        self.TocDataSize        = TocFile.uint32(len(self.TocData))
        self.StreamSize         = TocFile.uint32(len(self.StreamData))
        self.GpuResourceSize    = TocFile.uint32(len(self.GpuData))
        self.Unknown3           = TocFile.uint32(self.Unknown3)
        self.Unknown4           = TocFile.uint32(self.Unknown4)
        self.EntryIndex         = TocFile.uint32(Index)
        return self

    # -- Write TocEntry Data -- #
    def SerializeData(self, TocFile: MemoryStream, GpuFile, StreamFile):
        if TocFile.IsWriting():
            self.TocDataOffset = TocFile.tell()
        if self.TocDataSize > 0:
            if TocFile.IsReading():
                TocFile.seek(self.TocDataOffset)
                self.TocData = bytearray(self.TocDataSize)
            self.TocData = TocFile.bytes(self.TocData)

        if GpuFile.IsWriting(): self.GpuResourceOffset = ceil(float(GpuFile.tell())/64)*64
        if self.GpuResourceSize > 0:
            GpuFile.seek(self.GpuResourceOffset)
            if GpuFile.IsReading(): self.GpuData = bytearray(self.GpuResourceSize)
            self.GpuData = GpuFile.bytes(self.GpuData)

        if StreamFile.IsWriting(): self.StreamOffset = ceil(float(StreamFile.tell())/64)*64
        if self.StreamSize > 0:
            StreamFile.seek(self.StreamOffset)
            if StreamFile.IsReading(): self.StreamData = bytearray(self.StreamSize)
            self.StreamData = StreamFile.bytes(self.StreamData)
        if GpuFile.IsReading():
            self.TocData_OLD    = bytearray(self.TocData)
            self.GpuData_OLD    = bytearray(self.GpuData)
            self.StreamData_OLD = bytearray(self.StreamData)

    # -- Get Data -- #
    def GetData(self):
        return [self.TocData, self.GpuData, self.StreamData]
    # -- Set Data -- #
    def SetData(self, TocData, GpuData, StreamData, IsModified=True):
        self.TocData = TocData
        self.GpuData = GpuData
        self.StreamData = StreamData
        self.TocDataSize     = len(self.TocData)
        self.GpuResourceSize = len(self.GpuData)
        self.StreamSize      = len(self.StreamData)
        self.IsModified = IsModified
    # -- Undo Modified Data -- #
    def UndoModifiedData(self):
        self.TocData = bytearray(self.TocData_OLD)
        self.GpuData = bytearray(self.GpuData_OLD)
        self.StreamData = bytearray(self.StreamData_OLD)
        self.TocDataSize     = len(self.TocData)
        self.GpuResourceSize = len(self.GpuData)
        self.StreamSize      = len(self.StreamData)
        self.IsModified = False
        if self.IsLoaded:
            self.Load(True, False)
    # -- Load Data -- #
    def Load(self, Reload=False, MakeBlendObject=True, LoadMaterialSlotNames=False):
        callback = None
        if self.TypeID == UnitID: callback = LoadStingrayUnit
        if self.TypeID == TexID: callback = LoadStingrayTexture
        if self.TypeID == MaterialID: callback = LoadStingrayMaterial
        if self.TypeID == ParticleID: callback = LoadStingrayDump
        if self.TypeID == CompositeUnitID: callback = LoadStingrayCompositeUnit
        if self.TypeID == BoneID: callback = LoadStingrayBones
        if self.TypeID == AnimationID: callback = LoadStingrayAnimation
        if self.TypeID == StateMachineID: callback = LoadStingrayStateMachine
        if callback == None: callback = LoadStingrayDump

        if callback != None:
            if self.TypeID == UnitID:
                self.LoadedData = callback(self.FileID, self.TocData, self.GpuData, self.StreamData, Reload, MakeBlendObject, LoadMaterialSlotNames)
            else:
                self.LoadedData = callback(self.FileID, self.TocData, self.GpuData, self.StreamData, Reload, MakeBlendObject)
            if self.LoadedData == None: raise Exception("Archive Entry Load Failed")
            self.IsLoaded = True

    # -- Write Data -- #
    def Save(self, **kwargs):
        callback = None
        if not self.IsLoaded: self.Load(True, False)
        if self.TypeID == UnitID: callback = SaveStingrayUnit
        if self.TypeID == TexID: callback = SaveStingrayTexture
        if self.TypeID == MaterialID: callback = SaveStingrayMaterial
        if self.TypeID == ParticleID: callback = SaveStingrayDump
        if self.TypeID == AnimationID: callback = SaveStingrayAnimation
        if self.TypeID == BoneID: callback = SaveStingrayBones
        if self.TypeID == StateMachineID: callback = SaveStingrayStateMachine
        if callback == None: callback = SaveStingrayDump

        if self.IsLoaded:
            if self.TypeID == UnitID:
                BlenderOpts = kwargs.get("BlenderOpts")
                data = callback(self, self.FileID, self.TocData, self.GpuData, self.StreamData, self.LoadedData, BlenderOpts)
            else:
                data = callback(self, self.FileID, self.TocData, self.GpuData, self.StreamData, self.LoadedData)
            self.SetData(data[0], data[1], data[2])
        return True

class TocFileType:
    def __init__(self, ID=0, NumFiles=0):
        self.unk1     = 0
        self.TypeID   = ID
        self.NumFiles = NumFiles
        self.unk2     = 16
        self.unk3     = 64
    def Serialize(self, TocFile: MemoryStream):
        self.unk1     = TocFile.uint64(self.unk1)
        self.TypeID   = TocFile.uint64(self.TypeID)
        self.NumFiles = TocFile.uint64(self.NumFiles)
        self.unk2     = TocFile.uint32(self.unk2)
        self.unk3     = TocFile.uint32(self.unk3)
        return self


class SearchToc:
    def __init__(self):
        self.TocEntries = {}
        self.fileIDs = []
        self.Path = ""
        self.Name = ""

    def HasEntry(self, file_id, type_id):
        file_id = int(file_id)
        type_id = int(type_id)
        try:
            return file_id in self.TocEntries[type_id]
        except KeyError:
            return False
            
    def FromPackage(self, package_data, package_name):
        self.UpdatePath(os.path.join(Global_gamepath, package_name))
        num_entries = int.from_bytes(package_data[8:12], "little")
        for i in range(num_entries):
            offset = 0x10+i*0x10
            type_id = int.from_bytes(package_data[offset:offset+8], "little")
            file_id = int.from_bytes(package_data[offset+8:offset+16], "little")
            self.fileIDs.append(file_id)
            try:
                self.TocEntries[type_id].append(file_id)
            except KeyError:
                self.TocEntries[type_id] = [file_id]
        return True
        
    def FromSlimFile(self, path):
        self.UpdatePath(path)
        data = get_package_toc(path)
        if not data:
            PrettyPrint(f"unable to get package {os.path.basename(path)}", 'warn')
            return False
        magic, numTypes, numFiles = struct.unpack_from("<III", data, offset=0)
        if magic != 4026531857:
            PrettyPrint(f"Incorrect magic in package {os.path.basename(path)}: {magic}", 'error')
            return False
        # maybe could save files for later?
        offset = 72 + (numTypes << 5)
        
        for _ in range(numFiles):
            file_id, type_id, toc_data_offset = struct.unpack_from("<QQQ", data, offset=offset)
            self.fileIDs.append(int(file_id))
            try:
                self.TocEntries[type_id].append(file_id)
            except KeyError:
                self.TocEntries[type_id] = [file_id]
            offset += 80
            
        return True

    def FromFile(self, path):
        self.UpdatePath(path)
        bin_data = b""
        file = open(path, 'r+b')
        bin_data = file.read(12)
        magic, numTypes, numFiles = struct.unpack("<III", bin_data)
        if magic != 4026531857:
            file.close()
            return False

        offset = 60 + (numTypes << 5)
        bin_data = file.read(offset + 80 * numFiles)
        file.close()
        for _ in range(numFiles):
            file_id, type_id = struct.unpack_from("<QQ", bin_data, offset=offset)
            self.fileIDs.append(int(file_id))
            try:
                self.TocEntries[type_id].append(file_id)
            except KeyError:
                self.TocEntries[type_id] = [file_id]
            offset += 80
        return True

    def UpdatePath(self, path):
        self.Path = path
        self.Name = Path(path).name

class StreamToc:
    def __init__(self):
        self.magic      = self.numTypes = self.numFiles = self.unknown = 0
        self.unk4Data   = bytearray(56)
        self.TocTypes   = []
        self.TocEntries = []
        self.TocDict = {}
        self.Path = ""
        self.Name = ""
        self.LocalName = ""

    def Serialize(self, SerializeData=True):
        # Create Toc Types Structs
        if self.TocFile.IsWriting():
            self.UpdateTypes()
        # Begin Serializing file
        if len(self.TocFile.Data) == 0 and self.TocFile.IsReading(): return False
        self.magic      = self.TocFile.uint32(self.magic)
        if self.magic != 4026531857: return False

        self.numTypes   = self.TocFile.uint32(len(self.TocTypes))
        if self.TocFile.IsReading():
            self.numFiles   = self.TocFile.uint32(len(self.TocEntries))
        else:
            self.numFiles   = self.TocFile.uint32(sum([len(entries.keys()) for entries in self.TocDict.values()]))
        self.unknown    = self.TocFile.uint32(self.unknown)
        self.unk4Data   = self.TocFile.bytes(self.unk4Data, 56)

        if self.TocFile.IsReading():
            self.TocTypes   = [TocFileType() for n in range(self.numTypes)]
            self.TocEntries = [TocEntry() for n in range(self.numFiles)]
        # serialize Entries in correct order
        self.TocTypes   = [Entry.Serialize(self.TocFile) for Entry in self.TocTypes]
        TocEntryStart   = self.TocFile.tell()
        if self.TocFile.IsReading():
            self.TocEntries = [Entry.Serialize(self.TocFile) for Entry in self.TocEntries]
            for entry in self.TocEntries:
                try:
                    self.TocDict[entry.TypeID][entry.FileID] = entry
                except KeyError:
                    self.TocDict[entry.TypeID] = {}
                    self.TocDict[entry.TypeID][entry.FileID] = entry
        else:
            Index = 1
            for Type in self.TocTypes:
                for Entry in self.TocDict[Type.TypeID].values():
                    Entry.Serialize(self.TocFile, Index)
                    Index += 1

        # Serialize Data
        if SerializeData:
            for entry_type, entries in self.TocDict.items():
                for FileEntry in entries.values():
                    FileEntry.SerializeData(self.TocFile, self.GpuFile, self.StreamFile)

        # re-write toc entry info with updated offsets
        if self.TocFile.IsWriting():
            self.TocFile.seek(TocEntryStart)
            Index = 1
            for Type in self.TocTypes:
                for Entry in self.TocDict[Type.TypeID].values():
                    Entry.Serialize(self.TocFile, Index)
                    Index += 1
        return True

    def UpdateTypes(self):
        self.TocTypes = [TocFileType(type_id, len(self.TocDict[type_id])) for type_id in self.TocDict.keys()]

    def UpdatePath(self, path):
        self.Path = path
        self.Name = Path(path).name

    def FromFile(self, path, SerializeData=True):
        self.UpdatePath(path)
        toc_data, gpu_data, stream_data = load_package(path)
        self.TocFile = MemoryStream(toc_data)
        self.GpuFile = MemoryStream(gpu_data)
        self.StreamFile = MemoryStream(stream_data)
        return self.Serialize(SerializeData)

    def ToFile(self, path=None):
        self.TocFile = MemoryStream(IOMode = "write")
        self.GpuFile = MemoryStream(IOMode = "write")
        self.StreamFile = MemoryStream(IOMode = "write")
        self.Serialize()
        if path == None: path = self.Path
        num_entries = sum([len(self.TocDict[k]) for k in self.TocDict.keys()])
        min_size = 256 * num_entries
        if len(self.TocFile.Data) < min_size:
            self.TocFile.Data.extend(bytearray(min_size-len(self.TocFile.Data)))

        with open(path, 'w+b') as f:
            f.write(bytes(self.TocFile.Data))
        with open(path+".gpu_resources", 'w+b') as f:
            f.write(bytes(self.GpuFile.Data))
        with open(path+".stream", 'w+b') as f:
            f.write(bytes(self.StreamFile.Data))

    def GetFileData(self, FileID, TypeID):
        try:
            return self.TocDict[TypeID][FileID].GetData()
        except KeyError:
            return None
    def GetEntry(self, FileID, TypeID):
        TypeID = int(TypeID)
        FileID = int(FileID)
        try:
            return self.TocDict[TypeID][FileID]
        except KeyError:
            return None
    def AddEntry(self, NewEntry, override=False):
        if not override and self.GetEntry(NewEntry.FileID, NewEntry.TypeID) != None:
            raise Exception("Entry with same ID already exists")
        try:
            self.TocDict[NewEntry.TypeID][NewEntry.FileID] = NewEntry
        except KeyError:
            self.TocDict[NewEntry.TypeID] = {}
            self.TocDict[NewEntry.TypeID][NewEntry.FileID] = NewEntry
        LoadEntryLists()
        self.UpdateTypes()
    def RemoveEntry(self, FileID, TypeID):
        try:
            del self.TocDict[TypeID][FileID]
            LoadEntryLists()
            self.UpdateTypes()
        except KeyError:
            pass

class TocManager():
    def __init__(self):
        self.SearchArchives  = []
        self.LoadedArchives  = []
        self.ActiveArchive   = None
        self.Patches         = []
        self.ActivePatch     = None

        self.CopyBuffer      = []
        self.SelectedEntries = []
        self.DrawChain       = []
        self.LastSelected = None # Last Entry Manually Selected
        self.SavedFriendlyNames   = []
        self.SavedFriendlyNameIDs = []
    #________________________#
    # ---- Archive Code ---- #
    def LoadArchive(self, path, SetActive=True, IsPatch=False):
        # TODO: Add error if IsPatch is true but the path is not to a patch
        for Archive in self.LoadedArchives:
            if Archive.Path == path:
                return Archive
        archiveID = path.replace(Global_gamepath, '')
        archiveName = GetArchiveNameFromID(archiveID)
        PrettyPrint(f"Loading Archive: {archiveID} {archiveName}")
        toc = StreamToc()
        toc.FromFile(path)
        
        # add to global animation mapping:
        global Global_AnimationMapping
        if toc.TocDict.get(StateMachineID, None):
            for state_machine in toc.TocDict[StateMachineID].values():
                if not state_machine.IsLoaded:
                    state_machine.Load(False, False)
                for animation_id in state_machine.LoadedData.animation_ids:
                    try:
                        Global_AnimationMapping[animation_id].add(state_machine.FileID)
                    except KeyError:
                        Global_AnimationMapping[animation_id] = set()
                        Global_AnimationMapping[animation_id].add(state_machine.FileID)
        
        if SetActive and not IsPatch:
            unloadEmpty = bpy.context.scene.Hd2ToolPanelSettings.UnloadEmptyArchives and bpy.context.scene.Hd2ToolPanelSettings.EnableTools
            if unloadEmpty:
                if self.ArchiveNotEmpty(toc):
                    self.LoadedArchives.append(toc)
                    self.SetActive(toc)
                else:
                    PrettyPrint(f"Unloading {archiveID} as it is Empty")
            else:
                self.LoadedArchives.append(toc)
                self.SetActive(toc)
                bpy.context.scene.Hd2ToolPanelSettings.LoadedArchives = archiveID
        elif SetActive and IsPatch:
            self.Patches.append(toc)
            self.SetActivePatch(toc)
            material_entries = self.ActivePatch.TocDict.get(MaterialID, {})
            for entry in material_entries.values():
                ID = GetEntryParentMaterialID(entry)
                if ID in Global_MaterialParentIDs:
                    entry.MaterialTemplate = Global_MaterialParentIDs[ID]
                    entry.Load()
                    PrettyPrint(f"Creating Material: {entry.FileID} Template: {entry.MaterialTemplate}")
                else:
                    PrettyPrint(f"Material: {entry.FileID} Parent ID: {ID} is not an custom material, skipping.")
        else:
            self.LoadedArchives.append(toc)

        # Get search archives
        if len(self.SearchArchives) == 0:
            if is_slim_version():
                futures = []
                tocs = []
                executor = concurrent.futures.ThreadPoolExecutor()
                bundle_database = open(os.path.join(Global_gamepath, "bundle_database.data"), 'rb')
                bundle_database_data = bundle_database.read()
                num_packages = int.from_bytes(bundle_database_data[4:8], "little")
                for i in range(num_packages):
                    offset = 0x10 + 0x33 * i
                    name = bundle_database_data[offset:offset+0x33].decode().split("\x17")[0]
                    search_toc = SearchToc()
                    tocs.append(search_toc)
                    futures.append(executor.submit(search_toc.FromSlimFile, os.path.join(Global_gamepath, name)))
                for index, future in enumerate(futures):
                    if future.result():
                        self.SearchArchives.append(tocs[index])
                executor.shutdown()
            else:
                futures = []
                tocs = []
                executor = concurrent.futures.ThreadPoolExecutor()
                for root, dirs, files in os.walk(Path(path).parent):
                    for name in files:
                        if Path(name).suffix == "":
                            search_toc = SearchToc()
                            tocs.append(search_toc)
                            futures.append(executor.submit(search_toc.FromFile, os.path.join(root, name)))
                for index, future in enumerate(futures):
                    if future.result():
                        self.SearchArchives.append(tocs[index])
                executor.shutdown()
        return toc
    
    def GetEntryByLoadArchive(self, FileID: int, TypeID: int):
        return self.GetEntry(FileID, TypeID, SearchAll=True, IgnorePatch=True)
    
    def ArchiveNotEmpty(self, toc):
        hasMaterials = toc.TocDict.get(MaterialID, None) and len(toc.TocDict[MaterialID]) > 0
        hasTextures = toc.TocDict.get(TexID, None) and len(toc.TocDict[TexID]) > 0
        hasMeshes = (toc.TocDict.get(UnitID, None) and len(toc.TocDict[UnitID]) > 0) or (toc.TocDict.get(CompositeUnitID, None) and len(toc.TocDict[CompositeUnitID]) > 0)
        return hasMaterials or hasTextures or hasMeshes

    def UnloadArchives(self):
        # TODO: Make sure all data gets unloaded...
        # some how memory can still be too high after calling this
        self.LoadedArchives = []
        self.ActiveArchive  = None
        self.SearchArchives = []
    
    def UnloadPatches(self):
        self.Patches = []
        self.SetActivePatch(None)

    def BulkLoad(self, list):
        if bpy.context.scene.Hd2ToolPanelSettings.UnloadPatches:
            self.UnloadArchives()
        for itemPath in list:
            Global_TocManager.LoadArchive(itemPath)

    def SetActive(self, Archive):
        if Archive != self.ActiveArchive:
            self.ActiveArchive = Archive
            LoadEntryLists()

    def SetActiveByName(self, Name):
        for Archive in self.LoadedArchives:
            if Archive.Name == Name:
                self.SetActive(Archive)

    #______________________#
    # ---- Entry Code ---- #
    def GetEntry(self, FileID, TypeID, SearchAll=False, IgnorePatch=False):
        # Check Active Patch
        if not IgnorePatch and self.ActivePatch != None:
            Entry = self.ActivePatch.GetEntry(FileID, TypeID)
            if Entry != None:
                return Entry
        # Check Active Archive
        if self.ActiveArchive != None:
            Entry = self.ActiveArchive.GetEntry(FileID, TypeID)
            if Entry != None:
                return Entry
        # Check All Loaded Archives
        for Archive in self.LoadedArchives:
            Entry = Archive.GetEntry(FileID, TypeID)
            if Entry != None:
                return Entry
        # Check All Search Archives
        if SearchAll:
            for Archive in self.SearchArchives:
                if Archive.HasEntry(FileID, TypeID):
                    return self.LoadArchive(Archive.Path, False).GetEntry(FileID, TypeID)
            PrettyPrint(f"Could not find entry of FileID: {FileID} TypeID: {TypeID}")
        return None

    def Load(self, FileID, TypeID, Reload=False, SearchAll=False):
        Entry = self.GetEntry(FileID, TypeID, SearchAll)
        if Entry != None: Entry.Load(Reload)

    def Save(self, FileID, TypeID):
        Entry = self.GetEntry(FileID, TypeID)
        if Entry == None:
            PrettyPrint(f"Failed to save entry {FileID}")
            return False
        if not Global_TocManager.IsInPatch(Entry):
            Entry = self.AddEntryToPatch(FileID, TypeID)
        Entry.Save()
        return True

    def CopyPaste(self, Entry, GenID = False, NewID = None):
        if self.ActivePatch == None:
            raise Exception("No patch exists, please create one first")
        if self.ActivePatch:
            dup = deepcopy(Entry)
            dup.IsCreated = True
            # if self.ActivePatch.GetEntry(dup.FileID, dup.TypeID) != None and NewID == None:
            #     GenID = True
            if GenID and NewID == None: dup.FileID = RandomHash16()
            if NewID != None:
                dup.FileID = NewID
            self.ActivePatch.AddEntry(dup)
            
    def Copy(self, Entries):
        self.CopyBuffer = []
        for Entry in Entries:
            if Entry != None: self.CopyBuffer.append(Entry)
    def Paste(self, GenID = False, NewID = None):
        if self.ActivePatch == None:
            raise Exception("No patch exists, please create one first")
        if self.ActivePatch:
            for ToCopy in self.CopyBuffer:
                self.CopyPaste(ToCopy, GenID, NewID)
            self.CopyBuffer = []

    def ClearClipboard(self):
        self.CopyBuffer = []

    #______________________#
    # ---- Patch Code ---- #
    def PatchActiveArchive(self):
        self.ActivePatch.ToFile()

    def CreatePatchFromActive(self, name="New Patch"):
        if self.ActiveArchive == None:
            raise Exception("No Archive exists to create patch from, please open one first")

        patch = deepcopy(self.ActiveArchive)
        patch.TocEntries  = []
        patch.TocDict     = {}
        patch.TocTypes    = []
        # TODO: ask for which patch index
        path = self.ActiveArchive.Path
        if path.find(".patch_") != -1:
            num = int(path[path.find(".patch_")+len(".patch_"):]) + 1
            path = path[:path.find(".patch_")] + ".patch_" + str(num)
        else:
            path += ".patch_0"
        patch.UpdatePath(path)
        patch.LocalName = name
        PrettyPrint(f"Creating Patch: {path}")
        self.Patches.append(patch)
        self.SetActivePatch(patch)

    def SetActivePatch(self, Patch):
        self.ActivePatch = Patch
        LoadEntryLists()

    def SetActivePatchByName(self, Name):
        for Patch in self.Patches:
            if Patch.Name == Name:
                self.SetActivePatch(Patch)

    def AddNewEntryToPatch(self, Entry):
        if self.ActivePatch == None:
            raise Exception("No patch exists, please create one first")
        self.ActivePatch.AddEntry(Entry)
        
    def AddEntryToPatchID(self, Entry, dest_id):
        if self.ActivePatch == None:
            raise Exception("No patch exists, please create one first")
            
        if Entry != None:
            PatchEntry = deepcopy(Entry)
            PatchEntry.FileID = dest_id
            self.ActivePatch.AddEntry(PatchEntry, override=True)
            return PatchEntry
        return None

    def AddEntryToPatch(self, FileID, TypeID):
        if self.ActivePatch == None:
            raise Exception("No patch exists, please create one first")

        Entry = self.GetEntry(FileID, TypeID)
        if Entry != None:
            PatchEntry = deepcopy(Entry)
            if PatchEntry.IsSelected:
                self.SelectEntries([PatchEntry], True)
            self.ActivePatch.AddEntry(PatchEntry)
            return PatchEntry
        return None

    def RemoveEntryFromPatch(self, FileID, TypeID):
        if self.ActivePatch != None:
            self.ActivePatch.RemoveEntry(FileID, TypeID)
        return None

    def GetPatchEntry(self, Entry):
        if self.ActivePatch != None:
            return self.ActivePatch.GetEntry(Entry.FileID, Entry.TypeID)
        return None
    def GetPatchEntry_B(self, FileID, TypeID):
        if self.ActivePatch != None:
            return self.ActivePatch.GetEntry(FileID, TypeID)
        return None

    def IsInPatch(self, Entry):
        if self.ActivePatch != None:
            PatchEntry = self.ActivePatch.GetEntry(Entry.FileID, Entry.TypeID)
            if PatchEntry != None: return True
            else: return False
        return False

    def DuplicateEntry(self, FileID, TypeID, NewID):
        Entry = self.GetEntry(FileID, TypeID)
        if Entry != None:
            self.CopyPaste(Entry, False, NewID)

#endregion

#region Classes and Functions: Stingray Materials
def LoadStingrayAnimation(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    toc = MemoryStream(TocData)
    PrettyPrint("Loading Animation")
    animation = StingrayAnimation()
    animation.Serialize(toc)
    PrettyPrint("Finished Loading Animation")
    if MakeBlendObject: # To-do: create action for armature
        context = bpy.context
        armature = context.active_object
        try:
            bones_id = int(armature['BonesID'])
        except ValueError:
            raise Exception(f"\n\nCould not obtain custom property: BonesID from armature: {armature.name}. Please make sure this is a valid value")
        try:
            state_machine_id = int(armature['StateMachineID'])
        except ValueError:
            raise Exception(f"\n\nCould not obtain custom property: StateMachineID from armature: {armature.name}. Please make sure this is a valid value")
        state_machine_entry = Global_TocManager.GetEntryByLoadArchive(int(state_machine_id), StateMachineID)
        if not state_machine_entry:
            raise AnimationException("This animation is not for this armature")
        if not state_machine_entry.IsLoaded:
            state_machine_entry.Load()
        if int(ID) not in state_machine_entry.LoadedData.animation_ids:
            raise AnimationException("This animation is not for this armature")
        bones_entry = Global_TocManager.GetEntry(int(bones_id), BoneID, SearchAll=True, IgnorePatch=False)
        if not bones_entry.IsLoaded:
            bones_entry.Load()
        bones_data = bones_entry.TocData
        state_machine_entry = Global_TocManager.GetEntry(int(state_machine_id), StateMachineID, SearchAll=True, IgnorePatch=False)
        if not state_machine_entry.IsLoaded:
            state_machine_entry.Load()
        state_machine_data = state_machine_entry.LoadedData
        animation.to_action(context, armature, bones_data, state_machine_data, ID)
    return animation
    
def LoadStingrayStateMachine(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    toc = MemoryStream(TocData)
    state_machine = StingrayStateMachine()
    state_machine.Serialize(toc)
    return state_machine
    
def SaveStingrayStateMachine(self, ID, TocData, GpuData, StreamData, StateMachine):
    toc = MemoryStream(IOMode = "write")
    StateMachine.Serialize(toc)
    return [toc.Data, b"", b""]
    
def SaveStingrayAnimation(self, ID, TocData, GpuData, StreamData, Animation):
    toc = MemoryStream(IOMode = "write")
    Animation.Serialize(toc)
    return [toc.Data, b"", b""]

def LoadStingrayMaterial(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    exists = True
    force_reload = False
    try:
        mat = bpy.data.materials[str(ID)]
        force_reload = True
    except: exists = False


    f = MemoryStream(TocData)
    Material = StingrayMaterial()
    Material.Serialize(f)
    if MakeBlendObject and not (exists and not Reload): AddMaterialToBlend(ID, Material, Reload)
    elif force_reload: AddMaterialToBlend(ID, Material, True)
    return Material

def SaveStingrayMaterial(self, ID, TocData, GpuData, StreamData, LoadedData):
    if self.MaterialTemplate != None:
        texturesFilepaths = GenerateMaterialTextures(self)
    mat = LoadedData
    for TexIdx in range(len(mat.TexIDs)):
        if not bpy.context.scene.Hd2ToolPanelSettings.SaveTexturesWithMaterial:
            continue
        if bpy.context.scene.Hd2ToolPanelSettings.OnlySaveCustomTextures:
            if self.MaterialTemplate != None:
                template = TextureTypeLookup[self.MaterialTemplate]
                PrettyPrint(f"template: {template}")
                slot = template[TexIdx]
                PrettyPrint(f"slot: {slot}")
                if slot == '':
                    continue
        oldTexID = mat.TexIDs[TexIdx]
        if mat.DEV_DDSPaths[TexIdx] != None:
            # get texture data
            StingrayTex = StingrayTexture()
            with open(mat.DEV_DDSPaths[TexIdx], 'r+b') as f:
                StingrayTex.FromDDS(f.read())
            Toc = MemoryStream(IOMode="write")
            Gpu = MemoryStream(IOMode="write")
            Stream = MemoryStream(IOMode="write")
            StingrayTex.Serialize(Toc, Gpu, Stream)
            # add texture entry to archive
            Entry = TocEntry()

            TextureID = oldTexID
            if bpy.context.scene.Hd2ToolPanelSettings.GenerateRandomTextureIDs:
                TextureID = RandomHash16()

            Entry.FileID = TextureID
            Entry.TypeID = TexID
            Entry.IsCreated = True
            Entry.SetData(Toc.Data, Gpu.Data, Stream.Data, False)

            # Check for existing entry and remove it before adding
            ExistingEntry = Global_TocManager.GetEntry(Entry.FileID, Entry.TypeID)
            if ExistingEntry:
                Global_TocManager.RemoveEntryFromPatch(ExistingEntry.FileID, ExistingEntry.TypeID)

            Global_TocManager.AddNewEntryToPatch(Entry)
            mat.TexIDs[TexIdx] = TextureID
        else:
            Global_TocManager.Load(int(oldTexID), TexID, False, True)
            Entry = Global_TocManager.GetEntry(int(oldTexID), TexID, True)
            if Entry != None:
                Entry = deepcopy(Entry)

                TextureID = oldTexID
                if bpy.context.scene.Hd2ToolPanelSettings.GenerateRandomTextureIDs:
                    TextureID = RandomHash16()

                Entry.FileID = TextureID
                Entry.IsCreated = True

                ExistingEntry = Global_TocManager.GetEntry(Entry.FileID, Entry.TypeID)
                if ExistingEntry:
                    Global_TocManager.RemoveEntryFromPatch(ExistingEntry.FileID, ExistingEntry.TypeID)

                Global_TocManager.AddNewEntryToPatch(Entry)
                mat.TexIDs[TexIdx] = TextureID
                
        # Only use template texture if DEV_DDSPaths wasn't already used
        if self.MaterialTemplate != None and mat.DEV_DDSPaths[TexIdx] == None:
            path = texturesFilepaths[TexIdx]
            if not os.path.exists(path):
                raise Exception(f"Could not find file at path: {path}")
            if not Entry:
                raise Exception(f"Could not find or generate texture entry ID: {int(mat.TexIDs[TexIdx])}")

            if path.endswith(".dds"):
                SaveImageDDS(path, Entry.FileID)
            else:
                SaveImagePNG(path, Entry.FileID)
        if bpy.context.scene.Hd2ToolPanelSettings.GenerateRandomTextureIDs:
            Global_TocManager.RemoveEntryFromPatch(oldTexID, TexID)
    f = MemoryStream(IOMode="write")
    LoadedData.Serialize(f)
    return [f.Data, GpuData, b""]

def AddMaterialToBlend(ID, StingrayMat, EmptyMatExists=False):
    try:
        mat = bpy.data.materials[str(ID)]
        PrettyPrint(f"Found material for ID: {ID} Skipping creation of new material")
        return
    except:
        PrettyPrint(f"Unable to find material in blender scene for ID: {ID} creating new material")
        mat = bpy.data.materials.new(str(ID)); mat.name = str(ID)

    r.seed(ID)
    mat.diffuse_color = (r.random(), r.random(), r.random(), 1)
    mat.use_nodes = True
    #bsdf = mat.node_tree.nodes["Principled BSDF"] # It's not even used?

    Entry = Global_TocManager.GetEntry(int(ID), MaterialID)
    if Entry == None:
        PrettyPrint(f"No Entry Found when getting Material ID: {ID}", "ERROR")
        return
    if Entry.MaterialTemplate != None: CreateAddonMaterial(ID, StingrayMat, mat, Entry)
    else: CreateGameMaterial(StingrayMat, mat)
    
def CreateGameMaterial(StingrayMat, mat):
    for node in mat.node_tree.nodes:
        if node.bl_idname == 'ShaderNodeTexImage':
            mat.node_tree.nodes.remove(node)
    idx = 0
    height = round(len(StingrayMat.TexIDs) * 300 / 2)
    for TextureID in StingrayMat.TexIDs:
        texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texImage.location = (-450, height - 300*idx)

        try:    bpy.data.images[str(TextureID)]
        except: Global_TocManager.Load(TextureID, TexID, False, True)
        try: texImage.image = bpy.data.images[str(TextureID)]
        except:
            PrettyPrint(f"Failed to load texture {TextureID}. This is not fatal, but does mean that the materials in Blender will have empty image texture nodes", "warn")
            pass
        idx +=1

def CreateAddonMaterial(ID, StingrayMat, mat, Entry):
    mat.node_tree.nodes.clear()
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    output.location = (200, 300)
    group = mat.node_tree.nodes.new('ShaderNodeGroup')
    treeName = f"{Entry.MaterialTemplate}-{str(ID)}"
    nodeTree = bpy.data.node_groups.new(treeName, 'ShaderNodeTree')
    group.node_tree = nodeTree
    group.location = (0, 300)

    group_input = nodeTree.nodes.new('NodeGroupInput')
    group_input.location = (-400,0)
    group_output = nodeTree.nodes.new('NodeGroupOutput')
    group_output.location = (400,0)

    idx = 0
    height = round(len(StingrayMat.TexIDs) * 300 / 2)
    TextureNodes = []
    for TextureID in StingrayMat.TexIDs:
        texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texImage.location = (-450, height - 300*idx)

        TextureNodes.append(texImage)

        name = TextureTypeLookup[Entry.MaterialTemplate][idx]
        socket_type = "NodeSocketColor"
        nodeTree.interface.new_socket(name=name, in_out ="INPUT", socket_type=socket_type).hide_value = True

        try:    bpy.data.images[str(TextureID)]
        except: Global_TocManager.Load(TextureID, TexID, False, True)
        try: texImage.image = bpy.data.images[str(TextureID)]
        except:
            PrettyPrint(f"Failed to load texture {TextureID}. This is not fatal, but does mean that the materials in Blender will have empty image texture nodes", "warn")
            pass
        
        if "Normal" in name:
            texImage.image.colorspace_settings.name = 'Non-Color'

        mat.node_tree.links.new(texImage.outputs['Color'], group.inputs[idx])
        idx +=1

    nodeTree.interface.new_socket(name="Surface",in_out ="OUTPUT", socket_type="NodeSocketShader")

    nodes = mat.node_tree.nodes
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            nodes.remove(node)
        elif node.type == 'OUTPUT_MATERIAL':
             mat.node_tree.links.new(group.outputs['Surface'], node.inputs['Surface'])
    
    inputNode = nodeTree.nodes.get('Group Input')
    outputNode = nodeTree.nodes.get('Group Output')
    bsdf = nodeTree.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (50, 0)
    separateColor = nodeTree.nodes.new('ShaderNodeSeparateColor')
    separateColor.location = (-150, 0)
    normalMap = nodeTree.nodes.new('ShaderNodeNormalMap')
    normalMap.location = (-150, -150)

    bsdf.inputs['IOR'].default_value = 1
    bsdf.inputs['Emission Strength'].default_value = 1

    bpy.ops.file.unpack_all(method='REMOVE')
    
    PrettyPrint(f"Setting up any custom templates. Current Template: {Entry.MaterialTemplate}")

    if Entry.MaterialTemplate == "basic": SetupBasicBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap)
    elif Entry.MaterialTemplate == "basic+": SetupBasicBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap)
    elif Entry.MaterialTemplate == "original": SetupOriginalBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap)
    elif Entry.MaterialTemplate == "emissive": SetupEmissiveBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap)
    elif Entry.MaterialTemplate == "alphaclip": SetupAlphaClipBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat)
    elif Entry.MaterialTemplate == "alphaclip+": SetupAlphaClipPlusBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat)
    elif Entry.MaterialTemplate == "advanced": SetupAdvancedBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, TextureNodes, group, mat)
    elif Entry.MaterialTemplate == "translucent": SetupTranslucentBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat)
    
def SetupBasicBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap):
    bsdf.inputs['Emission Strength'].default_value = 0
    inputNode.location = (-750, 0)
    SetupNormalMapTemplate(nodeTree, inputNode, normalMap, bsdf)
    nodeTree.links.new(inputNode.outputs['Base Color'], bsdf.inputs['Base Color'])
    nodeTree.links.new(inputNode.outputs['PBR'], separateColor.inputs['Color'])
    nodeTree.links.new(separateColor.outputs['Red'], bsdf.inputs['Metallic'])
    nodeTree.links.new(separateColor.outputs['Green'], bsdf.inputs['Roughness'])
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])

def SetupOriginalBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap):
    inputNode.location = (-800, -0)
    SetupNormalMapTemplate(nodeTree, inputNode, normalMap, bsdf)
    nodeTree.links.new(inputNode.outputs['Base Color'], bsdf.inputs['Base Color'])
    nodeTree.links.new(inputNode.outputs['Emission'], bsdf.inputs['Emission Color'])
    nodeTree.links.new(inputNode.outputs['PBR'], separateColor.inputs['Color'])
    nodeTree.links.new(separateColor.outputs['Red'], bsdf.inputs['Metallic'])
    nodeTree.links.new(separateColor.outputs['Green'], bsdf.inputs['Roughness'])
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])

def SetupEmissiveBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap):
    nodeTree.links.new(inputNode.outputs['Base Color/Metallic'], bsdf.inputs['Base Color'])
    nodeTree.links.new(inputNode.outputs['Emission'], bsdf.inputs['Emission Color'])
    nodeTree.links.new(inputNode.outputs['Normal/AO/Roughness'], separateColor.inputs['Color'])
    nodeTree.links.new(separateColor.outputs['Red'], normalMap.inputs['Color'])
    nodeTree.links.new(normalMap.outputs['Normal'], bsdf.inputs['Normal'])
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])

def SetupAlphaClipBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat):
    bsdf.inputs['Emission Strength'].default_value = 0
    combineColor = nodeTree.nodes.new('ShaderNodeCombineColor')
    combineColor.inputs['Blue'].default_value = 1
    combineColor.location = (-350, -150)
    separateColor.location = (-550, -150)
    inputNode.location = (-750, 0)
    mat.blend_method = 'CLIP'
    nodeTree.links.new(inputNode.outputs['Base Color/Metallic'], bsdf.inputs['Base Color'])
    nodeTree.links.new(inputNode.outputs['Alpha Mask'], bsdf.inputs['Alpha'])
    nodeTree.links.new(inputNode.outputs['Normal/AO/Roughness'], separateColor.inputs['Color'])
    nodeTree.links.new(separateColor.outputs['Red'], combineColor.inputs['Red'])
    nodeTree.links.new(separateColor.outputs['Green'], combineColor.inputs['Green'])
    nodeTree.links.new(combineColor.outputs['Color'], normalMap.inputs['Color'])
    nodeTree.links.new(normalMap.outputs['Normal'], bsdf.inputs['Normal'])
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])

def SetupAlphaClipPlusBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat):
    SetupAlphaClipBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat)
    bsdf.inputs['Emission Strength'].default_value = 1
    nodeTree.links.new(inputNode.outputs['Emission'], bsdf.inputs['Emission Color'])

def SetupNormalMapTemplate(nodeTree, inputNode, normalMap, bsdf):
    separateColorNormal = nodeTree.nodes.new('ShaderNodeSeparateColor')
    separateColorNormal.location = (-550, -150)
    combineColorNormal = nodeTree.nodes.new('ShaderNodeCombineColor')
    combineColorNormal.location = (-350, -150)
    combineColorNormal.inputs['Blue'].default_value = 1
    nodeTree.links.new(inputNode.outputs['Normal'], separateColorNormal.inputs['Color'])
    nodeTree.links.new(separateColorNormal.outputs['Red'], combineColorNormal.inputs['Red'])
    nodeTree.links.new(separateColorNormal.outputs['Green'], combineColorNormal.inputs['Green'])
    nodeTree.links.new(combineColorNormal.outputs['Color'], normalMap.inputs['Color'])
    nodeTree.links.new(normalMap.outputs['Normal'], bsdf.inputs['Normal'])

def SetupAdvancedBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, TextureNodes, group, mat):
    bsdf.inputs['Emission Strength'].default_value = 0
    TextureNodes[5].image.colorspace_settings.name = 'Non-Color'
    nodeTree.nodes.remove(separateColor)
    inputNode.location = (-750, 0)
    separateColorNormal = nodeTree.nodes.new('ShaderNodeSeparateColor')
    separateColorNormal.location = (-550, -150)
    combineColorNormal = nodeTree.nodes.new('ShaderNodeCombineColor')
    combineColorNormal.location = (-350, -150)
    combineColorNormal.inputs['Blue'].default_value = 1
    nodeTree.links.new(inputNode.outputs['Normal/AO/Roughness'], separateColorNormal.inputs['Color'])
    nodeTree.links.new(separateColorNormal.outputs['Red'], combineColorNormal.inputs['Red'])
    nodeTree.links.new(separateColorNormal.outputs['Green'], combineColorNormal.inputs['Green'])
    nodeTree.links.new(normalMap.outputs['Normal'], bsdf.inputs['Normal'])
    nodeTree.links.new(combineColorNormal.outputs['Color'], normalMap.inputs['Color'])
    nodeTree.links.new(inputNode.outputs['Color/Emission Mask'], bsdf.inputs['Base Color'])
    nodeTree.links.new(inputNode.outputs['Metallic'], bsdf.inputs['Metallic'])

    RoughnessSocket = nodeTree.interface.new_socket(name="Normal/AO/Roughness (Alpha)", in_out ="INPUT", socket_type="NodeSocketFloat").hide_value = True
    mat.node_tree.links.new(TextureNodes[2].outputs['Alpha'], group.inputs['Normal/AO/Roughness (Alpha)'])
    nodeTree.links.new(inputNode.outputs['Normal/AO/Roughness (Alpha)'], bsdf.inputs['Roughness'])

    multiplyEmission = nodeTree.nodes.new('ShaderNodeMath')
    multiplyEmission.location = (-350, -350)
    multiplyEmission.operation = 'MULTIPLY'
    multiplyEmission.inputs[1].default_value = 0
    nodeTree.interface.new_socket(name="Color/Emission Mask (Alpha)", in_out ="INPUT", socket_type="NodeSocketFloat").hide_value = True
    mat.node_tree.links.new(TextureNodes[5].outputs['Alpha'], group.inputs['Color/Emission Mask (Alpha)'])
    nodeTree.links.new(inputNode.outputs['Color/Emission Mask (Alpha)'], multiplyEmission.inputs[0])
    nodeTree.links.new(multiplyEmission.outputs['Value'], bsdf.inputs['Emission Strength'])
    
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])

def SetupTranslucentBlenderMaterial(nodeTree, inputNode, outputNode, bsdf, separateColor, normalMap, mat):
    bsdf.inputs['Emission Strength'].default_value = 0
    nodeTree.nodes.remove(separateColor)
    inputNode.location = (-750, 0)
    SetupNormalMapTemplate(nodeTree, inputNode, normalMap, bsdf)
    nodeTree.links.new(bsdf.outputs['BSDF'], outputNode.inputs['Surface'])
    mat.blend_method = 'BLEND'
    bsdf.inputs['Alpha'].default_value = 0.02
    bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)

def CreateGenericMaterial(ID, StingrayMat, mat):
    idx = 0
    for TextureID in StingrayMat.TexIDs:
        # Create Node
        texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texImage.location = (-450, 850 - 300*idx)

        # Load Texture
        Global_TocManager.Load(TextureID, TexID, False, True)
        # Apply Texture
        try: texImage.image = bpy.data.images[str(TextureID)]
        except:
            PrettyPrint(f"Failed to load texture {TextureID}. This is not fatal, but does mean that the materials in Blender will have empty image texture nodes", "warn")
            pass
        idx +=1

def GenerateMaterialTextures(Entry):
    material = group = None
    for mat in bpy.data.materials:
        if mat.name == str(Entry.FileID):
            material = mat
            break
    if material == None:
        raise Exception(f"Material Could not be Found ID: {Entry.FileID} {bpy.data.materials}")
    PrettyPrint(f"Found Material {material.name} {material}")
    for node in material.node_tree.nodes:
        if node.type == 'GROUP':
            group = node
            break
    if group == None:
        raise Exception("Could not find node group within material")
    filepaths = []
    for input_socket in group.inputs:
        PrettyPrint(input_socket.name)
        if input_socket.is_linked:
            for link in input_socket.links:
                image = link.from_node.image
                if image.packed_file:
                    raise Exception(f"Image: {image.name} is packed. Please unpack your image.")
                path = bpy.path.abspath(image.filepath)
                PrettyPrint(f"Getting image path at: {path}")
                ID = image.name.split(".")[0]
                if not os.path.exists(path) and ID.isnumeric():
                    PrettyPrint(f"Image not found. Attempting to find image: {ID} in temp folder.", 'WARN')
                    tempdir = get_temp_folder()
                    path = f"{tempdir}/{ID}.png"
                filepaths.append(path)

                # enforce proper colorspace for abnormal stingray textures
                if "Normal" in input_socket.name or "Color/Emission Mask" in input_socket.name:
                     image.colorspace_settings.name = 'Non-Color'
    
    # display proper emissives on advanced material
    if "advanced" in group.node_tree.name:
        colorVariable = Entry.LoadedData.ShaderVariables[32].values
        emissionColor = (colorVariable[0], colorVariable[1], colorVariable[2], 1)
        emissionStrength = Entry.LoadedData.ShaderVariables[40].values[0]
        emissionStrength = max(0, emissionStrength)
        PrettyPrint(f"Emission color: {emissionColor} Strength: {emissionStrength}")
        for node in group.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Emission Color'].default_value = emissionColor
            if node.type == 'MATH' and node.operation == 'MULTIPLY':
                node.inputs[1].default_value = emissionStrength

    # update color and alpha of translucent
    if "translucent" in group.node_tree.name:
        colorVariable = Entry.LoadedData.ShaderVariables[7].values
        baseColor = (colorVariable[0], colorVariable[1], colorVariable[2], 1)
        alphaVariable = Entry.LoadedData.ShaderVariables[1].values[0]
        PrettyPrint(f"Base color: {baseColor} Alpha: {alphaVariable}")
        for node in group.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = baseColor
                node.inputs['Alpha'].default_value = alphaVariable

    PrettyPrint(f"Found {len(filepaths)} Images: {filepaths}")
    return filepaths

#endregion

#region Classes and Functions: Stingray Textures

def BlendImageToStingrayTexture(image, StingrayTex):
    tempdir  = get_temp_folder()
    dds_path = f"{tempdir}/blender_img.dds"
    tga_path = f"{tempdir}/blender_img.tga"

    image.file_format = 'TARGA_RAW'
    image.filepath_raw = tga_path
    image.save()

    subprocess.run([Global_texconvpath, "-y", "-o", tempdir, "-ft", "dds", "-dx10", "-f", StingrayTex.Format, "-sepalpha", "-alpha", dds_path], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    if os.path.isfile(dds_path):
        with open(dds_path, 'r+b') as f:
            StingrayTex.FromDDS(f.read())
    else:
        raise Exception("Failed to convert TGA to DDS")

def LoadStingrayTexture(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    exists = True
    try: bpy.data.images[str(ID)]
    except: exists = False

    StingrayTex = StingrayTexture()
    StingrayTex.Serialize(MemoryStream(TocData), MemoryStream(GpuData), MemoryStream(StreamData))
    dds = StingrayTex.ToDDS()

    if MakeBlendObject and not (exists and not Reload):
        tempdir = get_temp_folder()
        dds_path = f"{tempdir}/{ID}.dds"
        png_path = f"{tempdir}/{ID}.png"

        with open(dds_path, 'w+b') as f:
            f.write(dds)
        
        subprocess.run([Global_texconvpath, "-y", "-o", tempdir, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-sepalpha", "-alpha", dds_path], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if os.path.isfile(png_path):
            image = bpy.data.images.load(png_path)
            image.name = str(ID)
            image.pack()
        else:
            raise Exception(f"Failed to convert texture {ID} to PNG, or DDS failed to export")
    
    return StingrayTex

def SaveStingrayTexture(self, ID, TocData, GpuData, StreamData, LoadedData):
    exists = True
    try: bpy.data.images[str(ID)]
    except: exists = False

    Toc = MemoryStream(IOMode="write")
    Gpu = MemoryStream(IOMode="write")
    Stream = MemoryStream(IOMode="write")

    LoadedData.Serialize(Toc, Gpu, Stream)

    return [Toc.Data, Gpu.Data, Stream.Data]

#endregion

#region Stingray IO

def LoadStingrayBones(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    StingrayBonesData = StingrayBones(Global_BoneNames)
    StingrayBonesData.Serialize(MemoryStream(TocData))
    return StingrayBonesData
    
def SaveStingrayBones(self, ID, TocData, GpuData, StreamData, LoadedData):
    f = MemoryStream(TocData, IOMode="write") # Load in original TocData before overwriting it
    LoadedData.Serialize(f)
    return [f.Data, b"", b""]

def LoadStingrayCompositeUnit(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    StingrayCompositeMeshData = StingrayCompositeMesh()
    StingrayCompositeMeshData.Serialize(MemoryStream(TocData), MemoryStream(GpuData))
    return StingrayCompositeMeshData

def LoadStingrayParticle(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    f = MemoryStream(TocData)
    Particle = StingrayParticles()
    Particle.Serialize(f)
    return Particle

def SaveStingrayParticle(self, ID, TocData, GpuData, StreamData, LoadedData):
    f = MemoryStream(TocData, IOMode="write") # Load in original TocData before overwriting it
    LoadedData.Serialize(f)
    return [f.Data, b"", b""]

def LoadStingrayDump(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject):
    StingrayDumpData = StingrayRawDump()
    return StingrayDumpData

def SaveStingrayDump(self, ID, TocData, GpuData, StreamData, LoadedData):
    return [TocData, GpuData, StreamData]

def LoadStingrayUnit(ID, TocData, GpuData, StreamData, Reload, MakeBlendObject, LoadMaterialSlotNames=False):
    toc  = MemoryStream(TocData)
    gpu  = MemoryStream(GpuData)
        
    
    StingrayMesh = StingrayMeshFile()
    StingrayMesh.NameHash = int(ID)
    StingrayMesh.LoadMaterialSlotNames = LoadMaterialSlotNames
    StingrayMesh.Serialize(toc, gpu, Global_TocManager)
    bones_entry = Global_TocManager.GetEntry(StingrayMesh.BonesRef, BoneID, SearchAll=True, IgnorePatch=False)
    if bones_entry and not bones_entry.IsLoaded:
        bones_entry.Load(False, False)
    state_machine_entry = Global_TocManager.GetEntry(StingrayMesh.StateMachineRef, StateMachineID, SearchAll=True, IgnorePatch=False)
    if state_machine_entry and not state_machine_entry.IsLoaded:
        state_machine_entry.Load(False, False)
    if MakeBlendObject and bones_entry and state_machine_entry: CreateModel(StingrayMesh, str(ID), Global_BoneNames, bones_entry.LoadedData, state_machine_entry.LoadedData)
    elif MakeBlendObject: CreateModel(StingrayMesh, str(ID), Global_BoneNames, None, None)
    return StingrayMesh

def SaveStingrayUnit(self, ID, TocData, GpuData, StreamData, StingrayMesh, BlenderOpts=None):
    if BlenderOpts and BlenderOpts.get("AutoLods"):
        lod0 = None
        lod0_idx = 0
        for i, mesh in enumerate(StingrayMesh.RawMeshes):
            if mesh.LodIndex == 0:
                lod0 = mesh
                lod0_idx = i
                break
        # print(lod0)
        if lod0 != None:
            for n in range(len(StingrayMesh.RawMeshes)):
                if StingrayMesh.RawMeshes[n].IsLod():
                    newmesh = copy.copy(lod0)
                    newmesh.MeshInfoIndex = StingrayMesh.RawMeshes[n].MeshInfoIndex
                    StingrayMesh.RawMeshes[n] = newmesh
                    StingrayMesh.TransformInfo.TransformMatrices[StingrayMesh.MeshInfoArray[n].TransformIndex] = StingrayMesh.TransformInfo.TransformMatrices[StingrayMesh.MeshInfoArray[lod0.MeshInfoIndex].TransformIndex]
    toc  = MemoryStream(IOMode = "write")
    gpu  = MemoryStream(IOMode = "write")
    StingrayMesh.Serialize(toc, gpu, Global_TocManager, BlenderOpts=BlenderOpts)
    return [toc.Data, gpu.Data, b""]

#endregion

#region Operators: Archives & Patches

def ArchivesNotLoaded(self):
    if len(Global_TocManager.LoadedArchives) <= 0:
        self.report({'ERROR'}, "No Archives Currently Loaded")
        return True
    else: 
        return False
    
def PatchesNotLoaded(self):
    if len(Global_TocManager.Patches) <= 0:
        self.report({'ERROR'}, "No Patches Currently Loaded")
        return True
    else:
        return False

def ObjectHasModifiers(self, objects):
    for obj in objects:
        for modifier in obj.modifiers:
            if modifier.type != "ARMATURE":
                self.report({'ERROR'}, f"Object: {obj.name} has {len(obj.modifiers)} unapplied modifiers")
                return True
    return False

def ObjectHasShapeKeys(self, objects):
    for obj in objects:
        if hasattr(obj.data.shape_keys, 'key_blocks'):
            self.report({'ERROR'}, f"Object: {obj.name} has {len(obj.data.shape_keys.key_blocks)} unapplied shape keys")
            return True
    return False

def MaterialsNumberNames(self, objects):
    mesh_objs = [ob for ob in objects if ob.type == 'MESH']
    for mesh in mesh_objs:
        invalidMaterials = 0
        if len(mesh.material_slots) == 0:
            self.report({'ERROR'}, f"Object: {mesh.name} has no material slots")
            return True
        for slot in mesh.material_slots:
            if slot.material:
                materialName = slot.material.name
                if not materialName.isnumeric() and materialName != "StingrayDefaultMaterial":
                    invalidMaterials += 1
            else:
                invalidMaterials += 1
        if invalidMaterials > 0:
            self.report({'ERROR'}, f"Object: {mesh.name} has {invalidMaterials} non Helldivers 2 Materials")
            return True
    return False

def HasZeroVerticies(self, objects):
    mesh_objs = [ob for ob in objects if ob.type == 'MESH']
    for mesh in mesh_objs:
        verts = len(mesh.data.vertices)
        PrettyPrint(f"Object: {mesh.name} Verticies: {verts}")
        if verts <= 0:
            self.report({'ERROR'}, f"Object: {mesh.name} has no zero verticies")
            return True
    return False

def UnitNotValidToSave(self):
    objects = bpy.context.selected_objects
    for i, obj in enumerate(objects):
        if obj.type != 'MESH':
            objects.pop(i)

    return (PatchesNotLoaded(self) or 
            CheckDuplicateIDsInScene(self, objects) or 
            CheckVertexGroups(self, objects) or 
            ObjectHasModifiers(self, objects) or 
            MaterialsNumberNames(self, objects) or 
            HasZeroVerticies(self, objects) or 
            ObjectHasShapeKeys(self, objects) or 
            CheckHaveHD2Properties(self, objects)
            )

def CheckHaveHD2Properties(self, objects):
    list_copy = list(objects)
    for obj in list_copy:
        try:
            _ = obj["Z_ObjectID"]
            _ = obj["MeshInfoIndex"]
            _ = obj["BoneInfoIndex"]
        except KeyError:
            self.report({'ERROR'}, f"Object {obj.name} is missing HD2 properties")
            return True
    return False


def CheckDuplicateIDsInScene(self, objects):
    custom_objects = {}
    for obj in objects:
        obj_id = obj.get("Z_ObjectID")
        swap_id = obj.get("Z_SwapID")
        mesh_index = obj.get("MeshInfoIndex")
        bone_index = obj.get("BoneInfoIndex")
        if obj_id is not None:
            obj_tuple = (obj_id, mesh_index, bone_index, swap_id)
            try:
                custom_objects[obj_tuple].append(obj)
            except:
                custom_objects[obj_tuple] = [obj]
    for item in custom_objects.values():
        if len(item) > 1:
            self.report({'ERROR'}, f"Multiple objects with the same HD2 properties are in the scene! Please delete one and try again.\nObjects: {', '.join([obj.name for obj in item])}")
            return True
    return False


def CheckVertexGroups(self, objects):
    list_copy = list(objects)
    for obj in list_copy:
        incorrectGroups = 0
        try:
            BoneIndex = obj["BoneInfoIndex"]
        except KeyError:
            self.report({'ERROR'}, f"Couldn't find HD2 Properties in {obj.name}")
            return True
        if len(obj.vertex_groups) <= 0 and BoneIndex != -1:
            self.report({'ERROR'}, f"No Vertex Groups Found for non-static mesh: {obj.name}")
            return True
        if len(obj.vertex_groups) > 0 and BoneIndex == -1:
            self.report({'ERROR'}, f"Vertex Groups Found for static mesh: {obj.name}. Please remove vertex groups.")
            return True
        if bpy.context.scene.Hd2ToolPanelSettings.LegacyWeightNames:
            for group in obj.vertex_groups:
                if "_" not in group.name:
                    incorrectGroups += 1
                else:
                    parts = group.name.split("_")
                    if parts[1] is None or not parts[0].isnumeric() or not parts[1].isnumeric():
                        incorrectGroups += 1
        if incorrectGroups > 0:
            self.report({'ERROR'}, f"Found {incorrectGroups} Incorrect Vertex Group Name Scheming for Legacy Weight Names for Object: {obj.name}")
            return True
    return False

def CopyToClipboard(txt):
    cmd='echo '+txt.strip()+'|clip'
    return subprocess.check_call(cmd, shell=True)

def hex_to_decimal(hex_string):
    try:
        decimal_value = int(hex_string, 16)
        return decimal_value
    except ValueError:
        PrettyPrint(f"Invalid hexadecimal string: {hex_string}")

class ChangeFilepathOperator(Operator, ImportHelper):
    bl_label = "Change Filepath"
    bl_idname = "helldiver2.change_filepath"
    bl_description = "Change the game's data folder directory"
    #filename_ext = "."
    use_filter_folder = True

    filter_glob: StringProperty(options={'HIDDEN'}, default='')

    def __init__(self):
        global Global_gamepath
        self.filepath = bpy.path.abspath(Global_gamepath)
        
    def execute(self, context):
        global Global_gamepath
        global Global_gamepathIsValid
        filepath = self.filepath
        steamapps = "steamapps"
        if steamapps in filepath:
            filepath = f"{filepath.partition(steamapps)[0]}steamapps/common/Helldivers 2/data/ "[:-1]
        else:
            self.report({'ERROR'}, f"Could not find steamapps folder in filepath: {filepath}")
            return{'CANCELLED'}
        Global_gamepath = filepath
        Global_gamepathIsValid = True
        UpdateConfig()
        PrettyPrint(f"Changed Game File Path: {Global_gamepath}")
        return{'FINISHED'}
    
class ChangeSearchpathOperator(Operator, ImportHelper):
    bl_label = "Change Searchpath"
    bl_idname = "helldiver2.change_searchpath"
    bl_description = "Change the output directory for searching by entry ID"
    use_filter_folder = True

    filter_glob: StringProperty(options={'HIDDEN'}, default='')

    def __init__(self):
        global Global_searchpath
        self.filepath = bpy.path.abspath(Global_searchpath)
        
    def execute(self, context):
        global Global_searchpath
        Global_searchpath = self.filepath
        UpdateConfig()
        PrettyPrint(f"Changed Game Search Path: {Global_searchpath}")
        return{'FINISHED'}

class ChangeFilediverPathOperator(Operator, ImportHelper):
    bl_label = "Change Filediver Path"
    bl_idname = "helldiver2.change_filediverpath"
    bl_description = "Set the path to your filediver installation folder"
    use_filter_folder = True

    filter_glob: StringProperty(options={'HIDDEN'}, default='')

    def __init__(self):
        global Global_filediverpath
        if Global_filediverpath:
            self.filepath = bpy.path.abspath(Global_filediverpath)

    def execute(self, context):
        global Global_filediverpath, Global_filediverpathIsValid
        # Get directory from filepath
        filepath = self.filepath
        if os.path.isfile(filepath):
            filepath = os.path.dirname(filepath)

        filediver_exe = os.path.join(filepath, "filediver.exe")
        if not os.path.exists(filediver_exe):
            self.report({'ERROR'}, f"filediver.exe not found in: {filepath}")
            return {'CANCELLED'}

        Global_filediverpath = filepath
        Global_filediverpathIsValid = True
        UpdateConfig()
        PrettyPrint(f"Changed Filediver Path: {Global_filediverpath}")
        return {'FINISHED'}

class DefaultLoadArchiveOperator(Operator):
    bl_label = "Default Archive"
    bl_description = "Loads the Default Archive that Patches should be built upon"
    bl_idname = "helldiver2.archive_import_default"

    def execute(self, context):
        path = Global_gamepath + BaseArchiveHexID
        if not os.path.exists(Global_gamepath):
            self.report({'ERROR'}, "Current Filepath is Invalid. Change this in the Settings")
            context.scene.Hd2ToolPanelSettings.MenuExpanded = True
            return{'CANCELLED'}
        Global_TocManager.LoadArchive(path, True, False)

        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        
        return{'FINISHED'}
      
class LoadArchiveOperator(Operator, ImportHelper):
    bl_label = "Manually Load Archive"
    bl_idname = "helldiver2.archive_import"
    bl_description = "Loads a Selected Archive from Helldivers Data Folder"

    files: CollectionProperty(type=bpy.types.OperatorFileListElement,options={"HIDDEN", "SKIP_SAVE"})
    is_patch: BoolProperty(name="is_patch", default=False, options={'HIDDEN'})
    #files = CollectionProperty(name='File paths', type=bpy.types.PropertyGroup)

    def __init__(self):
        self.filepath = bpy.path.abspath(Global_gamepath)

    def execute(self, context):
        # Sanitize path by removing any provided extension, so the correct TOC file is loaded
        if not self.is_patch:
            filepaths = [Global_gamepath + f.name for f in self.files]
        else:
            if ".patch" not in self.filepath:
                self.report({'ERROR'}, f"Selected path: {self.filepath} is not a patch file! Please make sure to select the patch files. If you selected a zip file, please extract the contents and select the patch files actual patch files.")
                return {'CANCELLED'}
            filepaths = [self.filepath, ]
        oldLoadedLength = len(Global_TocManager.LoadedArchives)
        for filepath in filepaths:
            if not os.path.exists(filepath) or filepath.endswith(".ini") or filepath.endswith(".data"):
                continue
            path = Path(filepath)
            if not path.suffix.startswith(".patch_"): path = path.with_suffix("")

            archiveToc = Global_TocManager.LoadArchive(str(path), True, self.is_patch)
        PrettyPrint(f"Loaded {len(Global_TocManager.LoadedArchives) - oldLoadedLength} Archive(s)")

        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        
        return{'FINISHED'}

class UnloadArchivesOperator(Operator):
    bl_label = "Unload Archives"
    bl_idname = "helldiver2.archive_unloadall"
    bl_description = "Unloads All Current Loaded Archives"

    def execute(self, context):
        Global_TocManager.UnloadArchives()
        return{'FINISHED'}
    
class UnloadPatchesOperator(Operator):
    bl_label = "Unload Patches"
    bl_idname = "helldiver2.patches_unloadall"
    bl_description = "Unloads All Current Loaded Patches"

    def execute(self, context):
        Global_TocManager.UnloadPatches()
        return{'FINISHED'}
    
class BulkLoadOperator(Operator, ImportHelper):
    bl_label = "Bulk Loader"
    bl_idname = "helldiver2.bulk_load"
    bl_description = "Loads archives from a list of patch names in a text file"

    open_file_browser: BoolProperty(default=True, options={'HIDDEN'})
    file: StringProperty(options={'HIDDEN'})
    
    filter_glob: StringProperty(options={'HIDDEN'}, default='*.txt')

    def execute(self, context):
        self.file = self.filepath
        f = open(self.file, "r")
        entries = f.read().splitlines()
        numEntries = len(entries)
        PrettyPrint(f"Loading {numEntries} Archives")
        numArchives = len(Global_TocManager.LoadedArchives)
        entryList = (Global_gamepath + entry.split(" ")[0] for entry in entries)
        Global_TocManager.BulkLoad(entryList)
        numArchives = len(Global_TocManager.LoadedArchives) - numArchives
        numSkipped = numEntries - numArchives
        PrettyPrint(f"Loaded {numArchives} Archives. Skipped {numSkipped} Archives")
        PrettyPrint(f"{len(entries)} {entries}")
        archivesList = (archive.Name for archive in Global_TocManager.LoadedArchives)
        for item in archivesList:
            if item in entries:
                PrettyPrint(f"Switching To First Loaded Archive: {item}")
                bpy.context.scene.Hd2ToolPanelSettings.LoadedArchives = item
                break
        return{'FINISHED'}
    
class FixNinjaRipperOperator(Operator):
    bl_label = "Fix Ninja Ripper Imports"
    bl_idname = "helldiver2.fix_ninja_ripper"
    bl_description = "Transforms Ninja Ripper HD2 exports: rotates 90° on X, centers on player position, sets camera view"

    def execute(self, context):
        import bmesh
        import mathutils
        from math import radians

        # HD2 Ninja Ripper standard fix values
        rotation_matrix = mathutils.Matrix.Rotation(radians(90), 4, 'X')
        translation_offset = mathutils.Vector((0.721674, 1.001493, -0.168735))

        # Get all selected mesh objects
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_meshes:
            self.report({'WARNING'}, "No mesh objects selected. Select Ninja Ripper meshes first.")
            return {'CANCELLED'}

        # Transform all selected meshes
        for obj in selected_meshes:
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)

            # Apply rotation then translation to all vertices
            for vert in bm.verts:
                vert.co = rotation_matrix @ vert.co
                vert.co += translation_offset

            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

        # Set viewport camera position
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        r3d = space.region_3d
                        r3d.view_perspective = 'PERSP'
                        r3d.view_distance = 2.331160

                        # Set view location and rotation
                        view_loc = mathutils.Vector((1.894437, 0.610886, 0.387552))
                        view_rot = mathutils.Euler((1.387990, 0.013756, 1.872079))

                        # Build view matrix from location and rotation
                        view_matrix = view_rot.to_matrix().to_4x4()
                        view_matrix.translation = view_loc
                        r3d.view_matrix = view_matrix.inverted()
                        break

        self.report({'INFO'}, f"Fixed {len(selected_meshes)} Ninja Ripper meshes")
        return {'FINISHED'}

class SearchByEntryIDOperator(Operator, ImportHelper):
    bl_label = "Bulk Search By Entry ID"
    bl_idname = "helldiver2.search_by_entry"
    bl_description = "Search for Archives by their contained Entry IDs"

    filter_glob: StringProperty(options={'HIDDEN'}, default='*.txt')

    def execute(self, context):
        baseArchivePath = Global_gamepath + BaseArchiveHexID
        Global_TocManager.LoadArchive(baseArchivePath)
        
        findme = open(self.filepath, "r")
        fileIDs = findme.read().splitlines()
        findme.close()

        archives = []
        PrettyPrint(f"Searching for {len(fileIDs)} IDs")
        for fileID in fileIDs:
            ID = fileID.split()[0]
            try:
                name = fileID.split(" ", 1)[1]
            except:
                name = None
            if ID.startswith("0x"):
                ID = hex_to_decimal(ID)
            ID = int(ID)
           
            Archives = SearchByEntryID(ID)
            
            if Archives and bpy.context.scene.Hd2ToolPanelSettings.LoadFoundArchives:
                for Archive in Archives:
                    Global_TocManager.LoadArchive(Archive.Path, True, False)

        curenttime = str(datetime.datetime.now()).replace(":", "-").replace(".", "_")
        outputfile = f"{Global_searchpath}output_{curenttime}.txt"
        PrettyPrint(f"Found {len(archives)} archives")
        output = open(outputfile, "w")
        for item in archives:
            PrettyPrint(item)
            output.write(item + "\n")
        output.close()
        self.report({'INFO'}, f"Found {len(archives)} archives with matching IDs.")
        PrettyPrint(f"Output file created at: {outputfile}")
        return {'FINISHED'}

class SearchByEntryIDInput(Operator):
    bl_label = "Search By Entry ID"
    bl_idname = "helldiver2.search_by_entry_input"
    bl_description = "Search for Archives by their contained Entry IDs"

    entry_id: StringProperty(name="Entry ID")
    def execute(self, context):
            ID = self.entry_id
            if ID.startswith("0x"):
                ID = hex_to_decimal(self.entry_id)

            Archives = SearchByEntryID(int(ID))
            for Archive in Archives:
                Global_TocManager.LoadArchive(Archive.Path)

            # Redraw
            for area in context.screen.areas:
                if area.type == "VIEW_3D": area.tag_redraw()
            
            return{'FINISHED'}
    
    def invoke(self, context, event):
        if ArchivesNotLoaded(self):
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "entry_id")

def SearchByEntryID(ID: int):
    global Global_TocManager
    archives = []
    PrettyPrint(f"Searching for ID: {ID}")
    for Archive in Global_TocManager.SearchArchives:
        if ID in Archive.fileIDs:
            PrettyPrint(f"Found ID: {ID} in Archive: {Archive.Name}")
            archives.append(Archive)
        
    PrettyPrint(f"Found ID: {ID} in {len(archives)} unique archives")
    PrettyPrint(archives)
    return archives

class CreatePatchFromActiveOperator(Operator):
    bl_label = "Create Patch"
    bl_idname = "helldiver2.archive_createpatch"
    bl_description = "Creates Patch from Current Active Archive"

    def execute(self, context):
        original_archive = context.scene.Hd2ToolPanelSettings.LoadedArchives
        if bpy.context.scene.Hd2ToolPanelSettings.PatchBaseArchiveOnly:
            baseArchivePath = Global_gamepath + BaseArchiveHexID
            Global_TocManager.LoadArchive(baseArchivePath)
            context.scene.Hd2ToolPanelSettings.LoadedArchives = BaseArchiveHexID
        else:
            self.report({'WARNING'}, f"Patch Created Was Not From Base Archive.")
        
        if ArchivesNotLoaded(self):
            return{'CANCELLED'}
        
        Global_TocManager.CreatePatchFromActive()
        if original_archive:
            context.scene.Hd2ToolPanelSettings.LoadedArchives = original_archive

        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        
        return{'FINISHED'}
    
class PatchArchiveOperator(Operator):
    bl_label = "Patch Archive"
    bl_idname = "helldiver2.archive_export"
    bl_description = "Writes Patch to Current Active Patch"

    def execute(self, context):
        global Global_TocManager
        if PatchesNotLoaded(self):
            return{'CANCELLED'}
        
        
        #bpy.ops.wm.save_as_mainfile(filepath=)
        
        if bpy.context.scene.Hd2ToolPanelSettings.SaveUnsavedOnWrite:
            SaveUnsavedEntries(self)
        Global_TocManager.PatchActiveArchive()
        self.report({'INFO'}, f"Patch Written")
        return{'FINISHED'}

class RenamePatchOperator(Operator):
    bl_label = "Rename Mod"
    bl_idname = "helldiver2.rename_patch"
    bl_description = "Change Name of Current Mod Within the Tool"

    patch_name: StringProperty(name="Mod Name")

    def execute(self, context):
        if PatchesNotLoaded(self):
            return{'CANCELLED'}
        
        Global_TocManager.ActivePatch.LocalName = self.patch_name

        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        
        return{'FINISHED'}
    
    def invoke(self, context, event):
        if Global_TocManager.ActiveArchive == None:
            self.report({"ERROR"}, "No patch exists, please create one first")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "patch_name")

class ExportPatchAsZipOperator(Operator, ExportHelper):
    bl_label = "Export Patch"
    bl_idname = "helldiver2.export_patch"
    bl_description = "Exports the Current Active Patch as a Zip File"
    
    filename_ext = ".zip"
    use_filter_folder = True
    filter_glob: StringProperty(default='*.zip', options={'HIDDEN'})

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        
        filepath = self.properties.filepath
        outputFilename = filepath.replace(".zip", "")
        exportname = os.path.basename(filepath)
        
        patchName = Global_TocManager.ActivePatch.Name
        tempPatchFolder = get_temp_folder() + "/patchExport/"
        tempPatchFile = f"{tempPatchFolder}/{patchName}"
        PrettyPrint(f"Exporting in temp folder: {tempPatchFolder}")

        if not os.path.exists(tempPatchFolder):
            os.makedirs(tempPatchFolder)
        Global_TocManager.ActivePatch.ToFile(tempPatchFile)
        shutil.make_archive(outputFilename, 'zip', tempPatchFolder)
        for file in os.listdir(tempPatchFolder):
            path = f"{tempPatchFolder}/{file}"
            os.remove(path)
        os.removedirs(tempPatchFolder)

        if os.path.exists(filepath):
            self.report({'INFO'}, f"{patchName} Exported Successfully As {exportname}")
        else: 
            self.report({'ERROR'}, f"Failed to Export {patchName}")

        return {'FINISHED'}

def detect_patch_conflicts():
    """
    Scans all patches for entries with the same FileID.
    Returns: {(FileID, TypeID): [patch_name1, patch_name2, ...]}
    """
    entry_sources = {}  # {(FileID, TypeID): [patch_names]}

    for patch in Global_TocManager.Patches:
        for type_id, entries in patch.TocDict.items():
            for file_id in entries.keys():
                key = (file_id, type_id)
                if key not in entry_sources:
                    entry_sources[key] = []
                entry_sources[key].append(patch.Name)

    # Filter to only entries with 2+ sources (conflicts)
    conflicts = {k: v for k, v in entry_sources.items() if len(v) > 1}
    return conflicts

class CombinePatchesOperator(Operator):
    bl_label = "Combine Patches"
    bl_idname = "helldiver2.combine_patches"
    bl_description = "Combines all loaded patches into a single patch"

    combined_name: StringProperty(name="Combined Mod Name", default="Combined Patch")

    def invoke(self, context, event):
        if len(Global_TocManager.Patches) < 2:
            self.report({'ERROR'}, "Need at least 2 patches to combine")
            return {'CANCELLED'}

        if ArchivesNotLoaded(self):
            return {'CANCELLED'}

        # Detect conflicts
        conflicts = detect_patch_conflicts()

        # Populate conflict list in scene settings
        settings = context.scene.Hd2ToolPanelSettings
        settings.combine_conflicts.clear()

        for (file_id, type_id), patch_names in conflicts.items():
            item = settings.combine_conflicts.add()
            item.file_id = str(file_id)
            item.type_id = str(type_id)
            # Get friendly name (hex without 0x prefix)
            hex_id = format(file_id, 'x')
            item.friendly_name = GetArchiveNameFromID(hex_id) or f"0x{hex_id}"
            item.patches = ",".join(patch_names)

        # Show dialog (wider if conflicts exist)
        width = 500 if len(conflicts) > 0 else 300
        return context.window_manager.invoke_props_dialog(self, width=width)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.Hd2ToolPanelSettings

        # Combined name input
        layout.prop(self, "combined_name")
        layout.separator()

        # Show patch count
        layout.label(text=f"Combining {len(Global_TocManager.Patches)} patches")

        if len(settings.combine_conflicts) > 0:
            layout.separator()
            box = layout.box()
            box.label(text=f"Conflicts ({len(settings.combine_conflicts)}):", icon='ERROR')

            # List conflicts with dropdown for each
            for item in settings.combine_conflicts:
                row = box.row()
                row.label(text=item.friendly_name)
                row.prop(item, "selected_patch", text="")
        else:
            layout.label(text="No conflicts detected", icon='CHECKMARK')

    def execute(self, context):
        settings = context.scene.Hd2ToolPanelSettings

        # Build conflict resolution map: {(file_id, type_id): winning_patch_name}
        resolution = {}
        for item in settings.combine_conflicts:
            key = (int(item.file_id), int(item.type_id))
            resolution[key] = item.selected_patch

        # Create combined patch
        Global_TocManager.CreatePatchFromActive(name=self.combined_name)
        combined_patch = Global_TocManager.Patches[-1]  # Newly created

        # Track which patches to remove (all except combined)
        old_patches = Global_TocManager.Patches[:-1]

        entries_added = 0
        for patch in old_patches:
            for type_id, entries in patch.TocDict.items():
                for file_id, entry in entries.items():
                    key = (file_id, type_id)

                    # Check if this is a conflict
                    if key in resolution:
                        # Only add if this patch is the winner
                        if resolution[key] != patch.Name:
                            continue

                    # Check if already exists in combined
                    existing = combined_patch.GetEntry(file_id, type_id)
                    if existing is None:
                        new_entry = deepcopy(entry)
                        combined_patch.AddEntry(new_entry, override=False)
                        entries_added += 1
                    elif key not in resolution:
                        # Not a user-resolved conflict, use last-wins
                        new_entry = deepcopy(entry)
                        combined_patch.AddEntry(new_entry, override=True)

        # Unload old patches, keep only combined
        Global_TocManager.Patches = [combined_patch]
        Global_TocManager.SetActivePatch(combined_patch)

        self.report({'INFO'}, f"Combined into '{self.combined_name}' ({entries_added} entries)")

        # Redraw UI
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()

        return {'FINISHED'}

def draw_repatch_status(self, context):
    """Draw status text in bottom left of viewport"""
    import blf
    font_id = 0
    blf.size(font_id, 16)
    blf.color(font_id, 1.0, 0.8, 0.2, 1.0)  # Yellow-orange color
    blf.position(font_id, 20, 60, 0)
    blf.draw(font_id, RepatchModOperator._status_text)
    # Draw secondary info
    blf.size(font_id, 12)
    blf.color(font_id, 0.8, 0.8, 0.8, 1.0)  # Light gray
    blf.position(font_id, 20, 40, 0)
    blf.draw(font_id, "Press ESC to cancel")

def repatch_single_unit(file_id, patch, blender_opts, cleanup_objects=False):
    """
    Core repatch logic for a single unit. Used by both RepatchModOperator and RepatchFolderOperator.

    Args:
        file_id: The unit file ID to repatch
        patch: The patch containing the unit entry
        blender_opts: Blender options dict for serialization
        cleanup_objects: If True, removes created Blender objects after processing

    Returns:
        tuple: (success: bool, new_objects: list) - success status and list of created objects
    """
    settings = bpy.context.scene.Hd2ToolPanelSettings

    # Step 1: Import from patch entry
    patch_entry = patch.GetEntry(file_id, UnitID)
    if patch_entry is None:
        PrettyPrint(f"Could not find patch entry for {file_id}")
        return (False, [])

    # Import all mesh types - we want everything from the patch
    settings.AutoLods = True
    settings.ImportStatic = True
    settings.ImportLods = True

    # Use the exact same operator as the UI Import Unit button
    PrettyPrint(f"Importing unit: {file_id}")
    bpy.ops.helldiver2.archive_unit_import(object_id=str(file_id))

    # Find newly created objects - look for objects with matching Z_ObjectID
    new_objects = [obj for obj in bpy.context.scene.objects
                  if obj.get('Z_ObjectID') == str(file_id) and obj.type == 'MESH']
    PrettyPrint(f"Found {len(new_objects)} mesh objects for unit {file_id}")

    if len(new_objects) == 0:
        PrettyPrint(f"No mesh objects created for unit {file_id}, skipping")
        return (False, [])

    # Step 2: Store old MeshInfoIndex from imported patch object
    old_mesh_info_index = new_objects[0].get('MeshInfoIndex', 0)
    PrettyPrint(f"Old MeshInfoIndex from patch: {old_mesh_info_index}")

    # Step 3: Ensure game archive is loaded, then remove entry from patch and add fresh
    Global_TocManager.GetEntryByLoadArchive(file_id, UnitID)
    Global_TocManager.RemoveEntryFromPatch(file_id, UnitID)
    Global_TocManager.AddEntryToPatch(file_id, UnitID)

    # Step 4: Load fresh entry from game archive (without Blender objects)
    new_entry = Global_TocManager.GetEntry(file_id, UnitID)
    if new_entry is None:
        PrettyPrint(f"Could not create new entry for {file_id}")
        if cleanup_objects:
            for obj in new_objects:
                bpy.data.objects.remove(obj)
            return (False, [])
        return (False, new_objects)

    new_entry.Load(Reload=False, MakeBlendObject=False, LoadMaterialSlotNames=True)

    # Step 5: Find new MeshInfoIndex for LOD 0 and update if changed
    new_mesh_info_index = None
    for mesh in new_entry.LoadedData.RawMeshes:
        if mesh.LodIndex == 0:
            new_mesh_info_index = mesh.MeshInfoIndex
            break

    if new_mesh_info_index is not None and old_mesh_info_index != new_mesh_info_index:
        PrettyPrint(f"Updating MeshInfoIndex: {old_mesh_info_index} -> {new_mesh_info_index}")
        for obj in new_objects:
            if obj.get('MeshInfoIndex') == old_mesh_info_index:
                obj['MeshInfoIndex'] = new_mesh_info_index

    # Step 6: Select all new objects and extract mesh data
    bpy.ops.object.select_all(action='DESELECT')
    for obj in new_objects:
        obj.select_set(True)
    if len(new_objects) > 0:
        bpy.context.view_layer.objects.active = new_objects[0]

    # Step 7: Extract mesh data from Blender objects and replace in entry
    mesh_data = GetObjectsMeshData(Global_TocManager, Global_BoneNames)
    obj_id = str(file_id)
    if obj_id in mesh_data:
        for mesh_index, mesh in mesh_data[obj_id].items():
            try:
                new_entry.LoadedData.RawMeshes[mesh_index] = mesh
            except IndexError:
                PrettyPrint(f"MeshInfoIndex {mesh_index} exceeds mesh count for unit {file_id}")

    # Step 8: Save
    success = new_entry.Save(BlenderOpts=blender_opts)
    if success:
        PrettyPrint(f"Saved unit: {file_id}")
    else:
        PrettyPrint(f"Failed to save unit {file_id}")

    # Cleanup objects if requested
    if cleanup_objects:
        for obj in new_objects:
            bpy.data.objects.remove(obj)
        new_objects = []

    return (success, new_objects)

class RepatchModOperator(Operator):
    bl_label = "Repatch Units"
    bl_idname = "helldiver2.repatch_mod"
    bl_description = "Imports mod meshes into Blender, reloads from game archives, and re-saves. Use after game updates"

    _timer = None
    _draw_handler = None
    _state = "INIT"
    _status_text = ""
    _unit_file_ids = []
    _imported_objects = []
    _mesh_data = {}
    _ids = []
    _current_index = 0
    _units_saved = 0
    _units_failed = 0
    _blender_opts = None
    _patch = None

    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            self.report({'WARNING'}, "Repatch cancelled by user")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # Process based on current state
            if self._state == "IMPORTING":
                return self.process_import(context)
            elif self._state == "DONE":
                return self.finish(context)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        self._patch = Global_TocManager.ActivePatch

        # Collect unit entries
        self._unit_file_ids = []
        if UnitID in self._patch.TocDict:
            for file_id in list(self._patch.TocDict[UnitID].keys()):
                self._unit_file_ids.append(file_id)

        if len(self._unit_file_ids) == 0:
            self.report({'WARNING'}, "No unit entries found in patch")
            return {'CANCELLED'}

        # Initialize state
        self._state = "IMPORTING"
        self._current_index = 0
        self._imported_objects = []
        self._mesh_data = {}
        self._ids = []
        self._units_saved = 0
        self._units_failed = 0
        self._existing_objects = set(bpy.context.scene.objects)
        self._blender_opts = bpy.context.scene.Hd2ToolPanelSettings.get_settings_dict()
        self._tried_static = False  # Track if we've tried static mesh import
        self._current_old_mesh_info_index = None  # Track MeshInfoIndex from patch

        # Store original settings (we'll restore them when done)
        settings = bpy.context.scene.Hd2ToolPanelSettings
        self._orig_import_lods = settings.ImportLods
        self._orig_import_static = settings.ImportStatic
        self._orig_auto_lods = settings.AutoLods

        PrettyPrint(f"Found {len(self._unit_file_ids)} unit entries to repatch")
        context.window_manager.progress_begin(0, len(self._unit_file_ids) * 2)

        # Set initial status
        RepatchModOperator._status_text = f"Repatch: Starting... (0/{len(self._unit_file_ids)} units)"

        # Add draw handler for status text
        RepatchModOperator._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_repatch_status, (self, context), 'WINDOW', 'POST_PIXEL')

        # Start timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def process_import(self, context):
        """Process one unit at a time: import from patch, save to new archive data, cleanup"""
        if self._current_index >= len(self._unit_file_ids):
            # Done with all units
            self._state = "DONE"
            return {'PASS_THROUGH'}

        file_id = self._unit_file_ids[self._current_index]

        # Update status
        RepatchModOperator._status_text = f"Repatch: Processing unit {self._current_index + 1}/{len(self._unit_file_ids)}"

        try:
            # Use shared repatch function (keep objects in scene for inspection)
            success, new_objects = repatch_single_unit(file_id, self._patch, self._blender_opts, cleanup_objects=False)

            if success:
                self._units_saved += 1
            else:
                self._units_failed += 1

        except Exception as e:
            PrettyPrint(f"Error processing unit {file_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            self._units_failed += 1

        context.window_manager.progress_update(self._current_index)
        self._current_index += 1

        # Redraw UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'PASS_THROUGH'}

    def finish(self, context):
        self.cancel(context)
        context.window_manager.progress_end()

        if self._units_failed > 0:
            self.report({'WARNING'}, f"Repatched {self._units_saved} units, {self._units_failed} failed")
        else:
            self.report({'INFO'}, f"Repatched {self._units_saved} units successfully")

        return {'FINISHED'}

    def cancel(self, context):
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        if RepatchModOperator._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(RepatchModOperator._draw_handler, 'WINDOW')
            RepatchModOperator._draw_handler = None
        # Restore original settings
        try:
            settings = bpy.context.scene.Hd2ToolPanelSettings
            if hasattr(self, '_orig_import_lods'):
                settings.ImportLods = self._orig_import_lods
            if hasattr(self, '_orig_import_static'):
                settings.ImportStatic = self._orig_import_static
            if hasattr(self, '_orig_auto_lods'):
                settings.AutoLods = self._orig_auto_lods
        except Exception:
            pass  # Scene may not exist during shutdown
        # Force redraw to clear status text
        for area in context.screen.areas:
            area.tag_redraw()

def draw_repatch_folder_status(self, context):
    """Draw status text in bottom left of viewport for folder repatch"""
    import blf
    font_id = 0
    blf.size(font_id, 16)
    blf.color(font_id, 1.0, 0.8, 0.2, 1.0)  # Yellow-orange color
    blf.position(font_id, 20, 80, 0)
    blf.draw(font_id, RepatchFolderOperator._status_text)
    # Draw secondary info
    blf.size(font_id, 12)
    blf.color(font_id, 0.8, 0.8, 0.8, 1.0)  # Light gray
    blf.position(font_id, 20, 60, 0)
    blf.draw(font_id, RepatchFolderOperator._status_text2)
    blf.position(font_id, 20, 40, 0)
    blf.draw(font_id, "Press ESC to cancel")

class RepatchFolderOperator(Operator, ImportHelper):
    bl_label = "Repatch Folder"
    bl_idname = "helldiver2.repatch_folder"
    bl_description = "Loads each patch in folder, runs full repatch (import from patch, reload from game, re-save), then writes patch"

    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default='*', options={'HIDDEN'})

    _timer = None
    _draw_handler = None
    _state = "INIT"
    _status_text = ""
    _status_text2 = ""

    # Patch-level tracking
    _patch_files = []
    _current_patch_index = 0
    _patches_completed = 0
    _patches_failed = 0

    # Unit-level tracking (within current patch)
    _unit_file_ids = []
    _current_unit_index = 0
    _units_saved = 0
    _units_failed = 0

    _blender_opts = None
    _existing_objects = set()

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        folder_path = self.directory
        if not folder_path or not os.path.isdir(folder_path):
            self.report({'ERROR'}, "Invalid folder selected")
            return {'CANCELLED'}

        # Find all .patch_0 files in the folder (only patch_0, not other patch numbers)
        self._patch_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.patch_0'):
                    self._patch_files.append(os.path.join(root, file))

        if len(self._patch_files) == 0:
            self.report({'ERROR'}, "No .patch_0 files found in folder")
            return {'CANCELLED'}

        # Initialize state
        self._state = "LOADING_PATCH"
        self._current_patch_index = 0
        self._patches_completed = 0
        self._patches_failed = 0
        self._unit_file_ids = []
        self._current_unit_index = 0
        self._units_saved = 0
        self._units_failed = 0
        self._blender_opts = bpy.context.scene.Hd2ToolPanelSettings.get_settings_dict()
        self._existing_objects = set(bpy.context.scene.objects)

        # Store original settings
        settings = bpy.context.scene.Hd2ToolPanelSettings
        self._orig_import_lods = settings.ImportLods
        self._orig_import_static = settings.ImportStatic
        self._orig_auto_lods = settings.AutoLods

        PrettyPrint(f"Found {len(self._patch_files)} patch files to repatch")

        # Set initial status
        RepatchFolderOperator._status_text = f"Repatch Folder: Starting... (0/{len(self._patch_files)} patches)"
        RepatchFolderOperator._status_text2 = ""

        # Add draw handler for status text
        RepatchFolderOperator._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_repatch_folder_status, (self, context), 'WINDOW', 'POST_PIXEL')

        # Start timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            self.report({'WARNING'}, "Repatch folder cancelled by user")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self._state == "LOADING_PATCH":
                return self.load_next_patch(context)
            elif self._state == "IMPORTING":
                return self.process_unit(context)
            elif self._state == "WRITING_PATCH":
                return self.write_patch(context)
            elif self._state == "DONE":
                return self.finish(context)

        return {'PASS_THROUGH'}

    def load_next_patch(self, context):
        """Load the next patch file"""
        if self._current_patch_index >= len(self._patch_files):
            self._state = "DONE"
            return {'PASS_THROUGH'}

        patch_path = self._patch_files[self._current_patch_index]
        patch_name = os.path.basename(patch_path)

        RepatchFolderOperator._status_text = f"Repatch Folder: Loading patch {self._current_patch_index + 1}/{len(self._patch_files)}"
        RepatchFolderOperator._status_text2 = f"File: {patch_name}"

        try:
            PrettyPrint(f"Loading patch: {patch_path}")

            # Load as the active patch
            Global_TocManager.LoadArchive(patch_path, SetActive=True, IsPatch=True)

            if Global_TocManager.ActivePatch is None:
                PrettyPrint(f"Failed to load patch: {patch_path}")
                self._patches_failed += 1
                self._current_patch_index += 1
                return {'PASS_THROUGH'}

            # Collect unit entries from this patch
            self._unit_file_ids = []
            if UnitID in Global_TocManager.ActivePatch.TocDict:
                for file_id in list(Global_TocManager.ActivePatch.TocDict[UnitID].keys()):
                    self._unit_file_ids.append(file_id)

            if len(self._unit_file_ids) == 0:
                PrettyPrint(f"No unit entries found in patch {patch_name}, writing and moving on")
                # No units to process, just write and move on
                self._state = "WRITING_PATCH"
            else:
                # Reset unit tracking for this patch
                self._current_unit_index = 0
                self._units_saved = 0
                self._units_failed = 0
                PrettyPrint(f"Found {len(self._unit_file_ids)} units to repatch in {patch_name}")
                self._state = "IMPORTING"

        except Exception as e:
            PrettyPrint(f"Error loading patch {patch_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            self._patches_failed += 1
            self._current_patch_index += 1

        return {'PASS_THROUGH'}

    def process_unit(self, context):
        """Process one unit at a time using shared repatch logic"""
        if self._current_unit_index >= len(self._unit_file_ids):
            # Done with all units for this patch, write it
            self._state = "WRITING_PATCH"
            return {'PASS_THROUGH'}

        file_id = self._unit_file_ids[self._current_unit_index]
        patch_name = os.path.basename(self._patch_files[self._current_patch_index])

        # Update status
        RepatchFolderOperator._status_text = f"Repatch Folder: Patch {self._current_patch_index + 1}/{len(self._patch_files)}"
        RepatchFolderOperator._status_text2 = f"{patch_name}: Unit {self._current_unit_index + 1}/{len(self._unit_file_ids)}"

        try:
            # Use shared repatch function (keep objects in scene for inspection)
            success, _ = repatch_single_unit(file_id, Global_TocManager.ActivePatch, self._blender_opts, cleanup_objects=False)

            if success:
                self._units_saved += 1
            else:
                self._units_failed += 1

        except Exception as e:
            PrettyPrint(f"Error processing unit {file_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            self._units_failed += 1

        self._current_unit_index += 1

        # Redraw UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'PASS_THROUGH'}

    def write_patch(self, context):
        """Write the current patch and move to next"""
        patch_path = self._patch_files[self._current_patch_index]
        patch_name = os.path.basename(patch_path)

        RepatchFolderOperator._status_text = f"Repatch Folder: Writing patch {self._current_patch_index + 1}/{len(self._patch_files)}"
        RepatchFolderOperator._status_text2 = f"File: {patch_name}"

        try:
            # Write the patch
            Global_TocManager.PatchActiveArchive()
            PrettyPrint(f"Wrote patch: {patch_name} ({self._units_saved} units saved, {self._units_failed} failed)")
            self._patches_completed += 1
        except Exception as e:
            PrettyPrint(f"Error writing patch {patch_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            self._patches_failed += 1

        # Move to next patch
        self._current_patch_index += 1

        # Unload patches to prepare for next one
        Global_TocManager.UnloadPatches()

        self._state = "LOADING_PATCH"

        # Redraw UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'PASS_THROUGH'}

    def finish(self, context):
        self.cancel(context)

        total_patches = len(self._patch_files)
        if self._patches_failed > 0:
            self.report({'WARNING'}, f"Repatched {self._patches_completed}/{total_patches} patches, {self._patches_failed} failed")
        else:
            self.report({'INFO'}, f"Repatched {self._patches_completed}/{total_patches} patches successfully")

        return {'FINISHED'}

    def cancel(self, context):
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        if RepatchFolderOperator._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(RepatchFolderOperator._draw_handler, 'WINDOW')
            RepatchFolderOperator._draw_handler = None
        # Restore original settings
        try:
            settings = bpy.context.scene.Hd2ToolPanelSettings
            if hasattr(self, '_orig_import_lods'):
                settings.ImportLods = self._orig_import_lods
            if hasattr(self, '_orig_import_static'):
                settings.ImportStatic = self._orig_import_static
            if hasattr(self, '_orig_auto_lods'):
                settings.AutoLods = self._orig_auto_lods
        except Exception:
            pass
        # Force redraw
        for area in context.screen.areas:
            area.tag_redraw()

class NextArchiveOperator(Operator):
    bl_label = "Next Archive"
    bl_idname = "helldiver2.next_archive"
    bl_description = "Select the next archive in the list of loaded archives"

    def execute(self, context):
        for index in range(len(Global_TocManager.LoadedArchives)):
            if Global_TocManager.LoadedArchives[index] == Global_TocManager.ActiveArchive:
                nextIndex = min(len(Global_TocManager.LoadedArchives) - 1, index + 1)
                bpy.context.scene.Hd2ToolPanelSettings.LoadedArchives = Global_TocManager.LoadedArchives[nextIndex].Name
                return {'FINISHED'}
        return {'CANCELLED'}
#endregion

#region Operators: Entries

class ArchiveEntryOperator(Operator):
    bl_label  = "Archive Entry"
    bl_idname = "helldiver2.archive_entry"

    list_id: StringProperty()
    list_index: IntProperty()
    def execute(self, context):
        return{'FINISHED'}

    def invoke(self, context, event):
        ui_list = getattr(context.scene, self.list_id)
        list_item = ui_list[self.list_index]
        current_list_index = getattr(context.scene, self.list_id.replace("list", "index"))
        if event.ctrl:
            list_item.item_selected = not list_item.item_selected
        elif event.shift:
            upper = max(self.list_index, current_list_index)
            lower = min(self.list_index, current_list_index)
            selected_range = list(range(lower, upper+1))
            for i, item in enumerate(ui_list):
                if i in selected_range:
                    item.item_selected = True
                else:
                    item.item_selected = False
        else:
            for item in ui_list:
                item.item_selected = False
            list_item.item_selected = True        
        setattr(context.scene, self.list_id.replace("list", "index"), self.list_index)
        return {'FINISHED'}
    
class MaterialTextureEntryOperator(Operator):
    bl_label  = "Texture Entry"
    bl_idname = "helldiver2.material_texture_entry"

    object_id: StringProperty()
    object_typeid: StringProperty()

    texture_index: StringProperty()
    material_id: StringProperty()

    def execute(self, context):
        return{'FINISHED'}

    def invoke(self, context, event):
        return {'FINISHED'}
        
class StateMachineBlendMaskWeightOperator(Operator):
    bl_label = "Blend Mask"
    bl_idname = "helldiver2.blend_mask_weight"
    bl_description = "Blend Mask Bone Weight"
    
    object_id: StringProperty()
    blend_mask_index: bpy.props.IntProperty()
    bone_index: bpy.props.IntProperty()
    bone_weight: bpy.props.FloatProperty(min = 0.0, max = 1.0)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bone_weight")
        
    def execute(self, context):
        Entry = Global_TocManager.GetEntry(self.object_id, StateMachineID)
        if Entry:
            Entry.LoadedData.blend_masks[self.blend_mask_index].bone_weights[self.bone_index] = self.bone_weight
        else:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
        
class StateMachineSaveOperator(Operator):
    bl_label = "Save State Machine"
    bl_idname = "helldiver2.state_machine_save"
    bl_description = "Save State Machine"
    
    object_id: StringProperty()
    
    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            Global_TocManager.Save(int(EntryID), StateMachineID)
        return{'FINISHED'}
    
class MaterialShaderVariableEntryOperator(Operator):
    bl_label = "Shader Variable"
    bl_idname = "helldiver2.material_shader_variable"
    bl_description = "Material Shader Variable"

    object_id: StringProperty()
    variable_index: bpy.props.IntProperty()
    value_index: bpy.props.IntProperty()
    value: bpy.props.FloatProperty(
        name="Variable Value",
        description="Enter a floating point number"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value")

    def execute(self, context):
        Entry = Global_TocManager.GetEntry(self.object_id, MaterialID)
        if Entry:
            Entry.LoadedData.ShaderVariables[self.variable_index].values[self.value_index] = self.value
            PrettyPrint(f"Set value to: {self.value} at variable: {self.variable_index} value: {self.value_index} for material ID: {self.object_id}")
        else:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
class MaterialShaderVariableColorEntryOperator(Operator):
    bl_label = "Color Picker"
    bl_idname = "helldiver2.material_shader_variable_color"
    bl_description = "Material Shader Variable Color"

    object_id: StringProperty()
    variable_index: bpy.props.IntProperty()
    color: bpy.props.FloatVectorProperty(
                name=f"Color",
                subtype="COLOR",
                size=3,
                min=0.0,
                max=1.0,
                default=(1.0, 1.0, 1.0)
            )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "color")

    def execute(self, context):
        Entry = Global_TocManager.GetEntry(self.object_id, MaterialID)
        if Entry:
            for idx in range(3):
                Entry.LoadedData.ShaderVariables[self.variable_index].values[idx] = self.color[idx]
            PrettyPrint(f"Set color to: {self.color}for material ID: {self.object_id}")
        else:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}
        
        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()

        return {'FINISHED'}
    
    def invoke(self, context, event):
        Entry = Global_TocManager.GetEntry(self.object_id, MaterialID)
        if Entry:
            for idx in range(3):
                self.color[idx] = Entry.LoadedData.ShaderVariables[self.variable_index].values[idx]
        else:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

class AddEntryToPatchOperator(Operator):
    bl_label = "Add To Patch"
    bl_idname = "helldiver2.archive_addtopatch"
    bl_description = "Adds Entry into Patch"

    object_id: StringProperty()
    object_typeid: StringProperty()
    def execute(self, context):
        if PatchesNotLoaded(self):
            return{'CANCELLED'}
        
        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        for Entry in Entries:
            Global_TocManager.AddEntryToPatch(Entry.FileID, Entry.TypeID)
        return{'FINISHED'}

class RemoveEntryFromPatchOperator(Operator):
    bl_label = "Remove Entry From Patch"
    bl_idname = "helldiver2.archive_removefrompatch"

    object_id: StringProperty()
    object_typeid: StringProperty()
    def execute(self, context):
        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        for Entry in Entries:
            Global_TocManager.RemoveEntryFromPatch(Entry.FileID, Entry.TypeID)
        LoadEntryLists()
        return{'FINISHED'}

class UndoArchiveEntryModOperator(Operator):
    bl_label = "Remove Modifications"
    bl_idname = "helldiver2.archive_undo_mod"

    object_id: StringProperty()
    object_typeid: StringProperty()
    def execute(self, context):
        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        for Entry in Entries:
            if Entry != None:
                Entry.UndoModifiedData()
        return{'FINISHED'}

class DuplicateEntryOperator(Operator):
    bl_label = "Duplicate Entry"
    bl_idname = "helldiver2.archive_duplicate"
    bl_description = "Duplicate Selected Entry"

    def draw(self, context):
        layout = self.layout; row = layout.row()
        row.operator("helldiver2.generate_random_id", icon="FILE_REFRESH")
        row = layout.row()
        row.prop(context.scene, "new_id_entry", icon="FILE_REFRESH")

    object_id: StringProperty()
    object_typeid: StringProperty()
    def execute(self, context):
        if Global_TocManager.ActivePatch == None:
            context.scene.new_id_entry = ""
            self.report({'ERROR'}, "No Patches Currently Loaded")
            return {'CANCELLED'}
        if context.scene.new_id_entry == "":
            self.report({'ERROR'}, "No ID was given")
            return {'CANCELLED'}
        Global_TocManager.DuplicateEntry(int(self.object_id), int(self.object_typeid), int(context.scene.new_id_entry))
        if int(self.object_typeid) == MaterialID:
            material = bpy.data.materials.get(self.object_id)
            new_material = bpy.data.materials.get(context.scene.new_id_entry)
            if material and not new_material:
                dup = material.copy()
                dup.name = context.scene.new_id_entry
        context.scene.new_id_entry = ""
        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
class GenerateEntryIDOperator(Operator):
    bl_label = "Generate Random ID"
    bl_idname = "helldiver2.generate_random_id"
    bl_description = "Generates a random ID for the entry"

    def execute(self, context):
        context.scene.new_id_entry = str(RandomHash16())
        PrettyPrint(f"Generated random ID: {context.scene.new_id_entry}")
        return{'FINISHED'}

class RenamePatchEntryOperator(Operator):
    bl_label = "Rename Entry"
    bl_idname = "helldiver2.archive_entryrename"

    NewFileID : StringProperty(name="NewFileID", default="")
    def draw(self, context):
        layout = self.layout; row = layout.row()
        row.prop(self, "NewFileID", icon='COPY_ID')

    object_id: StringProperty()
    object_typeid: StringProperty()

    material_id: StringProperty(default="")
    texture_index: StringProperty(default="")
    def execute(self, context):
        Entry = Global_TocManager.GetPatchEntry_B(int(self.object_id), int(self.object_typeid))
        if Entry == None and self.material_id == "":
            raise Exception(f"Entry does not exist in patch (cannot rename non patch entries) ID: {self.object_id} TypeID: {self.object_typeid}")
        if Entry != None and self.NewFileID != "":
            Global_TocManager.RemoveEntryFromPatch(Entry.FileID, Entry.TypeID)
            Global_TocManager.AddEntryToPatchID(Entry, int(self.NewFileID))

        # Are we renaming via a texture entry in a material?
        if self.material_id != "" and self.texture_index != "":
            MaterialEntry = Global_TocManager.GetPatchEntry_B(int(self.material_id), int(MaterialID))
            MaterialEntry.LoadedData.TexIDs[int(self.texture_index)] = int(self.NewFileID)
            
            
        # Are we renaming a material? (duplicate Blender material if it exists and give it the new name)
        if int(self.object_typeid) == MaterialID:
            material = bpy.data.materials.get(self.object_id)
            if material:
                material.name = self.NewFileID

        # Redraw
        LoadEntryLists()
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
            
        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

class DumpArchiveObjectOperator(Operator):
    bl_label = "Dump Archive Object"
    bl_idname = "helldiver2.archive_object_dump_export"
    bl_description = "Dumps Entry's Contents"

    directory: StringProperty(name="Outdir Path",description="dump output dir")
    filter_folder: BoolProperty(default=True,options={"HIDDEN"})

    object_id: StringProperty(options={"HIDDEN"})
    object_typeid: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        for Entry in Entries:
            if Entry != None:
                data = Entry.GetData()
                FileName = str(Entry.FileID)+"."+GetTypeNameFromID(Entry.TypeID)
                with open(self.directory + FileName, 'w+b') as f:
                    f.write(data[0])
                if data[1] != b"":
                    with open(self.directory + FileName+".gpu", 'w+b') as f:
                        f.write(data[1])
                if data[2] != b"":
                    with open(self.directory + FileName+".stream", 'w+b') as f:
                        f.write(data[2])
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ImportDumpOperator(Operator, ImportHelper):
    bl_label = "Import Dump"
    bl_idname = "helldiver2.archive_object_dump_import"
    bl_description = "Loads Raw Dump"

    object_id: StringProperty(options={"HIDDEN"})
    object_typeid: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        for Entry in Entries:
            ImportDump(self, Entry, self.filepath)

        return{'FINISHED'}

class ImportDumpByIDOperator(Operator, ImportHelper):
    bl_label = "Import Dump by Entry ID"
    bl_idname = "helldiver2.archive_object_dump_import_by_id"
    bl_description = "Loads Raw Dump over matching entry IDs"

    directory: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: CollectionProperty(type=OperatorFileListElement, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        for file in self.files:
            filepath = self.directory + file.name
            fileID = file.name.split('.')[0]
            typeString = file.name.split('.')[1]
            typeID = GetIDFromTypeName(typeString)

            if typeID == None:
                self.report({'ERROR'}, f"File: {file.name} has no proper file extension for typing")
                return {'CANCELLED'}
            
            if os.path.exists(filepath):
                PrettyPrint(f"Found file: {filepath}")
            else:
                self.report({'ERROR'}, f"Filepath for selected file: {filepath} was not found")
                return {'CANCELLED'}

            entry = Global_TocManager.GetEntryByLoadArchive(int(fileID), int(typeID))
            if entry == None:
                self.report({'ERROR'}, f"Entry for fileID: {fileID} typeID: {typeID} can not be found. Make sure the fileID of your file is correct.")
                return {'CANCELLED'}
            
            ImportDump(self, entry, filepath)
            
        return{'FINISHED'}

def ImportDump(self: Operator, Entry: TocEntry, filepath: str):
    if Entry != None:
        if not Entry.IsLoaded: Entry.Load(False, False)
        path = filepath
        GpuResourchesPath = f"{path}.gpu"
        StreamPath = f"{path}.stream"

        with open(path, 'r+b') as f:
            Entry.TocData = f.read()

        if os.path.isfile(GpuResourchesPath):
            with open(GpuResourchesPath, 'r+b') as f:
                Entry.GpuData = f.read()
        else:
            Entry.GpuData = b""

        if os.path.isfile(StreamPath):
            with open(StreamPath, 'r+b') as f:
                Entry.StreamData = f.read()
        else:
            Entry.StreamData = b""

        Entry.IsModified = True
        if not Global_TocManager.IsInPatch(Entry):
            Global_TocManager.AddEntryToPatch(Entry.FileID, Entry.TypeID)
            
        self.report({'INFO'}, f"Imported Raw Dump: {path}")
    

#endregion

#region Operators: Meshes

class ImportStingrayUnitOperator(Operator):
    bl_label = "Import Archive Unit"
    bl_idname = "helldiver2.archive_unit_import"
    bl_description = "Loads Unit into Blender Scene"

    object_id: StringProperty()
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        Errors = []
        for EntryID in EntriesIDs:
            if len(EntriesIDs) == 1:
                Global_TocManager.Load(EntryID, UnitID)
            else:
                # try:
                Global_TocManager.Load(EntryID, UnitID)
                # except Exception as error:
                #     Errors.append([EntryID, error])

        # if len(Errors) > 0:
        #     PrettyPrint("\nThese errors occurred while attempting to load meshes...", "error")
        #     idx = 0
        #     for error in Errors:
        #         PrettyPrint(f"  Error {idx}: for mesh {error[0]}", "error")
        #         PrettyPrint(f"    {error[1]}\n", "error")
        #         idx += 1
        #     raise Exception("One or more meshes failed to load")
        return{'FINISHED'}

class ImportMeshWithShaderOperator(Operator):
    bl_label = "Import Mesh with Shader"
    bl_idname = "helldiver2.import_mesh_with_shader"
    bl_description = "Import mesh with accurate shader using filediver"

    object_id: StringProperty()

    def execute(self, context):
        global Global_filediverpath, Global_filediverpathIsValid, Global_gamepath

        # Validate filediver path
        if not Global_filediverpathIsValid:
            self.report({'ERROR'}, "Filediver path not set. Please set it in Settings.")
            context.scene.Hd2ToolPanelSettings.MenuExpanded = True
            return {'CANCELLED'}

        if not Global_gamepathIsValid:
            self.report({'ERROR'}, "Game path not set. Please set it in Settings.")
            context.scene.Hd2ToolPanelSettings.MenuExpanded = True
            return {'CANCELLED'}

        # Parse object_id - can be comma-separated list of decimal IDs
        selected_ids = []
        if self.object_id:
            for id_str in self.object_id.split(','):
                id_str = id_str.strip()
                if id_str:
                    try:
                        selected_ids.append(int(id_str))
                    except ValueError:
                        pass

        PrettyPrint(f"Selected unit FileIDs to import: {[hex(id) for id in selected_ids]}")

        # Get the archive ID from the active archive or the unit's object ID
        archive_id = None
        if selected_ids:
            # Try to find which archive contains the first unit
            entry = Global_TocManager.GetEntry(selected_ids[0], UnitID)
            if entry and hasattr(entry, 'ParentToc') and entry.ParentToc:
                archive_id = entry.ParentToc.Name
        if not archive_id and Global_TocManager.ActiveArchive:
            archive_id = Global_TocManager.ActiveArchive.Name

        if not archive_id:
            self.report({'ERROR'}, "No archive loaded. Please load an archive first.")
            return {'CANCELLED'}

        # Ensure archive_id has 0x prefix for filediver
        if not archive_id.startswith("0x"):
            archive_id = "0x" + archive_id

        # Step 1: Import regular meshes using SDK import (keeps HD2 properties like Z_ObjectID)
        sdk_objects = []
        sdk_fileid_map = {}  # Maps FileID (int) -> list of sdk_obj
        if selected_ids:
            objects_before = set(bpy.data.objects)

            # Do regular SDK import for each selected ID
            for file_id in selected_ids:
                try:
                    bpy.ops.helldiver2.archive_unit_import(object_id=str(file_id))
                except Exception as e:
                    PrettyPrint(f"SDK import failed for {hex(file_id)}: {e}", 'WARNING')

            # Find newly created objects and build FileID map
            sdk_objects = list(set(bpy.data.objects) - objects_before)
            for obj in sdk_objects:
                if obj.type == 'MESH' and obj.data:
                    # Get Z_ObjectID (the FileID) from the object
                    z_object_id = obj.get("Z_ObjectID")
                    if z_object_id:
                        try:
                            file_id = int(z_object_id)
                            if file_id not in sdk_fileid_map:
                                sdk_fileid_map[file_id] = []
                            sdk_fileid_map[file_id].append(obj)
                        except (ValueError, TypeError):
                            pass

            PrettyPrint(f"SDK import created {len(sdk_objects)} objects with {len(sdk_fileid_map)} unique FileIDs")

        # Create temp directory for output in Blender's temp folder
        temp_dir = os.path.join(bpy.app.tempdir, "filediver_exports")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # Build filediver command
            filediver_exe = os.path.join(Global_filediverpath, "filediver.exe")
            # Filediver expects game root folder, not the data subfolder
            game_root = Global_gamepath.rstrip("\\/")
            if game_root.lower().endswith("data"):
                game_root = os.path.dirname(game_root)
            cmd = [
                filediver_exe,
                "-g", game_root,
                "-T", "unit",
                "--model-format", "glb",
                "--unit-single-file",
                "-t", archive_id,
                "-o", temp_dir
            ]

            PrettyPrint(f"Running filediver: {' '.join(cmd)}")

            # Run filediver
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                PrettyPrint(f"Filediver error: {result.stderr}", 'ERROR')
                self.report({'ERROR'}, f"Filediver failed: {result.stderr[:200]}")
                return {'CANCELLED'}

            PrettyPrint(f"Filediver output: {result.stdout}")

            # Find the output glb file
            glb_file = None
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.endswith('.glb'):
                        glb_file = os.path.join(root, f)
                        break
                if glb_file:
                    break

            if not glb_file:
                self.report({'ERROR'}, "Filediver did not produce a .glb file")
                return {'CANCELLED'}

            # Check for hd2_accurate_blender_importer
            importer_exe = os.path.join(Global_filediverpath, "scripts_dist", "hd2_accurate_blender_importer", "hd2_accurate_blender_importer.exe")

            if os.path.exists(importer_exe):
                # Use the accurate blender importer
                blend_output = os.path.join(temp_dir, "output_with_shader.blend")
                importer_cmd = [importer_exe, glb_file, blend_output, "--packall"]

                PrettyPrint(f"Running importer: {' '.join(importer_cmd)}")

                importer_result = subprocess.run(importer_cmd, capture_output=True, text=True, timeout=300)

                if importer_result.returncode != 0:
                    PrettyPrint(f"Importer error: {importer_result.stderr}", 'ERROR')
                    self.report({'WARNING'}, "Accurate importer failed, SDK meshes kept without shaders")
                else:
                    # Import filediver blend and transfer materials to SDK objects
                    PrettyPrint(f"Importing blend file and transferring materials: {blend_output}")
                    self._import_and_transfer_materials(blend_output, context, sdk_fileid_map, glb_file)

                    # Create SimpleBake local presets for HD2 materials
                    self._create_simplebake_local_presets(context)

                    # Add imported objects to SimpleBake's bake list
                    self._add_objects_to_simplebake_list(context, sdk_objects)
            else:
                self.report({'INFO'}, "Accurate importer not found, SDK meshes kept without shaders")

            num_units = len(selected_ids) if selected_ids else "all"
            self.report({'INFO'}, f"Imported {num_units} mesh(es) with shader from archive {archive_id}")
            return {'FINISHED'}

        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "Filediver timed out after 5 minutes")
            return {'CANCELLED'}
        except Exception as e:
            PrettyPrint(f"Error during import: {str(e)}", 'ERROR')
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def _parse_glb_fileid_mapping(self, glb_path):
        """Parse GLB file to extract FileID -> mesh node names mapping.

        The GLB's root 'extras' contains a mapping like:
        {'0x0e26f06370e010d9': {'objects': [21], 'parent': 20, 'skin': 0}, ...}

        Where 'objects' is a list of node indices that have meshes for that FileID.

        Args:
            glb_path: Path to the GLB file

        Returns:
            Dict mapping FileID (int) -> list of mesh node names
        """
        import struct

        fileid_to_meshnames = {}

        try:
            with open(glb_path, 'rb') as f:
                # Read GLB header
                magic = f.read(4)
                if magic != b'glTF':
                    PrettyPrint(f"Invalid GLB file: {glb_path}", 'WARNING')
                    return fileid_to_meshnames

                version = struct.unpack('<I', f.read(4))[0]
                length = struct.unpack('<I', f.read(4))[0]

                # Read JSON chunk
                chunk_len = struct.unpack('<I', f.read(4))[0]
                chunk_type = f.read(4)
                json_data = f.read(chunk_len).decode('utf-8')
                gltf = json.loads(json_data)

                # Get the FileID -> node indices mapping from root extras
                extras = gltf.get('extras', {})
                nodes = gltf.get('nodes', [])

                for fileid_hex, data in extras.items():
                    if not fileid_hex.startswith('0x'):
                        continue

                    try:
                        fileid_int = int(fileid_hex, 16)
                    except ValueError:
                        continue

                    # Get mesh node names for this FileID
                    mesh_names = []
                    object_indices = data.get('objects', [])
                    for node_idx in object_indices:
                        if 0 <= node_idx < len(nodes):
                            node = nodes[node_idx]
                            # Only include nodes that have meshes
                            if 'mesh' in node:
                                mesh_names.append(node.get('name', f'node_{node_idx}'))

                    if mesh_names:
                        fileid_to_meshnames[fileid_int] = mesh_names

                PrettyPrint(f"Parsed GLB: found {len(fileid_to_meshnames)} FileIDs with mesh mappings")

        except Exception as e:
            PrettyPrint(f"Error parsing GLB for FileID mapping: {e}", 'WARNING')

        return fileid_to_meshnames

    def _import_and_transfer_materials(self, blend_path, context, sdk_fileid_map, glb_path):
        """Import filediver .blend file and transfer materials to SDK objects.

        Args:
            blend_path: Path to the filediver .blend file
            context: Blender context
            sdk_fileid_map: Dict mapping FileID (int) -> list of sdk_obj
            glb_path: Path to the GLB file for parsing FileID -> mesh name mapping
        """
        # Parse GLB to get FileID -> mesh names mapping
        fileid_to_meshnames = self._parse_glb_fileid_mapping(glb_path)

        # Import materials, node groups, and images from filediver blend
        # Also import objects temporarily to extract their materials
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects
            data_to.materials = data_from.materials
            data_to.node_groups = data_from.node_groups
            data_to.images = data_from.images

        filediver_objects = [obj for obj in data_to.objects if obj is not None]
        PrettyPrint(f"Loaded {len(filediver_objects)} filediver objects, {len(data_to.materials)} materials")

        # Build filediver name -> object mapping
        # Also map base names (without Blender's .001 suffix) to handle naming conflicts
        filediver_name_map = {}  # Maps mesh name -> filediver object
        filediver_basename_map = {}  # Maps base name (no .NNN suffix) -> filediver object
        import re
        blender_suffix_pattern = re.compile(r'\.\d{3}$')  # Matches .001, .002, etc.

        for obj in filediver_objects:
            if obj.type == 'MESH' and obj.data:
                filediver_name_map[obj.name] = obj
                # Also store by base name (strip .001 suffix if present)
                base_name = blender_suffix_pattern.sub('', obj.name)
                if base_name not in filediver_basename_map:
                    filediver_basename_map[base_name] = obj

        PrettyPrint(f"Filediver mesh names: {list(filediver_name_map.keys())}")
        if filediver_basename_map:
            PrettyPrint(f"Filediver base names: {list(filediver_basename_map.keys())}")

        # Match and transfer materials using FileID -> mesh name mapping
        materials_transferred = 0
        matched_sdk_objects = set()
        unmatched_fileids = []

        for fileid, sdk_objs in sdk_fileid_map.items():
            # Get mesh names for this FileID from the GLB mapping
            mesh_names = fileid_to_meshnames.get(fileid, [])

            if not mesh_names:
                unmatched_fileids.append(hex(fileid))
                continue

            # Find filediver objects matching these mesh names
            for sdk_obj in sdk_objs:
                best_match = None
                best_match_name = None

                # Try to find a matching filediver object by exact name
                for mesh_name in mesh_names:
                    if mesh_name in filediver_name_map:
                        best_match = filediver_name_map[mesh_name]
                        best_match_name = mesh_name
                        break

                # Fallback 1: try basename map (handles Blender's .001 suffix from naming conflicts)
                if best_match is None:
                    for mesh_name in mesh_names:
                        if mesh_name in filediver_basename_map:
                            best_match = filediver_basename_map[mesh_name]
                            best_match_name = mesh_name
                            PrettyPrint(f"  Matched via basename: '{mesh_name}' -> '{best_match.name}'")
                            break

                # Fallback 2: try matching by vertex count if name matching fails
                if best_match is None and sdk_obj.type == 'MESH' and sdk_obj.data:
                    sdk_vert_count = len(sdk_obj.data.vertices)
                    for mesh_name in mesh_names:
                        if mesh_name in filediver_name_map:
                            fd_obj = filediver_name_map[mesh_name]
                            if fd_obj.type == 'MESH' and fd_obj.data:
                                if len(fd_obj.data.vertices) == sdk_vert_count:
                                    best_match = fd_obj
                                    best_match_name = mesh_name
                                    break
                        # Also check basename map for vertex count fallback
                        if mesh_name in filediver_basename_map:
                            fd_obj = filediver_basename_map[mesh_name]
                            if fd_obj.type == 'MESH' and fd_obj.data:
                                if len(fd_obj.data.vertices) == sdk_vert_count:
                                    best_match = fd_obj
                                    best_match_name = mesh_name
                                    break

                if best_match is None:
                    PrettyPrint(f"No filediver match for FileID {hex(fileid)} ({sdk_obj.name})")
                    continue

                # Transfer materials from filediver object to SDK object
                PrettyPrint(f"Transferring materials from '{best_match.name}' to '{sdk_obj.name}' (FileID: {hex(fileid)})")

                # Clear existing materials on SDK object
                sdk_obj.data.materials.clear()

                # Copy materials from filediver object
                for mat_slot in best_match.material_slots:
                    if mat_slot.material:
                        sdk_obj.data.materials.append(mat_slot.material)
                        materials_transferred += 1

                # Copy UV layers that exist on filediver but not SDK (e.g., "UVs for Baking")
                # This is needed for the HD2 shader to work correctly
                sdk_mesh = sdk_obj.data
                fd_mesh = best_match.data
                if len(sdk_mesh.loops) == len(fd_mesh.loops):
                    for fd_uv in fd_mesh.uv_layers:
                        if fd_uv.name not in sdk_mesh.uv_layers:
                            sdk_mesh.uv_layers.new(name=fd_uv.name)
                            sdk_uv = sdk_mesh.uv_layers[fd_uv.name]
                            for i, loop in enumerate(sdk_uv.data):
                                loop.uv = fd_uv.data[i].uv
                            PrettyPrint(f"  Copied UV layer '{fd_uv.name}' ({len(sdk_uv.data)} coords)")

                matched_sdk_objects.add(sdk_obj)

                # Remove this filediver object from the name maps to avoid reuse
                if best_match_name:
                    if best_match_name in filediver_name_map:
                        del filediver_name_map[best_match_name]
                    if best_match_name in filediver_basename_map:
                        del filediver_basename_map[best_match_name]

        if unmatched_fileids:
            PrettyPrint(f"No GLB mapping for FileIDs: {unmatched_fileids}")

        PrettyPrint(f"Transferred materials to {len(matched_sdk_objects)} SDK objects ({materials_transferred} material slots)")

        # Check setting to keep or delete filediver objects
        keep_filediver = context.scene.Hd2ToolPanelSettings.KeepFilediverObjects

        if keep_filediver:
            # Keep filediver objects for debugging (link them to scene)
            filediver_collection_name = "Filediver_Import"
            if filediver_collection_name not in bpy.data.collections:
                filediver_collection = bpy.data.collections.new(filediver_collection_name)
                context.scene.collection.children.link(filediver_collection)
            else:
                filediver_collection = bpy.data.collections[filediver_collection_name]

            for obj in filediver_objects:
                filediver_collection.objects.link(obj)

            PrettyPrint(f"Kept {len(filediver_objects)} filediver objects in '{filediver_collection_name}' collection")
        else:
            # Clean up filediver objects (we only needed them for materials)
            for obj in filediver_objects:
                if obj.type == 'MESH' and obj.data and obj.data.users == 1:
                    mesh_data = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    bpy.data.meshes.remove(mesh_data)
                else:
                    bpy.data.objects.remove(obj, do_unlink=True)
            PrettyPrint(f"Cleaned up {len(filediver_objects)} filediver objects")

        PrettyPrint(f"Imported {len([m for m in data_to.materials if m])} materials, "
                    f"{len([n for n in data_to.node_groups if n])} node groups, "
                    f"{len([i for i in data_to.images if i])} textures")

    def _create_simplebake_local_presets(self, context):
        """Create SimpleBake local (blend file) presets for HD2 material types.

        These presets configure SimpleBake with appropriate settings for baking
        HD2 shader materials to different texture configurations.
        """
        try:
            # Check if SimpleBake is installed
            sbp = getattr(context.scene, 'SimpleBake_Props', None)
            if sbp is None:
                PrettyPrint("SimpleBake not installed, skipping preset creation")
                return
        except:
            PrettyPrint("SimpleBake not available, skipping preset creation")
            return

        # Base preset settings shared by all HD2 presets
        def get_base_preset():
            return {
                "global_mode": "PBR",
                "ray_distance": 0.0,
                "cage_and_ray_multiplier": 0.1,
                "cage_extrusion": 0.0,
                "auto_match_mode": "name",
                "selected_s2a": False,
                "s2a_opmode": "single",
                "merged_bake": False,
                "merged_bake_name": "Merged",
                "cycles_s2a": False,
                "imgheight": 2048,
                "imgwidth": 2048,
                "outputheight": 2048,
                "outputwidth": 2048,
                "everything32bitfloat": False,
                "use_alpha": False,
                "rough_glossy_switch": "Roughness",
                "ccrough_glossy_switch": "Clearcoat Roughness",
                "multiply_diffuse_ao": "purediffuse",
                "multiply_diffuse_ao_percent": 50,
                "normal_format_switch": "OpenGL",
                "tex_per_mat": False,
                "selected_col": True,
                "selected_metal": False,
                "selected_rough": False,
                "selected_normal": True,
                "selected_trans": False,
                "selected_transrough": False,
                "selected_emission": False,
                "selected_emission_strength": False,
                "selected_sss": False,
                "selected_sss_scale": False,
                "selected_ssscol": False,
                "selected_clearcoat": False,
                "selected_clearcoat_rough": False,
                "selected_specular": False,
                "selected_alpha": False,
                "selected_col_mats": False,
                "selected_col_vertex": False,
                "selected_ao": False,
                "selected_thickness": False,
                "selected_curvature": False,
                "selected_lightmap": False,
                "selected_displacement": False,
                "lightmap_apply_colman": True,
                "new_uv_option": False,
                "prefer_existing_sbmap": False,
                "new_uv_method": "SmartUVProject_Atlas",
                "restore_orig_uv_map": True,
                "uvpackmargin": 0.003,
                "average_uv_size": False,
                "expand_mat_uvs": False,
                "auto_detect_udims": True,
                "unwrapmargin": 0.0,
                "uvcorrectaspect": True,
                "channelpackfileformat": "PNG",
                "del_cptex_components": False,
                "save_bakes_external": False,
                "export_folder_per_object": False,
                "export_mesh_individual_or_combined": "individual",
                "export_format": "fbx",
                "jpeg_quality": 90,
                "save_obj_external": False,
                "merge_export_obj": False,
                "mesh_export_name": "Mesh",
                "copy_and_apply": True,
                "apply_bakes_to_original": False,
                "hide_source_objects": True,
                "hide_cage_object": True,
                "preserve_materials": False,
                "everything_16bit": False,
                "export_file_format": "PNG",
                "apply_col_man_to_col": True,
                "export_cycles_col_space": True,
                "rundenoise": False,
                "apply_mods_on_mesh_export": True,
                "objects_list_index": 0,
                "bgbake": "fg",
                "memLimit": "4096",
                "batch_name": "",
                "first_texture_show": True,
                "bgbake_name": "",
                "apply_transformation": True,
                "create_glTF_node": False,
                "glTF_selection": "Ambient Occlusion",
                "export_path": "",
                "move_new_uvs_to_top": False,
                "selected_bump": False,
                "cyclesbake_cs": "Non-Color",
                "export_mesh_preset_name": "None",
                "cyclesbake_copy_and_apply_mat_format": "emission",
                "clear_image": True,
                "cage_smooth_hard": "smooth",
                "boosted_sample_count": 128,
                "no_force_32bit_normals": False,
                "keep_internal_after_export": True,
                "ao_sample_count": 32,
                "isolate_objects": False,
                "uv_advanced_packing_show": False,
                "uvp_shape_method": "CONCAVE",
                "uvp_scale": True,
                "uvp_rotate": True,
                "uvp_rotation_method": "ANY",
                "uvp_margin_method": "ADD",
                "uvp_lock_pinned": False,
                "uvp_lock_method": "LOCKED",
                "uvp_merge_overlapping": True,
                "uvp_pack_to": "ACTIVE_UDIM",
                "showtips": True,
                "presets_show": True,
                "bake_objects_show": True,
                "pbr_settings_show": True,
                "aov_settings_show": False,
                "cyclesbake_settings_show": False,
                "specials_show": False,
                "textures_show": True,
                "export_show": True,
                "admin_settings_show": False,
                "uv_show": True,
                "other_show": False,
                "channelpacking_show": True,
                "bg_status_show": False,
                "bake_sequence": False,
                "bake_sequence_start_frame": 1,
                "bake_sequence_end_frame": 250,
                "findreplace_find": "",
                "findreplace_replace": "",
                "findreplace_type": "object",
                "do_aa": False,
                "aa_threshold": 0.1,
                "aa_contrast_limit": 0.5,
                "aa_corner_radius": 2,
                "cycles.bake_type": "COMBINED",
                "render.bake.use_pass_direct": True,
                "render.bake.use_pass_indirect": True,
                "render.bake.use_pass_diffuse": True,
                "render.bake.use_pass_glossy": True,
                "render.bake.use_pass_transmission": True,
                "render.bake.use_pass_emit": True,
                "render.bake.view_from": "ABOVE_SURFACE",
                "cycles.samples": 128,
                "render.bake.normal_space": "TANGENT",
                "render.bake.normal_r": "POS_X",
                "render.bake.normal_g": "POS_Y",
                "render.bake.normal_b": "POS_Z",
                "render.bake.use_pass_color": True,
                "render.bake.margin": 16,
                "render.bake.margin_type": "EXTEND",
                "render.image_settings.exr_codec": "ZIP",
                "cycles.use_denoising": False,
                "cycles.denoiser": "OPENIMAGEDENOISE",
                "cycles.denoising_input_passes": "RGB_ALBEDO_NORMAL",
                "cycles.denoising_prefilter": "ACCURATE",
                "objects_list": [],
                "pbr_target_obj": None,
                "cycles_target_obj": None,
                "cage_object": None,
            }

        # Define presets
        presets = {}

        # HD2 Basic+ - Color, Normal, Metallic, Roughness, AO with PBR channel pack
        preset = get_base_preset()
        preset["selected_col"] = True
        preset["selected_metal"] = True
        preset["selected_rough"] = True
        preset["selected_normal"] = True
        preset["selected_ao"] = True
        preset["channel_packed_images"] = {
            "PBR": {"R": "Metalness", "G": "Roughness", "B": "Ambient Occlusion", "A": "white",
                    "file_format": "PNG", "exr_codec": "ZIP", "png_compression": 15}
        }
        presets["HD2 Basic+"] = preset

        # HD2 Basic - Color, Normal, Metallic, Roughness, AO with PBR channel pack
        preset = get_base_preset()
        preset["selected_col"] = True
        preset["selected_metal"] = True
        preset["selected_rough"] = True
        preset["selected_normal"] = True
        preset["selected_ao"] = True
        preset["channel_packed_images"] = {
            "PBR": {"R": "Metalness", "G": "Roughness", "B": "Ambient Occlusion", "A": "white",
                    "file_format": "PNG", "exr_codec": "ZIP", "png_compression": 15}
        }
        presets["HD2 Basic"] = preset

        # HD2 Emissive - Color, Normal, Metallic, Roughness, AO, Emission
        preset = get_base_preset()
        preset["selected_col"] = True
        preset["selected_metal"] = True
        preset["selected_rough"] = True
        preset["selected_normal"] = True
        preset["selected_ao"] = True
        preset["selected_emission"] = True
        preset["channel_packed_images"] = {
            "PBR": {"R": "Metalness", "G": "Roughness", "B": "Ambient Occlusion", "A": "none",
                    "file_format": "PNG", "exr_codec": "ZIP", "png_compression": 15}
        }
        presets["HD2 Emissive"] = preset

        # HD2 Translucent - Color, Normal, Roughness, Transmission
        preset = get_base_preset()
        preset["selected_col"] = True
        preset["selected_rough"] = True
        preset["selected_normal"] = True
        preset["selected_trans"] = True
        preset["channel_packed_images"] = {}
        presets["HD2 Translucent"] = preset

        # HD2 Advanced - Full PBR
        preset = get_base_preset()
        preset["selected_col"] = True
        preset["selected_metal"] = True
        preset["selected_rough"] = True
        preset["selected_normal"] = True
        preset["selected_ao"] = True
        preset["selected_emission"] = True
        preset["selected_specular"] = True
        preset["selected_clearcoat"] = True
        preset["selected_clearcoat_rough"] = True
        preset["selected_alpha"] = True
        preset["channel_packed_images"] = {
            "PBR": {"R": "Metalness", "G": "Roughness", "B": "Ambient Occlusion", "A": "none",
                    "file_format": "PNG", "exr_codec": "ZIP", "png_compression": 15},
            "Clearcoat": {"R": "Clearcoat", "G": "Clearcoat Roughness", "B": "none", "A": "none",
                          "file_format": "PNG", "exr_codec": "ZIP", "png_compression": 15}
        }
        presets["HD2 Advanced"] = preset

        # Save presets to SimpleBake local presets
        presets_created = 0
        for name, preset_data in presets.items():
            try:
                key = f"SB_local_preset_{name}"
                # Only create if not already exists (don't overwrite user changes)
                if key not in sbp.keys():
                    sbp[key] = json.dumps(preset_data)
                    presets_created += 1
            except Exception as e:
                PrettyPrint(f"Failed to create SimpleBake preset '{name}': {e}", 'WARNING')

        # Refresh the local presets list
        if presets_created > 0:
            try:
                bpy.ops.simplebake.local_preset_refresh()
            except:
                pass
            PrettyPrint(f"Created {presets_created} SimpleBake local presets for HD2 materials")

    def _add_objects_to_simplebake_list(self, context, objects):
        """Add objects to SimpleBake's bake objects list.

        Args:
            context: Blender context
            objects: List of Blender objects to add to the bake list
        """
        try:
            sbp = getattr(context.scene, 'SimpleBake_Props', None)
            if sbp is None:
                return
        except:
            return

        # First, clean up stale entries (objects that no longer exist in scene)
        scene_object_names = {obj.name for obj in context.scene.objects}
        indices_to_remove = []
        for i, item in enumerate(sbp.objects_list):
            if item.name not in scene_object_names or item.obj_point is None:
                indices_to_remove.append(i)

        # Remove in reverse order to preserve indices
        removed_count = 0
        for i in reversed(indices_to_remove):
            sbp.objects_list.remove(i)
            removed_count += 1

        if removed_count > 0:
            PrettyPrint(f"Cleaned up {removed_count} stale objects from SimpleBake bake list")

        # Get mesh objects only
        mesh_objects = [obj for obj in objects if obj and obj.type == 'MESH']
        if not mesh_objects:
            return

        # Add new objects (avoid duplicates)
        added_count = 0
        for obj in mesh_objects:
            existing_names = [item.name for item in sbp.objects_list]
            if obj.name not in existing_names:
                item = sbp.objects_list.add()
                item.name = obj.name
                item.obj_point = obj
                added_count += 1

        PrettyPrint(f"Added {added_count} objects to SimpleBake bake list (total: {len(sbp.objects_list)})")


# Texture packing configurations for each material type
# Maps material template -> list of (texture_slot_name, channels_config)
# channels_config is a dict mapping RGBA channel -> (bake_output, source_channel or None for grayscale)
BAKE_TEXTURE_CONFIG = {
    "basic+": [
        # Slot 0: PBR texture - Metallic(R), Roughness(G), White(B), 1.0(A)
        # Basic+ uses fully white B channel (not AO) for best results
        ("PBR", {
            'R': ("Bake_Metallic", None),
            'G': ("Bake_Roughness", None),
            'B': ("constant", 1.0),  # Basic+ requires white, not AO
            'A': ("constant", 1.0),
        }, "BC7_UNORM"),
        # Slot 1: Base Color
        ("Base Color", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("constant", 1.0),
        }, "BC7_UNORM_SRGB"),
        # Slot 2: Normal
        ("Normal", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("constant", 1.0),  # Normal maps typically have B=1 for up direction
            'A': ("constant", 1.0),
        }, "BC7_UNORM"),
    ],
    "basic": [
        ("PBR", {
            'R': ("Bake_Metallic", None),
            'G': ("Bake_Roughness", None),
            'B': ("Bake_Ambient Occlusion", None),
            'A': ("constant", 1.0),
        }, "BC7_UNORM"),
        ("Base Color", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("constant", 1.0),
        }, "BC7_UNORM_SRGB"),
        ("Normal", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("constant", 1.0),
            'A': ("constant", 1.0),
        }, "BC7_UNORM"),
    ],
    "emissive": [
        # Slot 0: Normal/AO/Roughness - NormalR(R), NormalG(G), AO(B), Roughness(A)
        ("Normal/AO/Roughness", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("Bake_Ambient Occlusion", None),
            'A': ("Bake_Roughness", None),
        }, "BC7_UNORM"),
        # Slot 1: Emission (use color as emission for now)
        ("Emission", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("constant", 1.0),
        }, "BC7_UNORM_SRGB"),
        # Slot 2: Base Color/Metallic
        ("Base Color/Metallic", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("Bake_Metallic", None),
        }, "BC7_UNORM_SRGB"),
    ],
    "alphaclip": [
        ("Normal/AO/Roughness", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("Bake_Ambient Occlusion", None),
            'A': ("Bake_Roughness", None),
        }, "BC7_UNORM"),
        ("Alpha Mask", {
            'R': ("Bake_Alpha", None),
            'G': ("Bake_Alpha", None),
            'B': ("Bake_Alpha", None),
            'A': ("Bake_Alpha", None),
        }, "BC4_UNORM"),
        ("Base Color/Metallic", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("Bake_Metallic", None),
        }, "BC7_UNORM_SRGB"),
    ],
    "alphaclip+": [
        ("Normal/AO/Roughness", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("Bake_Ambient Occlusion", None),
            'A': ("Bake_Roughness", None),
        }, "BC7_UNORM"),
        ("Emission", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("constant", 1.0),
        }, "BC7_UNORM_SRGB"),
        ("Base Color/Metallic", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("Bake_Metallic", None),
        }, "BC7_UNORM_SRGB"),
        ("Alpha Mask", {
            'R': ("Bake_Alpha", None),
            'G': ("Bake_Alpha", None),
            'B': ("Bake_Alpha", None),
            'A': ("Bake_Alpha", None),
        }, "BC4_UNORM"),
    ],
    "advanced": [
        # Advanced has a complex 11-slot layout, we'll fill the key ones
        # Slot 0-1: empty
        # Slot 2: Normal/AO/Roughness
        ("", None, None),  # Slot 0 - empty
        ("", None, None),  # Slot 1 - empty
        ("Normal/AO/Roughness", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("Bake_Ambient Occlusion", None),
            'A': ("Bake_Roughness", None),
        }, "BC7_UNORM"),
        # Slot 3: Metallic
        ("Metallic", {
            'R': ("Bake_Metallic", None),
            'G': ("Bake_Metallic", None),
            'B': ("Bake_Metallic", None),
            'A': ("constant", 1.0),
        }, "BC4_UNORM"),
        ("", None, None),  # Slot 4 - empty
        # Slot 5: Color/Emission Mask
        ("Color/Emission Mask", {
            'R': ("Bake_Color", 'R'),
            'G': ("Bake_Color", 'G'),
            'B': ("Bake_Color", 'B'),
            'A': ("constant", 1.0),  # Emission mask - 1.0 = full emission
        }, "BC7_UNORM_SRGB"),
        ("", None, None),  # Slot 6 - empty
        ("", None, None),  # Slot 7 - empty
        ("", None, None),  # Slot 8 - empty
        ("", None, None),  # Slot 9 - empty
        ("", None, None),  # Slot 10 - empty
    ],
    "translucent": [
        ("Normal", {
            'R': ("Bake_Normal", 'R'),
            'G': ("Bake_Normal", 'G'),
            'B': ("constant", 1.0),
            'A': ("constant", 1.0),
        }, "BC7_UNORM"),
    ],
}


class SaveMeshWithBakedTexturesOperator(Operator):
    """Bake HD2 shader textures and save mesh with a simplified material template"""
    bl_label = "Bake & Save"
    bl_idname = "helldiver2.save_mesh_baked_textures"
    bl_description = "Bake textures from HD2 Shader and save with selected material type"
    bl_options = {'REGISTER', 'UNDO'}

    # Material type selection
    material_type: EnumProperty(
        name="Material Type",
        description="Target material type for baked textures",
        items=[
            ("basic+", "Basic+", "Basic material with color, normal, and PBR. Renders in UI."),
            ("basic", "Basic", "Basic material with color, normal, and PBR."),
            ("emissive", "Emissive", "Material with color, normal, and emission map."),
            ("alphaclip", "Alpha Clip", "Material with alpha mask support. Does not render in UI."),
            ("alphaclip+", "Alpha Clip+", "Alpha mask with emission support."),
            ("advanced", "Advanced", "Complex material with color, normal, emission and PBR. Renders in UI."),
            ("translucent", "Translucent", "Translucent material with normal map only."),
        ],
        default="basic+"
    )

    bake_resolution: EnumProperty(
        name="Resolution",
        description="Resolution for baked textures",
        items=[
            ("256", "256x256", "Low resolution"),
            ("512", "512x512", "Medium resolution"),
            ("1024", "1024x1024", "High resolution (recommended)"),
            ("2048", "2048x2048", "Very high resolution"),
            ("4096", "4096x4096", "Ultra resolution"),
        ],
        default="1024"
    )

    bake_samples: IntProperty(
        name="Samples",
        description="Number of samples for baking (higher = better quality but slower)",
        default=16,
        min=1,
        max=256
    )

    object_id: StringProperty(options={"HIDDEN"})

    # Internal state for two-stage process
    _stage: str = "settings"  # "settings" -> "confirm"
    _processed_objects: list = []  # List of (obj, original_materials, material_id, object_id)

    def invoke(self, context, event):
        self._stage = "settings"
        self._processed_objects = []
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        if self._stage == "settings":
            layout.prop(self, "material_type")
            layout.prop(self, "bake_resolution")
            layout.prop(self, "bake_samples")

            # Show texture slots that will be created
            layout.separator()
            layout.label(text="Textures to be created:")
            if self.material_type in BAKE_TEXTURE_CONFIG:
                for slot_name, channels, fmt in BAKE_TEXTURE_CONFIG[self.material_type]:
                    if slot_name and channels:
                        layout.label(text=f"  • {slot_name}", icon='TEXTURE')

        elif self._stage == "confirm":
            layout.label(text="Preview the baked materials on your objects.", icon='QUESTION')
            layout.label(text="Does everything look correct?")
            layout.separator()
            layout.label(text="Click OK to save the mesh with baked textures.")
            layout.label(text="Click Cancel (or press Escape) to revert.")

    def execute(self, context):
        if self._stage == "settings":
            # Stage 1: Do the baking and swap materials for preview
            return self._execute_bake(context)
        elif self._stage == "confirm":
            # Stage 2: User confirmed, save the mesh
            return self._execute_save(context)
        return {'CANCELLED'}

    def cancel(self, context):
        # User cancelled during confirmation - revert materials
        if self._stage == "confirm":
            self._revert_materials()
            self.report({'INFO'}, "Bake cancelled - materials reverted")

    def _execute_bake(self, context):
        """Stage 1: Bake textures and swap materials for preview"""
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        # Get selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Filter to objects with HD2 Shader materials
        valid_objects = []
        for obj in selected_objects:
            if self._has_hd2_shader(obj):
                valid_objects.append(obj)
            else:
                PrettyPrint(f"Skipping {obj.name}: no HD2 Shader found", 'WARNING')

        if not valid_objects:
            self.report({'ERROR'}, "No selected objects have HD2 Shader materials. Import with 'With Shader' first.")
            return {'CANCELLED'}

        # Process each object - bake and swap materials for preview
        self._processed_objects = []
        for obj in valid_objects:
            try:
                result = self._bake_and_preview(context, obj)
                if result:
                    self._processed_objects.append(result)
            except Exception as e:
                PrettyPrint(f"Failed to process {obj.name}: {str(e)}", 'ERROR')
                import traceback
                traceback.print_exc()

        if not self._processed_objects:
            self.report({'ERROR'}, "Failed to bake any meshes")
            return {'CANCELLED'}

        # Show confirmation dialog
        self._stage = "confirm"
        self.report({'INFO'}, f"Baked {len(self._processed_objects)} object(s). Check the preview and confirm.")
        return context.window_manager.invoke_props_dialog(self, width=350)

    def _execute_save(self, context):
        """Stage 2: User confirmed - save meshes with baked materials"""
        success_count = 0
        for obj, original_materials, material_id, object_id in self._processed_objects:
            try:
                if obj.name not in bpy.data.objects:
                    PrettyPrint(f"Object no longer exists, skipping", 'WARNING')
                    continue

                # Save the mesh with the new material
                self._save_mesh_with_material(context, obj, object_id, material_id)
                success_count += 1
                PrettyPrint(f"Saved {obj.name} with baked material")
            except Exception as e:
                PrettyPrint(f"Failed to save {obj.name}: {str(e)}", 'ERROR')
                import traceback
                traceback.print_exc()

        self._processed_objects = []

        if success_count > 0:
            self.report({'INFO'}, f"Successfully saved {success_count} mesh(es) with baked textures")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to save any meshes")
            return {'CANCELLED'}

    def _revert_materials(self):
        """Revert all objects to their original materials"""
        for obj, original_materials, material_id, object_id in self._processed_objects:
            try:
                if obj.name not in bpy.data.objects:
                    continue
                # Restore original materials
                obj.data.materials.clear()
                for mat in original_materials:
                    obj.data.materials.append(mat)
                PrettyPrint(f"Reverted materials on {obj.name}")
            except Exception as e:
                PrettyPrint(f"Failed to revert {obj.name}: {str(e)}", 'WARNING')
        self._processed_objects = []

    def _has_hd2_shader(self, obj):
        """Check if object has a material with HD2 Shader node group"""
        return has_hd2_shader(obj)

    def _find_hd2_shader_node(self, material):
        """Find the HD2 Shader node group in a material"""
        return find_hd2_shader_node(material)

    def _bake_and_preview(self, context, obj):
        """Bake textures, create material, and swap for preview. Returns (obj, original_mats, material_id, object_id)"""
        PrettyPrint(f"Processing object: {obj.name}")

        # Get object ID
        try:
            object_id = obj["Z_ObjectID"]
        except KeyError:
            raise Exception(f"Object {obj.name} has no Z_ObjectID property")

        # Get the first material with HD2 Shader
        hd2_mat = None
        hd2_shader_node = None
        for mat in obj.data.materials:
            shader_node = self._find_hd2_shader_node(mat)
            if shader_node:
                hd2_mat = mat
                hd2_shader_node = shader_node
                break

        if not hd2_shader_node:
            raise Exception(f"No HD2 Shader found in {obj.name}")

        # Store original materials for potential revert
        original_materials = list(obj.data.materials)

        # Select only this object for baking
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Step 1: Bake all required textures from HD2 Shader
        PrettyPrint("Step 1: Baking textures from HD2 Shader...")
        baked_images = self._bake_textures(context, obj, hd2_mat, hd2_shader_node)

        # Step 2: Pack channels according to material type config
        PrettyPrint("Step 2: Packing texture channels...")
        packed_textures = self._pack_textures(context, baked_images, obj.name)

        # Clean up baked images (no longer needed after packing)
        for img in baked_images.values():
            if img:
                bpy.data.images.remove(img)

        # Step 3: Create modded material with baked textures
        PrettyPrint("Step 3: Creating material with baked textures...")
        material_id = self._create_material_with_baked_textures(context, packed_textures)

        # Step 4: Create a preview Blender material and assign it to the object
        PrettyPrint("Step 4: Swapping to preview material...")
        self._swap_to_preview_material(context, obj, material_id)

        PrettyPrint(f"Baked and ready for preview: {obj.name}")
        return (obj, original_materials, material_id, object_id)

    def _bake_textures(self, context, obj, material, shader_node):
        """Bake all required outputs from the HD2 Shader using HD2Baker.

        Uses the HD2Baker class which provides cleaner node management and
        proper cleanup based on Principled Baker techniques.
        """
        resolution = int(self.bake_resolution)

        # Create baker instance
        baker = HD2Baker(context)
        baker.resolution = resolution
        baker.samples = self.bake_samples
        baker.use_gpu = True

        # Bake all outputs
        PrettyPrint(f"Baking textures using HD2Baker (resolution: {resolution}, samples: {self.bake_samples})...")
        results = baker.bake_object(obj)

        # Convert keys to match BAKE_TEXTURE_CONFIG format (e.g., "Color" -> "Bake_Color")
        baked_images = {}
        for key, image in results.items():
            bake_key = f"Bake_{key}"
            baked_images[bake_key] = image
            PrettyPrint(f"Baked {bake_key}")

        return baked_images

    def _pack_textures(self, context, baked_images, obj_name):
        """Pack baked textures into channel configurations for target material type"""
        config = BAKE_TEXTURE_CONFIG.get(self.material_type, [])
        packed_textures = []
        resolution = int(self.bake_resolution)

        for slot_name, channels, dds_format in config:
            if not slot_name or not channels:
                packed_textures.append(None)
                continue

            # Create new image for packed result
            packed_img = bpy.data.images.new(f"packed_{slot_name}_{obj_name}", resolution, resolution, alpha=True)

            # Get pixel data from source images
            pixels = [0.0] * (resolution * resolution * 4)

            for channel_idx, channel_name in enumerate(['R', 'G', 'B', 'A']):
                source_info = channels.get(channel_name)
                if not source_info:
                    continue

                source_output, source_channel = source_info

                if source_output == "constant":
                    # Fill with constant value
                    value = source_channel
                    for i in range(resolution * resolution):
                        pixels[i * 4 + channel_idx] = value
                elif source_output in baked_images:
                    source_img = baked_images[source_output]
                    source_pixels = list(source_img.pixels)

                    if source_channel is None:
                        # Use as grayscale (R channel)
                        for i in range(resolution * resolution):
                            pixels[i * 4 + channel_idx] = source_pixels[i * 4]  # R channel
                    else:
                        # Use specific channel
                        src_channel_idx = {'R': 0, 'G': 1, 'B': 2, 'A': 3}[source_channel]
                        for i in range(resolution * resolution):
                            pixels[i * 4 + channel_idx] = source_pixels[i * 4 + src_channel_idx]
                else:
                    # Source not available, use default
                    default_val = 0.5 if channel_name in ['R', 'G', 'B'] else 1.0
                    for i in range(resolution * resolution):
                        pixels[i * 4 + channel_idx] = default_val

            packed_img.pixels = pixels
            packed_textures.append((packed_img, slot_name, dds_format))

        return packed_textures

    def _create_material_with_baked_textures(self, context, packed_textures):
        """Create modded material with baked textures.

        This converts baked textures to DDS, creates a material from template,
        then directly overwrites the texture entries with our baked DDS files
        (similar to using 'Import DDS Texture' from the UI).
        """
        template = self.material_type
        tempdir = get_temp_folder()

        # Step 1: Convert all packed textures to DDS files first
        dds_paths = []
        for i, item in enumerate(packed_textures):
            if item is None:
                dds_paths.append(None)
                continue

            packed_img, slot_name, dds_format = item

            PrettyPrint(f"Converting baked texture {i}: {slot_name} to DDS...")

            # Save packed image as TGA
            tga_path = os.path.join(tempdir, f"bake_{slot_name.replace('/', '_')}.tga")
            packed_img.file_format = 'TARGA_RAW'
            packed_img.filepath_raw = tga_path
            packed_img.save()

            # Convert to DDS
            dds_path = os.path.join(tempdir, f"bake_{slot_name.replace('/', '_')}.dds")
            subprocess.run([
                Global_texconvpath, "-y", "-o", tempdir,
                "-ft", "dds", "-dx10", "-f", dds_format,
                "-sepalpha", "-alpha", tga_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            if not os.path.exists(dds_path):
                PrettyPrint(f"DDS conversion failed for {slot_name}", 'ERROR')
                dds_paths.append(None)
            else:
                dds_paths.append(dds_path)
                PrettyPrint(f"Created DDS: {dds_path}")

            # Clean up blender image
            bpy.data.images.remove(packed_img)

        # Step 2: Create modded material from template (this also saves it with template textures)
        CreateModdedMaterial(template)

        # Find the newly created material entry
        material_entries = []
        for entry in Global_TocManager.ActivePatch.TocDict.get(MaterialID, {}).values():
            if entry.IsCreated and entry.MaterialTemplate == template:
                material_entries.append(entry)

        if not material_entries:
            raise Exception("Failed to create material entry")

        mat_entry = material_entries[-1]
        PrettyPrint(f"Created material entry {mat_entry.FileID}")

        # Step 3: Load the material to get texture IDs
        if not mat_entry.IsLoaded:
            mat_entry.Load()
        mat = mat_entry.LoadedData

        # Step 4: Create texture entries by copying template textures and replacing with our DDS data
        # (this mirrors how "Import DDS" works - load existing texture, replace data, save)
        PrettyPrint("Creating texture entries from baked DDS files...")
        new_tex_ids = []
        for i, dds_path in enumerate(dds_paths):
            if dds_path is None:
                new_tex_ids.append(mat.TexIDs[i] if i < len(mat.TexIDs) else 0)
                continue

            if i >= len(mat.TexIDs):
                PrettyPrint(f"Skipping texture {i}: no template texture ID", 'WARNING')
                continue

            # Get the template texture ID and load it
            template_tex_id = mat.TexIDs[i]
            PrettyPrint(f"Loading template texture {template_tex_id} for slot {i}")

            # Load the template texture entry
            Global_TocManager.Load(int(template_tex_id), TexID, False, True)
            template_entry = Global_TocManager.GetEntry(int(template_tex_id), TexID, True)

            if template_entry is None:
                PrettyPrint(f"Could not find template texture {template_tex_id}, skipping", 'ERROR')
                new_tex_ids.append(template_tex_id)
                continue

            # Load the template texture data
            template_entry.Load()
            StingrayTex = template_entry.LoadedData

            # Replace with our baked DDS data (just like Import DDS does)
            PrettyPrint(f"Replacing texture data with {dds_path}")
            with open(dds_path, 'rb') as f:
                StingrayTex.FromDDS(f.read())

            # Serialize to binary
            Toc = MemoryStream(IOMode="write")
            Gpu = MemoryStream(IOMode="write")
            Stream = MemoryStream(IOMode="write")
            StingrayTex.Serialize(Toc, Gpu, Stream)

            # Generate a new ID for this texture
            tex_id = RandomHash16()
            PrettyPrint(f"Creating texture {i} with new ID {tex_id}")

            # Create new texture entry with the data
            tex_entry = TocEntry()
            tex_entry.FileID = tex_id
            tex_entry.TypeID = TexID
            tex_entry.IsCreated = True
            tex_entry.SetData(Toc.Data, Gpu.Data, Stream.Data, False)

            # Add to patch
            Global_TocManager.AddNewEntryToPatch(tex_entry)
            new_tex_ids.append(tex_id)
            PrettyPrint(f"Added texture entry {tex_id} to patch")

        # Step 5: Update material's TexIDs to point to our new textures
        PrettyPrint(f"Updating material TexIDs from {mat.TexIDs} to {new_tex_ids}")
        for i, tex_id in enumerate(new_tex_ids):
            if i < len(mat.TexIDs):
                mat.TexIDs[i] = tex_id

        # Step 6: Save the material with updated TexIDs
        PrettyPrint("Saving material with updated texture IDs...")
        f = MemoryStream(IOMode="write")
        mat.Serialize(f)
        mat_entry.SetData(f.Data, b"", b"", False)

        PrettyPrint(f"Created material {mat_entry.FileID} with template {template} and baked textures")
        return mat_entry.FileID

    def _swap_to_preview_material(self, context, obj, material_id):
        """Swap the object's Blender materials to a preview material for user confirmation.

        Creates a simple PBR material in Blender using the baked textures so the user
        can see approximately what the result will look like before saving.
        NOTE: Material name MUST be just the numeric ID for GetMeshData to work.
        """
        # Material name must be just the numeric ID for GetMeshData to parse it
        mat_name = str(material_id)

        # Always create a fresh preview material (remove old one if exists)
        if mat_name in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[mat_name])

        # Create a new preview material
        preview_mat = bpy.data.materials.new(name=mat_name)
        preview_mat.use_nodes = True
        nodes = preview_mat.node_tree.nodes
        links = preview_mat.node_tree.links

        # Clear default nodes
        nodes.clear()

        # Create Principled BSDF and output
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (300, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        # Try to load the baked texture images
        tempdir = get_temp_folder()
        config = BAKE_TEXTURE_CONFIG.get(self.material_type, [])

        for i, (slot_name, channels, dds_format) in enumerate(config):
            if not slot_name or not channels:
                continue

            # Look for the TGA version of the texture (we save as TGA)
            tga_path = os.path.join(tempdir, f"bake_{slot_name.replace('/', '_')}.tga")
            PrettyPrint(f"Looking for preview texture: {tga_path}")

            if os.path.exists(tga_path):
                img = bpy.data.images.load(tga_path)
                tex_node = nodes.new('ShaderNodeTexImage')
                tex_node.image = img
                tex_node.location = (-400, 200 - i * 300)

                # Set correct colorspace based on texture type
                # PBR and Normal contain linear data, Base Color is sRGB
                if "Color" in slot_name or "Base" in slot_name:
                    img.colorspace_settings.name = 'sRGB'
                else:
                    img.colorspace_settings.name = 'Non-Color'

                # Connect based on slot type
                if "Color" in slot_name or "Base" in slot_name:
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                elif "Normal" in slot_name:
                    normal_map = nodes.new('ShaderNodeNormalMap')
                    normal_map.location = (-150, 200 - i * 300)
                    links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                    links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
                elif "PBR" in slot_name:
                    # PBR is packed: R=Metallic, G=Roughness, B=AO
                    sep = nodes.new('ShaderNodeSeparateColor')
                    sep.location = (-150, 200 - i * 300)
                    links.new(tex_node.outputs['Color'], sep.inputs['Color'])
                    links.new(sep.outputs['Red'], bsdf.inputs['Metallic'])
                    links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
            else:
                PrettyPrint(f"Preview texture not found: {tga_path}", 'WARNING')

        PrettyPrint(f"Created preview material: {mat_name}")

        # Assign preview material to all slots on the object
        if obj.data.materials:
            for i in range(len(obj.data.materials)):
                obj.data.materials[i] = preview_mat
        else:
            obj.data.materials.append(preview_mat)

        PrettyPrint(f"Assigned preview material to {obj.name}")

    def _save_mesh_with_material(self, context, obj, object_id, material_id):
        """Save the mesh with the specified material ID."""
        # Select only this object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Get settings
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()

        # Get the entry and load it
        Entry = Global_TocManager.GetEntryByLoadArchive(int(object_id), UnitID)
        if Entry is None:
            raise Exception(f"Could not find entry for {object_id}")

        Entry.Load(True, False, True)

        # Add entry to patch
        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(object_id))

        # Get mesh data from Blender objects
        MeshData = GetObjectsMeshData(Global_TocManager, Global_BoneNames)

        # Get the mesh data for this object
        ID = str(object_id)
        if ID not in MeshData:
            raise Exception(f"No mesh data found for ID {ID}")

        meshes = MeshData[ID]

        # Replace mesh data in entry
        for mesh_index, mesh in meshes.items():
            try:
                Entry.LoadedData.RawMeshes[mesh_index] = mesh
            except IndexError:
                raise Exception(f"MeshInfoIndex {mesh_index} exceeds mesh count")

        # Set all MaterialIDs to our baked material
        if hasattr(Entry.LoadedData, 'MaterialIDs'):
            for i in range(len(Entry.LoadedData.MaterialIDs)):
                Entry.LoadedData.MaterialIDs[i] = material_id
            PrettyPrint(f"Set all MaterialIDs to {material_id}")

        # Save the entry
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)
        if not wasSaved:
            raise Exception(f"Failed to save mesh {object_id}")


class SaveStingrayUnitOperator(Operator):
    bl_label  = "Save Unit"
    bl_idname = "helldiver2.archive_unit_save"
    bl_description = "Saves Unit"
    bl_options = {'REGISTER', 'UNDO'} 

    object_id: StringProperty()
    def execute(self, context):
        mode = context.mode
        if mode != 'OBJECT':
            self.report({'ERROR'}, f"You are Not in OBJECT Mode. Current Mode: {mode}")
            return {'CANCELLED'}
        if UnitNotValidToSave(self):
            return {'CANCELLED'}
        object = None
        object = bpy.context.active_object
        if object == None:
            self.report({"ERROR"}, "No Object selected. Please select the object to be saved.")
            return {'CANCELLED'}
        try:
            ID = object["Z_ObjectID"]
        except:
            self.report({'ERROR'}, f"{object.name} has no HD2 custom properties")
            return{'CANCELLED'}
        SwapID = ""
        try:
            SwapID = object["Z_SwapID"]
            if SwapID != "" and not SwapID.isnumeric():
                self.report({"ERROR"}, f"Object: {object.name} has an incorrect Swap ID. Assure that the ID is a proper integer entry ID.")
                return {'CANCELLED'}
        except:
            self.report({'INFO'}, f"{object.name} has no HD2 Swap ID. Skipping Swap.")
        global Global_BoneNames
        Entry = Global_TocManager.GetEntryByLoadArchive(int(ID), UnitID)
        if Entry is None:
            self.report({'ERROR'},
                f"Archive for entry being saved is not loaded. Could not find custom property object at ID: {ID}")
            return{'CANCELLED'}
        Entry.Load(True, False, True)
        dest_id = int(ID)
        existing_entry = None
        if SwapID and SwapID.isnumeric() and SwapID != ID:
            dest_id = int(SwapID)
        Entry = Global_TocManager.AddEntryToPatchID(Entry, dest_id)
        model = GetObjectsMeshData(Global_TocManager, Global_BoneNames)
        BlenderOpts = bpy.context.scene.Hd2ToolPanelSettings.get_settings_dict()
        if Entry is None:
            self.report({'ERROR'},
                f"Archive for entry being saved is not loaded. Could not find custom property object at ID: {ID}")
            return{'CANCELLED'}
        if SwapID and SwapID.isnumeric():
            ID = SwapID
        m = model[ID]
        meshes = model[ID]
        for mesh_index, mesh in meshes.items():
            try:
                Entry.LoadedData.RawMeshes[mesh_index] = mesh
            except IndexError:
                excpectedLength = len(Entry.LoadedData.RawMeshes) - 1
                self.report({'ERROR'}, f"MeshInfoIndex of {mesh_index} for {object.name} exceeds the number of meshes. Expected maximum MeshInfoIndex is: {excpectedLength}. Please change the custom properties to match this value and resave the mesh.")
                return{'CANCELLED'}
        for mesh_index, mesh in meshes.items():
            try:
                if Entry.LoadedData.RawMeshes[mesh_index].DEV_BoneInfoIndex == -1 and object[
                    'BoneInfoIndex'] > -1:
                    self.report({'ERROR'},
                                f"Attempting to overwrite static mesh with {object[0].name}"
                                f", which has bones. Check your MeshInfoIndex is correct.")
                    return{'CANCELLED'}
                Entry.LoadedData.RawMeshes[mesh_index] = mesh
            except IndexError:
                self.report({'ERROR'},
                            f"MeshInfoIndex for {object[0].name} exceeds the number of meshes")
                return{'CANCELLED'}
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)
        if not wasSaved:
            self.report({"ERROR"}, f"Failed to save unit {bpy.context.selected_objects[0].name}.")
            return{'CANCELLED'}
        self.report({'INFO'}, f"Saved Unit Object ID: {self.object_id}")
        return{'FINISHED'}


def modify_lod_data_for_always_visible(lod_data: bytearray, mode: str = 'zero') -> bytearray:
    """
    Modify LOD screen percentage thresholds to make a unit always visible.

    Args:
        lod_data: The UnreversedLODGroupListData bytearray
        mode: 'zero' = set all thresholds to 0.0, 'tiny' = set to very small value

    Returns:
        Modified bytearray
    """
    import struct

    if not lod_data or len(lod_data) < 4:
        return lod_data

    # Parse as float32 values
    num_floats = len(lod_data) // 4
    floats = list(struct.unpack(f'<{num_floats}f', lod_data[:num_floats * 4]))

    # Find and modify LOD threshold values (typically small positive floats 0.0-1.0)
    modified = False
    for i, f in enumerate(floats):
        # LOD thresholds are typically between 0.0 and 1.0 (screen percentage)
        # Values like 0.01, 0.05, 0.1, 0.2 are common
        if 0.0 < f <= 1.0:
            if mode == 'zero':
                floats[i] = 0.0
            elif mode == 'tiny':
                floats[i] = 1e-9  # Extremely small but not zero
            modified = True
            PrettyPrint(f"  LOD threshold [{i}]: {f:.6f} -> {floats[i]:.6f}")

    if not modified:
        PrettyPrint("  No LOD thresholds found in expected range (0.0-1.0)")

    # Pack back to bytes
    new_data = bytearray(struct.pack(f'<{num_floats}f', *floats))
    # Preserve any remaining bytes after the float data
    if len(lod_data) > num_floats * 4:
        new_data.extend(lod_data[num_floats * 4:])

    return new_data


def expand_bounding_box(unk2_data: bytearray, scale: float = 100.0) -> bytearray:
    """
    Expand the bounding box in MeshInfo.unk2 to reduce frustum culling.

    Args:
        unk2_data: The 32-byte unk2 field (likely AABB: MinXYZ + pad + MaxXYZ + pad)
        scale: How much to expand the bounding box

    Returns:
        Modified bytearray
    """
    import struct

    if not unk2_data or len(unk2_data) != 32:
        return unk2_data

    # Parse as 8 float32 values: [MinX, MinY, MinZ, ?, MaxX, MaxY, MaxZ, ?]
    floats = list(struct.unpack('<8f', unk2_data))

    # Expand min values (make more negative) and max values (make more positive)
    # Skip padding values (indices 3 and 7)
    for i in [0, 1, 2]:  # Min XYZ
        if floats[i] != 0.0:
            floats[i] = floats[i] - abs(floats[i]) * scale
        else:
            floats[i] = -scale

    for i in [4, 5, 6]:  # Max XYZ
        if floats[i] != 0.0:
            floats[i] = floats[i] + abs(floats[i]) * scale
        else:
            floats[i] = scale

    return bytearray(struct.pack('<8f', *floats))


class UnitLodValueOperator(Operator):
    """Edit a single LOD threshold value"""
    bl_label = "Edit LOD Value"
    bl_idname = "helldiver2.unit_lod_value"
    bl_description = "Edit this LOD threshold value"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    value_index: IntProperty()
    value: FloatProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value", text="LOD Threshold")
        layout.label(text="0.0 = always visible, 0.05 = 5% screen height", icon='INFO')

    def execute(self, context):
        import struct

        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}

        if not Entry.IsLoaded:
            Entry.Load(True, False, True)

        mesh_file = Entry.LoadedData
        lod_data = mesh_file.UnreversedLODGroupListData

        if not lod_data or len(lod_data) < 4:
            self.report({'ERROR'}, "No LOD data found")
            return {'CANCELLED'}

        # Parse, modify, repack
        num_floats = len(lod_data) // 4
        floats = list(struct.unpack(f'<{num_floats}f', lod_data[:num_floats * 4]))

        if self.value_index >= len(floats):
            self.report({'ERROR'}, f"Invalid value index: {self.value_index}")
            return {'CANCELLED'}

        floats[self.value_index] = self.value
        new_data = bytearray(struct.pack(f'<{num_floats}f', *floats))
        if len(lod_data) > num_floats * 4:
            new_data.extend(lod_data[num_floats * 4:])
        mesh_file.UnreversedLODGroupListData = new_data

        # Add to patch and save
        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save unit")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Set LOD[{self.value_index}] = {self.value}")
        return {'FINISHED'}


class UnitBboxValueOperator(Operator):
    """Edit bounding box values for a mesh"""
    bl_label = "Edit Bounding Box"
    bl_idname = "helldiver2.unit_bbox_value"
    bl_description = "Edit the bounding box for this mesh"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    mesh_index: IntProperty()

    min_x: FloatProperty(name="Min X")
    min_y: FloatProperty(name="Min Y")
    min_z: FloatProperty(name="Min Z")
    max_x: FloatProperty(name="Max X")
    max_y: FloatProperty(name="Max Y")
    max_z: FloatProperty(name="Max Z")

    def invoke(self, context, event):
        import struct

        # Load current values
        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry and Entry.IsLoaded:
            mesh_file = Entry.LoadedData
            if self.mesh_index < len(mesh_file.MeshInfoArray):
                mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
                if len(mesh_info.unk2) == 32:
                    floats = struct.unpack('<8f', mesh_info.unk2)
                    self.min_x, self.min_y, self.min_z = floats[0], floats[1], floats[2]
                    self.max_x, self.max_y, self.max_z = floats[4], floats[5], floats[6]

        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Bounding Box (AABB)", icon='MESH_CUBE')
        row = col.row()
        row.prop(self, "min_x")
        row.prop(self, "max_x")
        row = col.row()
        row.prop(self, "min_y")
        row.prop(self, "max_y")
        row = col.row()
        row.prop(self, "min_z")
        row.prop(self, "max_z")
        layout.label(text="Larger bbox = less frustum culling", icon='INFO')

    def execute(self, context):
        import struct

        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}

        if not Entry.IsLoaded:
            Entry.Load(True, False, True)

        mesh_file = Entry.LoadedData
        if self.mesh_index >= len(mesh_file.MeshInfoArray):
            self.report({'ERROR'}, f"Invalid mesh index: {self.mesh_index}")
            return {'CANCELLED'}

        mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
        if len(mesh_info.unk2) != 32:
            self.report({'ERROR'}, "Invalid bounding box data")
            return {'CANCELLED'}

        # Parse existing to preserve padding values
        floats = list(struct.unpack('<8f', mesh_info.unk2))
        floats[0], floats[1], floats[2] = self.min_x, self.min_y, self.min_z
        floats[4], floats[5], floats[6] = self.max_x, self.max_y, self.max_z
        mesh_info.unk2 = bytearray(struct.pack('<8f', *floats))

        # Add to patch and save
        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save unit")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Updated bounding box for mesh {self.mesh_index}")
        return {'FINISHED'}


class UnitHeaderValueOperator(Operator):
    """Edit a value in UnkHeaderData1"""
    bl_label = "Edit Header Value"
    bl_idname = "helldiver2.unit_header_value"
    bl_description = "Edit this header value"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    field_name: StringProperty()
    value_index: IntProperty()
    value: FloatProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value", text=f"{self.field_name}[{self.value_index}]")

    def execute(self, context):
        import struct

        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None or not Entry.IsLoaded:
            self.report({'ERROR'}, f"Could not find entry")
            return {'CANCELLED'}

        mesh_file = Entry.LoadedData
        data = getattr(mesh_file, self.field_name, None)
        if not data:
            self.report({'ERROR'}, f"Field {self.field_name} not found")
            return {'CANCELLED'}

        num_floats = len(data) // 4
        floats = list(struct.unpack(f'<{num_floats}f', data[:num_floats * 4]))
        if self.value_index >= len(floats):
            self.report({'ERROR'}, f"Invalid index")
            return {'CANCELLED'}

        floats[self.value_index] = self.value
        new_data = bytearray(struct.pack(f'<{num_floats}f', *floats))
        if len(data) > num_floats * 4:
            new_data.extend(data[num_floats * 4:])
        setattr(mesh_file, self.field_name, new_data)

        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Set {self.field_name}[{self.value_index}] = {self.value}")
        return {'FINISHED'}


class UnitMeshInfoUint32Operator(Operator):
    """Edit a uint32 field in MeshInfo"""
    bl_label = "Edit MeshInfo uint32"
    bl_idname = "helldiver2.unit_meshinfo_uint32"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    mesh_index: IntProperty()
    field_name: StringProperty()
    value: IntProperty(min=0, max=4294967295)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value", text=self.field_name)
        layout.label(text=f"Hex: 0x{self.value:08x}")

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None or not Entry.IsLoaded:
            self.report({'ERROR'}, f"Could not find entry")
            return {'CANCELLED'}

        mesh_file = Entry.LoadedData
        if self.mesh_index >= len(mesh_file.MeshInfoArray):
            self.report({'ERROR'}, f"Invalid mesh index")
            return {'CANCELLED'}

        mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
        setattr(mesh_info, self.field_name, self.value)

        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Set Mesh[{self.mesh_index}].{self.field_name} = {self.value}")
        return {'FINISHED'}


class UnitMeshInfoInt32Operator(Operator):
    """Edit an int32 field in MeshInfo"""
    bl_label = "Edit MeshInfo int32"
    bl_idname = "helldiver2.unit_meshinfo_int32"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    mesh_index: IntProperty()
    field_name: StringProperty()
    value: IntProperty(min=-2147483648, max=2147483647)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value", text=self.field_name)

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None or not Entry.IsLoaded:
            self.report({'ERROR'}, f"Could not find entry")
            return {'CANCELLED'}

        mesh_file = Entry.LoadedData
        if self.mesh_index >= len(mesh_file.MeshInfoArray):
            self.report({'ERROR'}, f"Invalid mesh index")
            return {'CANCELLED'}

        mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
        setattr(mesh_info, self.field_name, self.value)

        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Set Mesh[{self.mesh_index}].{self.field_name} = {self.value}")
        return {'FINISHED'}


class UnitMeshInfoUint64Operator(Operator):
    """Edit a uint64 field in MeshInfo"""
    bl_label = "Edit MeshInfo uint64"
    bl_idname = "helldiver2.unit_meshinfo_uint64"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    mesh_index: IntProperty()
    field_name: StringProperty()
    value: IntProperty()  # Note: Blender IntProperty is limited, we use string for display
    value_str: StringProperty()

    def invoke(self, context, event):
        self.value_str = str(self.value)
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "value_str", text=self.field_name)
        try:
            val = int(self.value_str)
            layout.label(text=f"Hex: 0x{val:016x}")
        except:
            layout.label(text="Invalid number", icon='ERROR')

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        try:
            new_value = int(self.value_str)
        except:
            self.report({'ERROR'}, "Invalid number")
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None or not Entry.IsLoaded:
            self.report({'ERROR'}, f"Could not find entry")
            return {'CANCELLED'}

        mesh_file = Entry.LoadedData
        if self.mesh_index >= len(mesh_file.MeshInfoArray):
            self.report({'ERROR'}, f"Invalid mesh index")
            return {'CANCELLED'}

        mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
        setattr(mesh_info, self.field_name, new_value)

        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Set Mesh[{self.mesh_index}].{self.field_name} = {new_value}")
        return {'FINISHED'}


class UnitMeshInfoUnk6Operator(Operator):
    """Edit unk6 (40 bytes) in MeshInfo"""
    bl_label = "Edit MeshInfo unk6"
    bl_idname = "helldiver2.unit_meshinfo_unk6"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()
    mesh_index: IntProperty()

    # 10 float values
    f0: FloatProperty(name="[0]")
    f1: FloatProperty(name="[1]")
    f2: FloatProperty(name="[2]")
    f3: FloatProperty(name="[3]")
    f4: FloatProperty(name="[4]")
    f5: FloatProperty(name="[5]")
    f6: FloatProperty(name="[6]")
    f7: FloatProperty(name="[7]")
    f8: FloatProperty(name="[8]")
    f9: FloatProperty(name="[9]")

    def invoke(self, context, event):
        import struct

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry and Entry.IsLoaded:
            mesh_file = Entry.LoadedData
            if self.mesh_index < len(mesh_file.MeshInfoArray):
                mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
                if len(mesh_info.unk6) == 40:
                    floats = struct.unpack('<10f', mesh_info.unk6)
                    self.f0, self.f1, self.f2, self.f3, self.f4 = floats[0], floats[1], floats[2], floats[3], floats[4]
                    self.f5, self.f6, self.f7, self.f8, self.f9 = floats[5], floats[6], floats[7], floats[8], floats[9]

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="unk6 (40 bytes = 10 floats)", icon='FILE_HIDDEN')
        row = layout.row()
        row.prop(self, "f0")
        row.prop(self, "f1")
        row = layout.row()
        row.prop(self, "f2")
        row.prop(self, "f3")
        row = layout.row()
        row.prop(self, "f4")
        row.prop(self, "f5")
        row = layout.row()
        row.prop(self, "f6")
        row.prop(self, "f7")
        row = layout.row()
        row.prop(self, "f8")
        row.prop(self, "f9")

    def execute(self, context):
        import struct

        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None or not Entry.IsLoaded:
            self.report({'ERROR'}, f"Could not find entry")
            return {'CANCELLED'}

        mesh_file = Entry.LoadedData
        if self.mesh_index >= len(mesh_file.MeshInfoArray):
            self.report({'ERROR'}, f"Invalid mesh index")
            return {'CANCELLED'}

        mesh_info = mesh_file.MeshInfoArray[self.mesh_index]
        floats = [self.f0, self.f1, self.f2, self.f3, self.f4, self.f5, self.f6, self.f7, self.f8, self.f9]
        mesh_info.unk6 = bytearray(struct.pack('<10f', *floats))

        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Updated Mesh[{self.mesh_index}].unk6")
        return {'FINISHED'}


class MakeUnitAlwaysVisibleOperator(Operator):
    """Make units always visible regardless of distance (supports multiple selection)"""
    bl_label = "Make Always Visible"
    bl_idname = "helldiver2.make_always_visible"
    bl_description = "Set all LOD thresholds to 0 to make units always visible at any distance"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()  # Comma-separated list of IDs

    expand_bbox: BoolProperty(
        name="Also Expand Bounding Boxes",
        description="Expand bounding boxes to reduce frustum culling (object stays visible when looking slightly away)",
        default=False
    )

    bbox_scale: FloatProperty(
        name="Bbox Scale",
        description="How much to expand the bounding box (higher = more visible when off-screen)",
        default=10.0,
        min=1.0,
        max=1000.0
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        # Count how many units will be modified
        ids = [id.strip() for id in self.object_id.split(',') if id.strip()]
        count = len(ids)

        if count > 1:
            layout.label(text=f"This will modify {count} units", icon='HIDE_OFF')
        else:
            layout.label(text="This will set all LOD thresholds to 0.0", icon='HIDE_OFF')

        layout.prop(self, "expand_bbox")
        if self.expand_bbox:
            layout.prop(self, "bbox_scale")
        layout.separator()
        layout.label(text="Changes will be saved to the patch.", icon='INFO')

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        if not self.object_id:
            self.report({'ERROR'}, "No object ID provided")
            return {'CANCELLED'}

        # Parse comma-separated IDs
        ids = [id.strip() for id in self.object_id.split(',') if id.strip()]

        if not ids:
            self.report({'ERROR'}, "No valid IDs provided")
            return {'CANCELLED'}

        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        success_count = 0
        error_count = 0

        for object_id in ids:
            try:
                Entry = Global_TocManager.GetEntryByLoadArchive(int(object_id), UnitID)
                if Entry is None:
                    PrettyPrint(f"Could not find entry for ID: {object_id}", "WARNING")
                    error_count += 1
                    continue

                if not Entry.IsLoaded:
                    Entry.Load(True, False, True)

                if not Entry.LoadedData:
                    error_count += 1
                    continue

                mesh_file = Entry.LoadedData

                # Modify LOD thresholds
                mesh_file.UnreversedLODGroupListData = modify_lod_data_for_always_visible(
                    mesh_file.UnreversedLODGroupListData, mode='zero'
                )

                # Expand bounding boxes if requested
                if self.expand_bbox:
                    for mesh_info in mesh_file.MeshInfoArray:
                        if len(mesh_info.unk2) == 32:
                            mesh_info.unk2 = expand_bounding_box(mesh_info.unk2, self.bbox_scale)

                # Add to patch and save
                Entry = Global_TocManager.AddEntryToPatchID(Entry, int(object_id))
                wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

                if wasSaved:
                    success_count += 1
                    PrettyPrint(f"Made always visible: {object_id}")
                else:
                    error_count += 1

            except Exception as e:
                PrettyPrint(f"Error processing {object_id}: {str(e)}", "ERROR")
                error_count += 1

        if success_count > 0:
            msg = f"Made {success_count} unit(s) always visible"
            if error_count > 0:
                msg += f" ({error_count} errors)"
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Failed to modify any units ({error_count} errors)")
            return {'CANCELLED'}


class SaveUnitDataOperator(Operator):
    """Save the current unit data to patch"""
    bl_label = "Save Unit Data"
    bl_idname = "helldiver2.save_unit_data"
    bl_description = "Save the unit's current LOD and visibility settings to the patch"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty()

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        Entry = Global_TocManager.GetEntryByLoadArchive(int(self.object_id), UnitID)
        if Entry is None:
            self.report({'ERROR'}, f"Could not find entry for ID: {self.object_id}")
            return {'CANCELLED'}

        if not Entry.IsLoaded:
            Entry.Load(True, False, True)

        # Add to patch and save
        Entry = Global_TocManager.AddEntryToPatchID(Entry, int(self.object_id))
        BlenderOpts = context.scene.Hd2ToolPanelSettings.get_settings_dict()
        wasSaved = Entry.Save(BlenderOpts=BlenderOpts)

        if not wasSaved:
            self.report({'ERROR'}, "Failed to save unit")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Saved unit data for ID: {self.object_id}")
        return {'FINISHED'}


class AuditUnitLodValuesOperator(Operator, ExportHelper):
    """Audit all loaded units and sort by LOD/visibility values, output to file"""
    bl_label = "Audit Unit LOD Values"
    bl_idname = "helldiver2.audit_unit_lod"
    bl_description = "Scan all archives for units and output sorted by LOD thresholds to a text file"
    bl_options = {'REGISTER'}

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})

    scan_all_archives: BoolProperty(
        name="Scan All Archives",
        description="Scan all archives in game folder (slow but thorough). Requires loading one archive first to populate index.",
        default=True
    )

    sort_by: EnumProperty(
        name="Sort By",
        items=[
            ('lod_min', "Min LOD Threshold", "Sort by smallest LOD threshold value"),
            ('lod_max', "Max LOD Threshold", "Sort by largest LOD threshold value"),
            ('lod_count', "LOD Value Count", "Sort by number of LOD values"),
            ('bbox_size', "Bounding Box Size", "Sort by bounding box volume"),
            ('unk1', "MeshInfo.unk1", "Sort by unk1 value"),
            ('unk3', "MeshInfo.unk3", "Sort by unk3 value"),
            ('unk8', "MeshInfo.unk8", "Sort by unk8 value"),
        ],
        default='lod_min'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scan_all_archives")
        layout.prop(self, "sort_by")

    def execute(self, context):
        import struct
        import gc
        from datetime import datetime
        from pathlib import Path

        # Determine which archives to scan
        archives_to_scan = []
        if self.scan_all_archives:
            if len(Global_TocManager.SearchArchives) > 0:
                archives_to_scan = Global_TocManager.SearchArchives
            else:
                self.report({'ERROR'}, "No search archives available. Load at least one archive first to populate the search index.")
                return {'CANCELLED'}
        else:
            if len(Global_TocManager.LoadedArchives) == 0:
                self.report({'ERROR'}, "No archives loaded")
                return {'CANCELLED'}
            archives_to_scan = Global_TocManager.LoadedArchives

        results = []
        errors = 0
        processed_ids = set()  # Avoid duplicates across archives

        total_archives = len(archives_to_scan)
        BATCH_SIZE = 50  # Process archives in batches to avoid memory explosion

        PrettyPrint(f"UNIT LOD AUDIT - Scanning {total_archives} archives in batches of {BATCH_SIZE}...")

        for batch_start in range(0, total_archives, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_archives)
            batch_archives = archives_to_scan[batch_start:batch_end]

            PrettyPrint(f"=== Batch {batch_start//BATCH_SIZE + 1}: Archives {batch_start+1}-{batch_end} of {total_archives} ===")

            for archive in batch_archives:
                # Get archive name from path
                archive_name = Path(archive.Path).stem if hasattr(archive, 'Path') else "unknown"

                # Get unit file IDs from this archive
                unit_file_ids = []
                loaded_archive = None

                if hasattr(archive, 'TocDict'):
                    # Already a full archive with entries (StreamToc)
                    loaded_archive = archive
                    unit_file_ids = list(archive.TocDict.get(UnitID, {}).keys())
                elif hasattr(archive, 'TocEntries'):
                    # SearchToc - need to load the archive
                    unit_file_ids = archive.TocEntries.get(UnitID, [])
                    if len(unit_file_ids) > 0:
                        try:
                            loaded_archive = Global_TocManager.LoadArchive(archive.Path, SetActive=False)
                        except Exception as e:
                            PrettyPrint(f"  Skipping archive {archive_name} - load error: {e}", 'WARN')
                            errors += 1
                            continue

                if len(unit_file_ids) == 0 or loaded_archive is None:
                    continue

                for file_id in unit_file_ids:
                    # Skip if already processed from another archive
                    if file_id in processed_ids:
                        continue
                    processed_ids.add(file_id)

                    try:
                        entry = loaded_archive.GetEntry(file_id, UnitID)
                        if entry is None:
                            continue

                        # Load if needed
                        if not entry.IsLoaded:
                            entry.Load(False, False, True)

                        if not entry.LoadedData:
                            continue

                        mesh_file = entry.LoadedData

                        # Extract LOD data
                        lod_data = mesh_file.UnreversedLODGroupListData
                        lod_floats = []
                        if lod_data and len(lod_data) >= 4:
                            num_floats = len(lod_data) // 4
                            lod_floats = list(struct.unpack(f'<{num_floats}f', lod_data[:num_floats * 4]))
                            lod_floats = [f for f in lod_floats if -1e6 < f < 1e6]

                        # Extract MeshInfo values (from first mesh)
                        unk1 = unk3 = unk4 = unk8 = 0
                        bbox_size = 0
                        bbox_str = ""
                        unk6_str = ""
                        if mesh_file.MeshInfoArray:
                            mi = mesh_file.MeshInfoArray[0]
                            unk1 = mi.unk1
                            unk3 = mi.unk3
                            unk4 = mi.unk4
                            unk8 = mi.unk8
                            if len(mi.unk2) == 32:
                                bbox = struct.unpack('<8f', mi.unk2)
                                dx = abs(bbox[4] - bbox[0])
                                dy = abs(bbox[5] - bbox[1])
                                dz = abs(bbox[6] - bbox[2])
                                bbox_size = dx * dy * dz
                                bbox_str = f"({bbox[0]:.2f},{bbox[1]:.2f},{bbox[2]:.2f})->({bbox[4]:.2f},{bbox[5]:.2f},{bbox[6]:.2f})"
                            if len(mi.unk6) == 40:
                                unk6 = struct.unpack('<10f', mi.unk6)
                                unk6_str = ",".join([f"{v:.2f}" for v in unk6])

                        # Calculate sort key
                        if self.sort_by == 'lod_min':
                            sort_key = min(lod_floats) if lod_floats else float('inf')
                        elif self.sort_by == 'lod_max':
                            sort_key = max(lod_floats) if lod_floats else 0
                        elif self.sort_by == 'lod_count':
                            sort_key = len(lod_floats)
                        elif self.sort_by == 'bbox_size':
                            sort_key = bbox_size
                        elif self.sort_by == 'unk1':
                            sort_key = unk1
                        elif self.sort_by == 'unk3':
                            sort_key = unk3
                        elif self.sort_by == 'unk8':
                            sort_key = unk8
                        else:
                            sort_key = 0

                        results.append({
                            'file_id': file_id,
                            'archive': archive_name,
                            'sort_key': sort_key,
                            'lod_floats': lod_floats,
                            'lod_min': min(lod_floats) if lod_floats else None,
                            'lod_max': max(lod_floats) if lod_floats else None,
                            'lod_count': len(lod_floats),
                            'lod_all': ",".join([f"{v:.6f}" for v in lod_floats]),
                            'bbox_size': bbox_size,
                            'bbox_str': bbox_str,
                            'unk1': unk1,
                            'unk3': unk3,
                            'unk4': unk4,
                            'unk6_str': unk6_str,
                            'unk8': unk8,
                            'mesh_count': len(mesh_file.MeshInfoArray),
                        })

                    except Exception as e:
                        errors += 1

            # Free memory after each batch - unload archives loaded during this batch
            Global_TocManager.LoadedArchives = []
            Global_TocManager.ActiveArchive = None
            gc.collect()
            PrettyPrint(f"  Batch complete. Units found so far: {len(results)}")

        # Sort results
        reverse = self.sort_by in ['lod_max', 'lod_count', 'bbox_size', 'unk1', 'unk3', 'unk8']
        results.sort(key=lambda x: x['sort_key'], reverse=reverse)

        # Write to file
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.write(f"HD2SDK Unit LOD Audit Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Units: {len(results)} ({errors} errors)\n")
            f.write(f"Sorted by: {self.sort_by} ({'descending' if reverse else 'ascending'})\n")
            f.write("=" * 150 + "\n\n")

            # Header
            f.write(f"{'Archive':<45} {'UnitID':<22} {'LOD Min':>12} {'LOD Max':>12} {'#LOD':>5} {'BBox Vol':>14} {'unk1':>12} {'unk3':>12} {'unk4':>12}\n")
            f.write("-" * 150 + "\n")

            # All results
            for r in results:
                archive_short = r['archive'][-43:] if len(r['archive']) > 43 else r['archive']
                lod_min = f"{r['lod_min']:.6f}" if r['lod_min'] is not None else "N/A"
                lod_max = f"{r['lod_max']:.6f}" if r['lod_max'] is not None else "N/A"
                f.write(f"{archive_short:<45} {r['file_id']:<22} {lod_min:>12} {lod_max:>12} {r['lod_count']:>5} {r['bbox_size']:>14.1f} {r['unk1']:>12} {r['unk3']:>12} {r['unk4']:>12}\n")

            # Detailed section
            f.write("\n\n" + "=" * 150 + "\n")
            f.write("DETAILED DATA (All LOD values, bbox, unk6)\n")
            f.write("=" * 150 + "\n\n")

            for r in results:
                f.write(f"Archive: {r['archive']}\n")
                f.write(f"UnitID: {r['file_id']} (0x{r['file_id']:016x})\n")
                f.write(f"  LOD values: [{r['lod_all']}]\n")
                f.write(f"  Bbox: {r['bbox_str']}\n")
                f.write(f"  unk1: {r['unk1']} (0x{r['unk1']:016x})\n")
                f.write(f"  unk3: {r['unk3']} (0x{r['unk3']:08x})\n")
                f.write(f"  unk4: {r['unk4']} (0x{r['unk4']:08x})\n")
                f.write(f"  unk6: [{r['unk6_str']}]\n")
                f.write(f"  unk8: {r['unk8']} (0x{r['unk8']:016x})\n")
                f.write("\n")

            # Notable entries
            f.write("\n" + "=" * 150 + "\n")
            f.write("NOTABLE ENTRIES\n")
            f.write("=" * 150 + "\n\n")

            always_visible = [r for r in results if r['lod_min'] == 0.0]
            f.write(f"Units with LOD min = 0.0 (potentially always visible): {len(always_visible)}\n")
            for r in always_visible:
                f.write(f"  {r['archive']}_{r['file_id']}\n")

            f.write("\n")
            small_lod = [r for r in results if r['lod_min'] is not None and 0 < r['lod_min'] < 0.01]
            f.write(f"Units with very small LOD min (< 0.01): {len(small_lod)}\n")
            for r in small_lod:
                f.write(f"  {r['archive']}_{r['file_id']} - LOD min: {r['lod_min']:.6f}\n")

        self.report({'INFO'}, f"Audit complete. {len(results)} units written to {self.filepath}")
        return {'FINISHED'}


class BatchSaveStingrayUnitOperator(Operator):
    bl_label  = "Save Units"
    bl_idname = "helldiver2.archive_unit_batchsave"
    bl_description = "Saves Units"
    bl_options = {'REGISTER', 'UNDO'} 

    def execute(self, context):
        start = time.time()
        errors = False
        if UnitNotValidToSave(self):
            return {'CANCELLED'}

        o = bpy.context.selected_objects

        if len(o) == 0:
            self.report({'WARNING'}, "No Objects Selected")
            return {'CANCELLED'}

        IDs = []
        IDswaps = {}
        objects = []
        for object in o:
            if object.type == 'MESH':
                objects.append(object)
        for i, object in enumerate(objects):
            SwapID = ""
            try:
                ID = object["Z_ObjectID"]
                try:
                    SwapID = object["Z_SwapID"]
                    IDswaps[SwapID] = ID
                    PrettyPrint(f"Found Swap of ID: {ID} Swap: {SwapID}")
                    if SwapID != "" and not SwapID.isnumeric():
                        self.report({"ERROR"}, f"Object: {object.name} has an incorrect Swap ID. Assure that the ID is a proper integer entry ID.")
                        return {'CANCELLED'}
                except:
                    self.report({'INFO'}, f"{object.name} has no HD2 Swap ID. Skipping Swap.")
                IDitem = [ID, SwapID]
                if IDitem not in IDs:
                    IDs.append(IDitem)
            except KeyError:
                self.report({'ERROR'}, f"{object.name} has no HD2 custom properties")
                return {'CANCELLED'}
        num_initially_selected = len(objects)
        swapCheck = {}
        for IDitem in IDs:
            ID = IDitem[0]
            SwapID = IDitem[1]
            if swapCheck.get(ID) == None:
                swapCheck[ID] = SwapID
            else:
                if (swapCheck[ID] == "" and SwapID != "") or (swapCheck[ID] != "" and SwapID == ""):
                    self.report({'ERROR'}, f"All Lods of object: {object.name} must have a swap ID! If you want to have an entry save to itself whilst swapping, set the SwapID to its own ObjectID.")
                    return {'CANCELLED'}
        objects_by_id = {}
        for obj in objects:
            try:
                objects_by_id[obj["Z_ObjectID"]][obj["MeshInfoIndex"]] = obj
            except KeyError:
                objects_by_id[obj["Z_ObjectID"]] = {obj["MeshInfoIndex"]: obj}
        global Global_BoneNames
        BlenderOpts = bpy.context.scene.Hd2ToolPanelSettings.get_settings_dict()
        num_meshes = len(objects)
        entries = []
        for IDitem in IDs:
            ID = IDitem[0]
            SwapID = IDitem[1]
            Entry = Global_TocManager.GetEntryByLoadArchive(int(ID), UnitID)
            if Entry is None:
                self.report({'ERROR'}, f"Archive for entry being saved is not loaded. Could not find custom property object at ID: {ID}")
                errors = True
                entries.append(None)
                continue
            Entry.Load(True, False, True)
            dest_id = int(ID)
            if SwapID and SwapID.isnumeric() and SwapID != ID:
                dest_id = int(SwapID)
            Entry = Global_TocManager.AddEntryToPatchID(Entry, dest_id)
            entries.append(Entry)
        MeshData = GetObjectsMeshData(Global_TocManager, Global_BoneNames)    
        for i, IDitem in enumerate(IDs):
            ID = IDitem[0]
            SwapID = IDitem[1]
            if SwapID and SwapID.isnumeric():
                ID = SwapID
            Entry = entries[i]
            if Entry is None:
                num_meshes -= len(MeshData[ID])
                continue
            MeshList = MeshData[ID]
            for mesh_index, mesh in MeshList.items():
                try:
                    Entry.LoadedData.RawMeshes[mesh_index] = mesh
                except IndexError:
                    excpectedLength = len(Entry.LoadedData.RawMeshes) - 1
                    self.report({'ERROR'},f"MeshInfoIndex of {mesh_index} for {object.name} exceeds the number of meshes. Expected maximum MeshInfoIndex is: {excpectedLength}. Please change the custom properties to match this value and resave the unit.")
                    errors = True
                    num_meshes -= 1
            wasSaved = Entry.Save(BlenderOpts=BlenderOpts)
            if not wasSaved:
                self.report({"ERROR"}, f"Failed to save unit with ID {ID}.")
                num_meshes -= len(MeshData[ID])
                continue
        PrettyPrint("Saving unit materials")
        SaveMeshMaterials(objects)
        self.report({'INFO'}, f"Saved {num_meshes}/{num_initially_selected} selected Units")
        if errors:
            self.report({'ERROR'}, f"Errors occurred while saving units. Click here to view.")
        PrettyPrint(f"Time to save units: {time.time()-start}")
        return{'FINISHED'}

class OverrideAllHelmetsOperator(Operator):
    bl_label = "Override All Helmets"
    bl_idname = "helldiver2.override_all_helmets"
    bl_description = "Replace all helmet meshes with the selected patched unit"
    bl_options = {'REGISTER', 'UNDO'}

    object_id: StringProperty(name="Object ID", default="")

    _timer = None
    _helmet_list = None
    _helmet_index = 0
    _success_count = 0
    _error_count = 0
    _source_toc_data = None
    _source_gpu_data = None
    _source_stream_data = None
    _source_materials = None  # Dict of {MaterialID: (TocData, GpuData, StreamData)}
    _source_textures = None   # Dict of {TexID: (TocData, GpuData, StreamData)}
    _start_time = 0

    def modal(self, context, event):
        if event.type == 'TIMER':
            # Process one helmet per timer tick
            if self._helmet_index >= len(self._helmet_list):
                # Done processing all helmets
                self.finish(context)
                elapsed = time.time() - self._start_time
                self.report({'INFO'}, f"Overridden {self._success_count}/{len(self._helmet_list)} helmets in {elapsed:.2f}s. Errors: {self._error_count}")
                return {'FINISHED'}

            hex_id, helmet_name = self._helmet_list[self._helmet_index]
            self._helmet_index += 1

            # Update status
            context.workspace.status_text_set(f"Processing helmet {self._helmet_index}/{len(self._helmet_list)}: {helmet_name}")

            try:
                # Load the archive to get the actual unit FileIDs inside
                archive_path = Global_gamepath + hex_id
                loaded_archive = Global_TocManager.LoadArchive(archive_path)

                if loaded_archive is None:
                    PrettyPrint(f"Could not load archive for helmet: {helmet_name}")
                    self._error_count += 1
                    return {'RUNNING_MODAL'}

                # Get the actual unit FileIDs from this archive
                unit_entries = loaded_archive.TocDict.get(UnitID, {})
                if len(unit_entries) == 0:
                    PrettyPrint(f"No unit entries in helmet archive: {helmet_name}")
                    self._error_count += 1
                    return {'RUNNING_MODAL'}

                # For each unit in this helmet archive, create a patch entry with copied binary data
                for unit_file_id in unit_entries.keys():
                    # Create new entry with same binary data but different FileID
                    patch_entry = TocEntry()
                    patch_entry.FileID = unit_file_id
                    patch_entry.TypeID = UnitID
                    patch_entry.IsModified = True
                    patch_entry.TocData = bytes(self._source_toc_data)
                    patch_entry.GpuData = bytes(self._source_gpu_data)
                    patch_entry.StreamData = bytes(self._source_stream_data)
                    patch_entry.TocData_Size = len(patch_entry.TocData)
                    patch_entry.GpuData_Size = len(patch_entry.GpuData)
                    patch_entry.StreamData_Size = len(patch_entry.StreamData)

                    # Add to patch
                    Global_TocManager.ActivePatch.AddEntry(patch_entry, override=True)

                # Also add all materials from the source mesh
                for mat_id, (toc_data, gpu_data, stream_data) in self._source_materials.items():
                    mat_entry = TocEntry()
                    mat_entry.FileID = mat_id
                    mat_entry.TypeID = MaterialID
                    mat_entry.IsModified = True
                    mat_entry.TocData = bytes(toc_data)
                    mat_entry.GpuData = bytes(gpu_data)
                    mat_entry.StreamData = bytes(stream_data)
                    mat_entry.TocData_Size = len(mat_entry.TocData)
                    mat_entry.GpuData_Size = len(mat_entry.GpuData)
                    mat_entry.StreamData_Size = len(mat_entry.StreamData)
                    Global_TocManager.ActivePatch.AddEntry(mat_entry, override=True)

                # Also add all textures from the source materials
                for tex_id, (toc_data, gpu_data, stream_data) in self._source_textures.items():
                    tex_entry = TocEntry()
                    tex_entry.FileID = tex_id
                    tex_entry.TypeID = TexID
                    tex_entry.IsModified = True
                    tex_entry.TocData = bytes(toc_data)
                    tex_entry.GpuData = bytes(gpu_data)
                    tex_entry.StreamData = bytes(stream_data)
                    tex_entry.TocData_Size = len(tex_entry.TocData)
                    tex_entry.GpuData_Size = len(tex_entry.GpuData)
                    tex_entry.StreamData_Size = len(tex_entry.StreamData)
                    Global_TocManager.ActivePatch.AddEntry(tex_entry, override=True)

                self._success_count += 1

            except Exception as e:
                PrettyPrint(f"Error processing helmet {helmet_name}: {str(e)}")
                self._error_count += 1

            return {'RUNNING_MODAL'}

        elif event.type == 'ESC':
            self.finish(context)
            self.report({'WARNING'}, f"Cancelled. Processed {self._success_count} helmets before cancellation.")
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.workspace.status_text_set(None)

    def invoke(self, context, event):
        self._start_time = time.time()

        # Validate patches are loaded
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        # Get the entry by object_id
        if not self.object_id:
            self.report({'ERROR'}, "No unit specified")
            return {'CANCELLED'}

        try:
            file_id = int(self.object_id)
        except ValueError:
            self.report({'ERROR'}, f"Invalid object ID: {self.object_id}")
            return {'CANCELLED'}

        # Get the patch version of the entry which has the binary data
        patch_source = Global_TocManager.ActivePatch.GetEntry(file_id, UnitID)
        if patch_source is None:
            self.report({'ERROR'}, "Unit must be in the patch. Save the mesh first.")
            return {'CANCELLED'}

        # Ensure binary data exists
        if patch_source.TocData is None or len(patch_source.TocData) == 0:
            self.report({'ERROR'}, "Source entry has no binary data. Save the mesh first.")
            return {'CANCELLED'}

        # Store the binary data from the source entry
        self._source_toc_data = bytes(patch_source.TocData)
        self._source_gpu_data = bytes(patch_source.GpuData) if patch_source.GpuData else b""
        self._source_stream_data = bytes(patch_source.StreamData) if patch_source.StreamData else b""

        PrettyPrint(f"Source entry binary sizes - Toc: {len(self._source_toc_data)}, Gpu: {len(self._source_gpu_data)}, Stream: {len(self._source_stream_data)}")

        # Load and parse the source mesh to get MaterialIDs
        self._source_materials = {}
        self._source_textures = {}

        try:
            # Parse the mesh to extract MaterialIDs
            if not patch_source.IsLoaded:
                patch_source.Load(False, False, True)  # Load without creating Blender objects

            if patch_source.LoadedData and hasattr(patch_source.LoadedData, 'MaterialIDs'):
                material_ids = patch_source.LoadedData.MaterialIDs
                PrettyPrint(f"Found {len(material_ids)} materials in source mesh: {material_ids}")

                for mat_id in material_ids:
                    # Get material entry from patch or archive
                    mat_entry = Global_TocManager.GetEntry(mat_id, MaterialID, SearchAll=True)
                    if mat_entry and mat_entry.TocData:
                        self._source_materials[mat_id] = (
                            bytes(mat_entry.TocData),
                            bytes(mat_entry.GpuData) if mat_entry.GpuData else b"",
                            bytes(mat_entry.StreamData) if mat_entry.StreamData else b""
                        )
                        PrettyPrint(f"Collected material {mat_id}")

                        # Load material to get texture IDs
                        if not mat_entry.IsLoaded:
                            mat_entry.Load(False, False)

                        if mat_entry.LoadedData and hasattr(mat_entry.LoadedData, 'TexIDs'):
                            for tex_id in mat_entry.LoadedData.TexIDs:
                                if tex_id not in self._source_textures:
                                    tex_entry = Global_TocManager.GetEntry(tex_id, TexID, SearchAll=True)
                                    if tex_entry and tex_entry.TocData:
                                        self._source_textures[tex_id] = (
                                            bytes(tex_entry.TocData),
                                            bytes(tex_entry.GpuData) if tex_entry.GpuData else b"",
                                            bytes(tex_entry.StreamData) if tex_entry.StreamData else b""
                                        )
                                        PrettyPrint(f"Collected texture {tex_id}")

                PrettyPrint(f"Total collected: {len(self._source_materials)} materials, {len(self._source_textures)} textures")
        except Exception as e:
            PrettyPrint(f"Warning: Could not collect materials/textures: {str(e)}")

        # Load helmet IDs from archivehashes.json
        try:
            with open(Global_archivehashpath, "r") as f:
                archive_data = json.load(f)
            helmet_ids = archive_data.get("Helmet", {})
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load archivehashes.json: {str(e)}")
            return {'CANCELLED'}

        if len(helmet_ids) == 0:
            self.report({'ERROR'}, "No helmets found in archivehashes.json")
            return {'CANCELLED'}

        # Store state for modal
        self._helmet_list = list(helmet_ids.items())
        self._helmet_index = 0
        self._success_count = 0
        self._error_count = 0

        # Start timer for modal processing
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)

        self.report({'INFO'}, f"Starting to process {len(self._helmet_list)} helmets with {len(self._source_materials)} materials and {len(self._source_textures)} textures...")
        return {'RUNNING_MODAL'}

def SaveMeshMaterials(objects):
    if not bpy.context.scene.Hd2ToolPanelSettings.AutoSaveUnitMaterials:
        PrettyPrint(f"Skipping saving of materials as setting is disabled")
        return
    PrettyPrint(f"Saving materials for {len(objects)} objects")
    materials = []
    for object in objects:
        for slot in object.material_slots:
            if slot.material:
                materialName = slot.material.name
                PrettyPrint(f"Found material: {materialName} in {object.name}")
                try: 
                    material = bpy.data.materials[materialName]
                except:
                    raise Exception(f"Could not find material: {materialName}")
                if material not in materials:
                    materials.append(material)

    PrettyPrint(f"Found {len(materials)} unique materials {materials}")
    for material in materials:
        try:
            ID = int(material.name)
        except:
            PrettyPrint(f"Failed to convert material: {material.name} to ID")
            continue

        nodeName = ""
        for node in material.node_tree.nodes:
            if node.type == 'GROUP':
                nodeName = node.node_tree.name
                PrettyPrint(f"ID: {ID} Group: {nodeName}")
                break

        if nodeName == "" and not bpy.context.scene.Hd2ToolPanelSettings.SaveNonSDKMaterials:
            PrettyPrint(f"Cancelling Saving Material: {ID}")
            continue

        entry = Global_TocManager.GetEntry(ID, MaterialID)
        if entry:
            if not entry.IsModified:
                PrettyPrint(f"Saving material: {ID}")
                Global_TocManager.Save(ID, MaterialID)
            else:
                PrettyPrint(f"Skipping Saving Material: {ID} as it already has been modified")
        elif "-" in nodeName:
            if str(ID) in nodeName.split("-")[1]:
                template = nodeName.split("-")[0]
                PrettyPrint(f"Creating material: {ID} with template: {template}")
                CreateModdedMaterial(template, ID)
                Global_TocManager.Save(ID, MaterialID)
            else:
                PrettyPrint(f"Failed to find template from group: {nodeName}", "error")
        else:
            PrettyPrint(f"Failed to save material: {ID}", "error")


#endregion

#region Operators: Textures

# save texture from blender to archive button
# TODO: allow the user to choose an image, instead of looking for one of the same name
class SaveTextureFromBlendImageOperator(Operator):
    bl_label = "Save Texture"
    bl_idname = "helldiver2.texture_saveblendimage"
    bl_description = "Saves Texture"

    object_id: StringProperty()
    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        Entries = EntriesFromString(self.object_id, TexID)
        for Entry in Entries:
            if Entry != None:
                if not Entry.IsLoaded: Entry.Load()
                try:
                    BlendImageToStingrayTexture(bpy.data.images[str(self.object_id)], Entry.LoadedData)
                except:
                    PrettyPrint("No blend texture was found for saving, using original", "warn"); pass
            Global_TocManager.Save(Entry.FileID, TexID)
        return{'FINISHED'}

# import texture from archive button
class ImportTextureOperator(Operator):
    bl_label = "Import Texture"
    bl_idname = "helldiver2.texture_import"
    bl_description = "Loads Texture into Blender Project"

    object_id: StringProperty()
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            Global_TocManager.Load(int(EntryID), TexID)
        return{'FINISHED'}

# export texture to file
class ExportTextureOperator(Operator, ExportHelper):
    bl_label = "Export Texture"
    bl_idname = "helldiver2.texture_export"
    bl_description = "Export Texture to a Desired File Location"
    filename_ext = ".dds"

    filter_glob: StringProperty(default='*.dds', options={'HIDDEN'})
    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        Entry = Global_TocManager.GetEntry(int(self.object_id), TexID)
        if Entry != None:
            data = Entry.Load(False, False)
            with open(self.filepath, 'w+b') as f:
                f.write(Entry.LoadedData.ToDDS())
        return{'FINISHED'}
    
    def invoke(self, context, _event):
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if not blend_filepath:
                blend_filepath = self.object_id
            else:
                blend_filepath = os.path.splitext(blend_filepath)[0]

            self.filepath = blend_filepath + self.filename_ext

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class ExportTexturePNGOperator(Operator, ExportHelper):
    bl_label = "Export Texture"
    bl_idname = "helldiver2.texture_export_png"
    bl_description = "Export Texture to a Desired File Location"
    filename_ext = ".png"

    filter_glob: StringProperty(default='*.png', options={'HIDDEN'})
    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        Global_TocManager.Load(int(self.object_id), TexID)
        Entry = Global_TocManager.GetEntry(int(self.object_id), TexID)
        if Entry != None:
            tempdir = get_temp_folder()
            for i in range(Entry.LoadedData.ArraySize):
                filename = os.path.basename(self.filepath)
                directory = self.filepath.replace(filename, "")
                filename = filename.replace(".png", "")
                layer = "" if Entry.LoadedData.ArraySize == 1 else f"_layer{i}"
                dds_path = f"{tempdir}/{filename}{layer}.dds"
                with open(dds_path, 'w+b') as f:
                    if Entry.LoadedData.ArraySize == 1:
                        f.write(Entry.LoadedData.ToDDS())
                    else:
                        f.write(Entry.LoadedData.ToDDSArray()[i])
                subprocess.run([Global_texconvpath, "-y", "-o", directory, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-sepalpha", "-alpha", dds_path])
                if os.path.isfile(dds_path):
                    self.report({'INFO'}, f"Saved PNG Texture to: {dds_path}")
                else:
                    self.report({'ERROR'}, f"Failed to Save Texture: {dds_path}")
        return{'FINISHED'}
    
    def invoke(self, context, event):
        blend_filepath = context.blend_data.filepath
        filename = f"{self.object_id}.png"
        self.filepath = blend_filepath + filename
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# batch export texture to file
class BatchExportTextureOperator(Operator):
    bl_label = "Export Textures"
    bl_idname = "helldiver2.texture_batchexport"
    bl_description = "Export Textures to a Desired File Location"
    filename_ext = ".dds"

    directory: StringProperty(name="Outdir Path",description="dds output dir")
    filter_folder: BoolProperty(default=True,options={"HIDDEN"})

    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            Entry = Global_TocManager.GetEntry(EntryID, TexID)
            if Entry != None:
                data = Entry.Load(False, False)
                with open(self.directory + str(Entry.FileID)+".dds", 'w+b') as f:
                    f.write(Entry.LoadedData.ToDDS())
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class BatchExportTexturePNGOperator(Operator):
    bl_label = "Export Texture"
    bl_idname = "helldiver2.texture_batchexport_png"
    bl_description = "Export Textures to a Desired File Location"
    filename_ext = ".png"

    directory: StringProperty(name="Outdir Path",description="png output dir")
    filter_folder: BoolProperty(default=True,options={"HIDDEN"})

    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        exportedfiles = 0
        for EntryID in EntriesIDs:
            Global_TocManager.Load(EntryID, TexID)
            Entry = Global_TocManager.GetEntry(EntryID, TexID)
            if Entry != None:
                tempdir = get_temp_folder()
                dds_path = f"{tempdir}/{EntryID}.dds"
                with open(dds_path, 'w+b') as f:
                    f.write(Entry.LoadedData.ToDDS())
                subprocess.run([Global_texconvpath, "-y", "-o", self.directory, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-alpha", dds_path])
                filepath = f"{self.directory}/{EntryID}.png"
                if os.path.isfile(filepath):
                    exportedfiles += 1
                else:
                    self.report({'ERROR'}, f"Failed to save texture as PNG: {filepath}")
        self.report({'INFO'}, f"Exported {exportedfiles} PNG Files To: {self.directory}")
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# Helper function to check if a texture is likely a UI atlas using raw file analysis (no Blender)
def is_ui_atlas_texture_fast(png_path, black_threshold=0.6, max_unique_colors=50):
    """
    Fast PNG analysis without Blender's image loading.
    Reads PNG directly and samples pixels for speed.
    """
    try:
        import struct
        import zlib

        with open(png_path, 'rb') as f:
            # Verify PNG signature
            sig = f.read(8)
            if sig != b'\x89PNG\r\n\x1a\n':
                return False, 0, 0

            width = height = 0
            idat_data = b''

            # Read chunks
            while True:
                chunk_len = struct.unpack('>I', f.read(4))[0]
                chunk_type = f.read(4)

                if chunk_type == b'IHDR':
                    data = f.read(chunk_len)
                    width, height = struct.unpack('>II', data[:8])
                    f.read(4)  # CRC
                elif chunk_type == b'IDAT':
                    idat_data += f.read(chunk_len)
                    f.read(4)  # CRC
                elif chunk_type == b'IEND':
                    break
                else:
                    f.read(chunk_len + 4)

            # Decompress image data
            raw_data = zlib.decompress(idat_data)

            # Sample pixels (stride = width * 4 + 1 for filter byte)
            stride = width * 4 + 1
            black_count = 0
            unique_colors = set()
            sample_step = max(1, (width * height) // 5000)  # Sample ~5000 pixels
            sampled = 0

            for y in range(0, height, max(1, int(sample_step ** 0.5))):
                row_start = y * stride + 1  # Skip filter byte
                for x in range(0, width, max(1, int(sample_step ** 0.5))):
                    idx = row_start + x * 4
                    if idx + 3 >= len(raw_data):
                        continue
                    r, g, b, a = raw_data[idx], raw_data[idx+1], raw_data[idx+2], raw_data[idx+3]
                    sampled += 1

                    # Check black or transparent
                    if a < 25 or (r < 13 and g < 13 and b < 13):
                        black_count += 1

                    # Quantize colors
                    color_key = (r // 25, g // 25, b // 25)
                    unique_colors.add(color_key)

            if sampled == 0:
                return False, 0, 0

            black_ratio = black_count / sampled
            num_colors = len(unique_colors)

            return black_ratio >= black_threshold and num_colors <= max_unique_colors, black_ratio, num_colors

    except Exception as e:
        # Fallback to slower Blender method
        return is_ui_atlas_texture_blender(png_path, black_threshold, max_unique_colors)

def is_ui_atlas_texture_blender(png_path, black_threshold=0.6, max_unique_colors=50):
    """Fallback Blender-based analysis."""
    try:
        img = bpy.data.images.load(png_path)
        pixels = img.pixels[:]  # Faster than list()
        total_pixels = img.size[0] * img.size[1]

        black_count = 0
        unique_colors = set()
        sample_step = max(4, (total_pixels // 2500) * 4)

        for i in range(0, len(pixels), sample_step):
            if i + 3 >= len(pixels):
                break
            r, g, b, a = pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]

            if a < 0.1 or (r < 0.05 and g < 0.05 and b < 0.05):
                black_count += 1

            color_key = (int(r * 10), int(g * 10), int(b * 10))
            unique_colors.add(color_key)

        bpy.data.images.remove(img)

        sampled = len(pixels) // sample_step
        black_ratio = black_count / sampled if sampled > 0 else 0
        return black_ratio >= black_threshold and len(unique_colors) <= max_unique_colors, black_ratio, len(unique_colors)

    except Exception as e:
        return False, 0, 0

# Helper function for template matching - extract color signature once, reuse for all textures
def extract_template_colors(template_path):
    """Extract color signature from template image (call once, reuse for all comparisons)."""
    try:
        img = bpy.data.images.load(template_path)
        pixels = img.pixels[:]

        template_colors = {}
        sample_step = max(4, len(pixels) // 10000)

        for i in range(0, len(pixels), sample_step):
            if i + 3 >= len(pixels):
                break
            r, g, b, a = pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]

            if a < 0.1 or (r < 0.1 and g < 0.1 and b < 0.1):
                continue

            color_key = (round(r, 1), round(g, 1), round(b, 1))
            template_colors[color_key] = template_colors.get(color_key, 0) + 1

        bpy.data.images.remove(img)
        return template_colors

    except Exception as e:
        PrettyPrint(f"Error extracting template colors: {str(e)}", "warn")
        return {}

def match_texture_to_template(texture_path, template_colors, threshold=0.8):
    """Fast color matching using pre-extracted template colors."""
    try:
        img = bpy.data.images.load(texture_path)
        pixels = img.pixels[:]

        texture_colors = {}
        sample_step = max(4, len(pixels) // 10000)

        for i in range(0, len(pixels), sample_step):
            if i + 3 >= len(pixels):
                break
            r, g, b, a = pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]

            if a < 0.1 or (r < 0.1 and g < 0.1 and b < 0.1):
                continue

            color_key = (round(r, 1), round(g, 1), round(b, 1))
            texture_colors[color_key] = texture_colors.get(color_key, 0) + 1

        bpy.data.images.remove(img)

        if not template_colors:
            return False, 0

        matched = sum(1 for c in template_colors if c in texture_colors)
        match_score = matched / len(template_colors)

        return match_score >= threshold, match_score

    except Exception as e:
        return False, 0

# Try to import OpenCV for better template matching
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None
    np = None


def compute_image_hash(image_path, hash_size=16):
    """
    Compute a perceptual hash (difference hash) for an image.
    Returns a binary hash that can be compared with Hamming distance.
    Works with or without OpenCV.
    """
    if OPENCV_AVAILABLE and cv2 is not None:
        try:
            img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                return None

            # Convert to grayscale
            if len(img.shape) == 3:
                if img.shape[2] == 4:
                    # RGBA - use alpha as mask for transparent pixels
                    gray = cv2.cvtColor(img[:,:,:3], cv2.COLOR_BGR2GRAY)
                    alpha = img[:,:,3]
                    # Set transparent pixels to a neutral value
                    gray[alpha < 128] = 128
                else:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            # Resize to hash_size+1 x hash_size
            resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)

            # Compute difference hash (compare adjacent pixels)
            diff = resized[:, 1:] > resized[:, :-1]

            # Convert to integer hash
            return diff.flatten()
        except Exception as e:
            PrettyPrint(f"Error computing image hash (OpenCV): {str(e)}", "warn")
            return None
    else:
        # Fallback using Blender's image loading
        try:
            img = bpy.data.images.load(image_path)
            pixels = img.pixels[:]
            w, h = img.size[0], img.size[1]
            bpy.data.images.remove(img)

            # Sample pixels at grid positions
            grid_vals = []
            for gy in range(hash_size):
                for gx in range(hash_size + 1):
                    px = int(gx / (hash_size + 1) * w)
                    py = int(gy / hash_size * h)
                    px = min(px, w - 1)
                    py = min(py, h - 1)
                    idx = (py * w + px) * 4
                    if idx + 3 < len(pixels):
                        r, g, b, a = pixels[idx], pixels[idx+1], pixels[idx+2], pixels[idx+3]
                        # Grayscale value, neutral for transparent
                        if a < 0.5:
                            grid_vals.append(0.5)
                        else:
                            grid_vals.append(0.299 * r + 0.587 * g + 0.114 * b)
                    else:
                        grid_vals.append(0.5)

            # Compute difference hash
            diff = []
            for gy in range(hash_size):
                for gx in range(hash_size):
                    idx = gy * (hash_size + 1) + gx
                    diff.append(grid_vals[idx + 1] > grid_vals[idx])

            return diff
        except Exception as e:
            PrettyPrint(f"Error computing image hash (Blender): {str(e)}", "warn")
            return None


def hash_similarity(hash1, hash2):
    """
    Compute similarity between two image hashes (0.0 to 1.0).
    Uses Hamming distance - perfect match = 1.0
    """
    if hash1 is None or hash2 is None:
        return 0.0

    if len(hash1) != len(hash2):
        return 0.0

    # Count matching bits
    if OPENCV_AVAILABLE and hasattr(hash1, 'flatten'):
        matches = np.sum(hash1 == hash2)
        total = len(hash1.flatten())
    else:
        matches = sum(1 for a, b in zip(hash1, hash2) if a == b)
        total = len(hash1)

    return matches / total if total > 0 else 0.0


def compute_mse_similarity(image_path, template_path, target_size=64):
    """
    Compute structural similarity between two images using SSIM and contrast matching.
    Returns similarity score 0.0 to 1.0 (1.0 = identical).

    Uses multiple checks to filter false positives:
    1. SSIM (Structural Similarity Index) - captures structural patterns
    2. Contrast ratio - ensures both images have similar variance/texture density
    3. Mean brightness difference - catches very different overall appearances

    This is more robust than MSE alone for fog/noise textures where two "mostly white"
    images can have high MSE similarity even though one has visible patterns and other is flat.
    """
    if not OPENCV_AVAILABLE or cv2 is None:
        return 1.0  # If OpenCV unavailable, don't filter

    try:
        # Load both images
        img1 = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        img2 = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)

        if img1 is None or img2 is None:
            return 0.0

        # Convert to grayscale for comparison
        if len(img1.shape) == 3:
            if img1.shape[2] == 4:
                gray1 = cv2.cvtColor(img1[:,:,:3], cv2.COLOR_BGR2GRAY)
            else:
                gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = img1

        if len(img2.shape) == 3:
            if img2.shape[2] == 4:
                gray2 = cv2.cvtColor(img2[:,:,:3], cv2.COLOR_BGR2GRAY)
            else:
                gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray2 = img2

        # Resize both to same size for comparison
        resized1 = cv2.resize(gray1, (target_size, target_size), interpolation=cv2.INTER_AREA)
        resized2 = cv2.resize(gray2, (target_size, target_size), interpolation=cv2.INTER_AREA)

        # Convert to float for calculations
        f1 = resized1.astype(np.float32)
        f2 = resized2.astype(np.float32)

        # 1. Compute SSIM (Structural Similarity Index)
        # SSIM = (2*mu1*mu2 + C1) * (2*sigma12 + C2) / ((mu1^2 + mu2^2 + C1) * (sigma1^2 + sigma2^2 + C2))
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        mu1 = np.mean(f1)
        mu2 = np.mean(f2)
        sigma1_sq = np.var(f1)
        sigma2_sq = np.var(f2)
        sigma12 = np.mean((f1 - mu1) * (f2 - mu2))

        ssim = ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2))

        # 2. Check contrast ratio (standard deviation ratio)
        # Both images should have similar "texture density"
        std1 = np.sqrt(sigma1_sq)
        std2 = np.sqrt(sigma2_sq)

        # Avoid division by zero
        if std2 < 1.0:
            std2 = 1.0
        if std1 < 1.0:
            std1 = 1.0

        contrast_ratio = min(std1, std2) / max(std1, std2)

        # 3. Check mean brightness difference
        mean_diff = abs(mu1 - mu2) / 255.0
        brightness_sim = 1.0 - mean_diff

        # Combine scores: require all three to be good
        # SSIM is most important for structural matching
        # Contrast ratio catches "flat vs textured" mismatches
        # Brightness similarity catches overall appearance differences
        combined = ssim * 0.5 + contrast_ratio * 0.3 + brightness_sim * 0.2

        # Also apply a hard threshold: if contrast ratio is too low, reject
        # This catches the case where template has texture but candidate is flat
        if contrast_ratio < 0.3:
            combined = combined * 0.5  # Penalize heavily

        return max(0.0, min(1.0, combined))
    except Exception as e:
        return 0.0


def compute_histogram_similarity(image_path, template_histogram):
    """
    Compare image histogram to template histogram.
    Returns similarity score 0.0 to 1.0.
    """
    if not OPENCV_AVAILABLE or cv2 is None:
        return 0.0

    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return 0.0

        # Convert to BGR if RGBA
        if len(img.shape) == 3 and img.shape[2] == 4:
            # Use only non-transparent pixels
            alpha = img[:,:,3]
            mask = (alpha > 128).astype(np.uint8) * 255
            bgr = img[:,:,:3]
        else:
            bgr = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            mask = None

        # Compute histogram
        hist = cv2.calcHist([bgr], [0, 1, 2], mask, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        # Compare using correlation
        similarity = cv2.compareHist(template_histogram, hist, cv2.HISTCMP_CORREL)
        return max(0.0, similarity)  # Clamp to 0-1

    except Exception as e:
        return 0.0


def compute_histogram(image_path):
    """Compute color histogram for an image."""
    if not OPENCV_AVAILABLE or cv2 is None:
        return None

    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None

        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:,:,3]
            mask = (alpha > 128).astype(np.uint8) * 255
            bgr = img[:,:,:3]
        else:
            bgr = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            mask = None

        hist = cv2.calcHist([bgr], [0, 1, 2], mask, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        return hist

    except Exception as e:
        return None


def find_template_contained(texture_path, template_path, threshold=0.7):
    """
    Check if template image is contained within texture.
    Returns (found, score, location) where location is (x, y) of best match.
    Uses multi-scale template matching to find the template at any size.
    """
    if not OPENCV_AVAILABLE or cv2 is None:
        return False, 0.0, None

    try:
        texture = cv2.imread(texture_path, cv2.IMREAD_UNCHANGED)
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)

        if texture is None or template is None:
            return False, 0.0, None

        # Convert to grayscale, handling alpha
        def to_gray_with_alpha(img):
            if len(img.shape) == 3:
                if img.shape[2] == 4:
                    gray = cv2.cvtColor(img[:,:,:3], cv2.COLOR_BGR2GRAY)
                    alpha = img[:,:,3]
                    # Treat transparent as white (background)
                    gray[alpha < 128] = 255
                    return gray, alpha
                else:
                    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None
            return img, None

        tex_gray, _ = to_gray_with_alpha(texture)
        tpl_gray, tpl_alpha = to_gray_with_alpha(template)

        # Create mask from alpha if available
        tpl_mask = None
        if tpl_alpha is not None:
            tpl_mask = (tpl_alpha > 128).astype(np.uint8) * 255

        best_score = 0.0
        best_loc = None
        best_scale = 1.0

        # Try multiple scales
        tex_h, tex_w = tex_gray.shape[:2]
        tpl_h, tpl_w = tpl_gray.shape[:2]

        # Calculate scale range based on size difference
        min_scale = max(0.1, min(16 / tpl_w, 16 / tpl_h))  # Don't go smaller than 16px
        max_scale = min(4.0, min(tex_w / tpl_w, tex_h / tpl_h) * 0.9)  # Don't exceed texture size

        scales = [s for s in [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
                  if min_scale <= s <= max_scale]

        if not scales:
            scales = [1.0]

        for scale in scales:
            new_w = int(tpl_w * scale)
            new_h = int(tpl_h * scale)

            if new_w < 8 or new_h < 8:
                continue
            if new_w > tex_w or new_h > tex_h:
                continue

            # Resize template
            tpl_scaled = cv2.resize(tpl_gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Resize mask if available
            mask_scaled = None
            if tpl_mask is not None:
                mask_scaled = cv2.resize(tpl_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

            # Template matching
            if mask_scaled is not None:
                result = cv2.matchTemplate(tex_gray, tpl_scaled, cv2.TM_CCORR_NORMED, mask=mask_scaled)
            else:
                result = cv2.matchTemplate(tex_gray, tpl_scaled, cv2.TM_CCOEFF_NORMED)

            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_scale = scale

                if best_score >= 0.95:
                    break

        return best_score >= threshold, best_score, best_loc

    except Exception as e:
        PrettyPrint(f"Error in contains matching: {str(e)}", "warn")
        return False, 0.0, None


def get_template_dimensions(template_path):
    """Get dimensions of template image."""
    if OPENCV_AVAILABLE and cv2 is not None:
        try:
            img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                return img.shape[1], img.shape[0]  # width, height
        except:
            pass

    # Fallback to Blender
    try:
        img = bpy.data.images.load(template_path)
        dims = (img.size[0], img.size[1])
        bpy.data.images.remove(img)
        return dims
    except:
        return None, None


def find_template_opencv(texture_path, template_path, threshold=0.7, check_rotations=True):
    """
    Use OpenCV for fast, accurate template matching.
    Handles multiple scales and rotations.
    Returns (found, best_score, best_scale, best_rotation)
    """
    if not OPENCV_AVAILABLE:
        return False, 0, 1.0, 0

    try:
        # Load images
        texture = cv2.imread(texture_path, cv2.IMREAD_UNCHANGED)
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)

        if texture is None or template is None:
            return False, 0, 1.0, 0

        # Convert to grayscale for matching
        if len(texture.shape) == 3:
            tex_gray = cv2.cvtColor(texture, cv2.COLOR_BGR2GRAY)
        else:
            tex_gray = texture

        if len(template.shape) == 3:
            tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            tpl_gray = template

        best_score = 0
        best_scale = 1.0
        best_rotation = 0

        # Try different scales
        scales = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        rotations = [0, 90, 180, 270] if check_rotations else [0]

        for rotation in rotations:
            # Rotate template
            if rotation == 0:
                tpl_rotated = tpl_gray
            else:
                center = (tpl_gray.shape[1] // 2, tpl_gray.shape[0] // 2)
                matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
                tpl_rotated = cv2.warpAffine(tpl_gray, matrix, (tpl_gray.shape[1], tpl_gray.shape[0]))

            for scale in scales:
                # Resize template
                new_w = int(tpl_rotated.shape[1] * scale)
                new_h = int(tpl_rotated.shape[0] * scale)

                if new_w < 5 or new_h < 5:
                    continue
                if new_w > tex_gray.shape[1] or new_h > tex_gray.shape[0]:
                    continue

                tpl_scaled = cv2.resize(tpl_rotated, (new_w, new_h))

                # Template matching
                result = cv2.matchTemplate(tex_gray, tpl_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > best_score:
                    best_score = max_val
                    best_scale = scale
                    best_rotation = rotation

                    # Early exit if very good match
                    if best_score >= 0.9:
                        return True, best_score, best_scale, best_rotation

        return best_score >= threshold, best_score, best_scale, best_rotation

    except Exception as e:
        PrettyPrint(f"OpenCV matching error: {str(e)}", "warn")
        return False, 0, 1.0, 0

# Shape-based matching (scale and rotation invariant) - fallback if no OpenCV
def extract_shape_silhouette(image_path, grid_size=12):
    """
    Extract a normalized silhouette from an image.
    Returns a set of (x, y) grid positions that are filled, normalized to grid_size.
    """
    try:
        img = bpy.data.images.load(image_path)
        pixels = img.pixels[:]
        w, h = img.size[0], img.size[1]
        bpy.data.images.remove(img)

        # Find bounding box of non-transparent pixels
        min_x, max_x = w, 0
        min_y, max_y = h, 0
        filled_pixels = []

        for y in range(h):
            for x in range(w):
                idx = (y * w + x) * 4
                r, g, b, a = pixels[idx], pixels[idx+1], pixels[idx+2], pixels[idx+3]
                # Consider pixel filled if not transparent and not pure black
                if a > 0.1 and (r > 0.1 or g > 0.1 or b > 0.1):
                    filled_pixels.append((x, y))
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

        if not filled_pixels or max_x <= min_x or max_y <= min_y:
            return set()

        # Normalize to grid
        shape_w = max_x - min_x + 1
        shape_h = max_y - min_y + 1

        grid = set()
        for x, y in filled_pixels:
            gx = int((x - min_x) / shape_w * grid_size)
            gy = int((y - min_y) / shape_h * grid_size)
            gx = min(gx, grid_size - 1)
            gy = min(gy, grid_size - 1)
            grid.add((gx, gy))

        return grid

    except Exception as e:
        PrettyPrint(f"Error extracting shape: {str(e)}", "warn")
        return set()

def rotate_shape_90(shape, grid_size=12):
    """Rotate shape 90 degrees clockwise."""
    return {(grid_size - 1 - y, x) for x, y in shape}

def get_all_rotations(shape, grid_size=12):
    """Get all 4 rotations of a shape."""
    rotations = [shape]
    current = shape
    for _ in range(3):
        current = rotate_shape_90(current, grid_size)
        rotations.append(current)
    return rotations

def shape_similarity(shape1, shape2, check_density=True):
    """
    Calculate similarity between two shapes.
    Uses Jaccard similarity AND density check to avoid matching
    large solid shapes that "contain" smaller shapes.
    """
    if not shape1 or not shape2:
        return 0

    # Jaccard similarity (intersection over union)
    intersection = len(shape1 & shape2)
    union = len(shape1 | shape2)
    jaccard = intersection / union if union > 0 else 0

    if not check_density:
        return jaccard

    # Density check: shapes should have similar number of filled cells
    # This prevents a large solid rectangle from matching a small arrow
    size1, size2 = len(shape1), len(shape2)
    size_ratio = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 0

    # Combined score: both Jaccard AND density must be good
    # Require density ratio > 0.5 (shapes within 2x size of each other)
    if size_ratio < 0.4:
        return jaccard * 0.3  # Heavily penalize size mismatch

    return jaccard * (0.5 + 0.5 * size_ratio)  # Boost score for similar sizes

def find_shape_in_texture(texture_path, template_shapes, grid_size=12, threshold=0.6, scales=[0.5, 0.75, 1.0, 1.5, 2.0]):
    """
    Search for a shape in a texture at multiple scales and rotations.
    template_shapes: list of rotated versions of the template shape
    Returns (found, best_score)
    """
    try:
        img = bpy.data.images.load(texture_path)
        pixels = img.pixels[:]
        tex_w, tex_h = img.size[0], img.size[1]
        bpy.data.images.remove(img)

        best_score = 0

        # Estimate template size from grid density
        template_size = int(grid_size * 3)  # Base search window

        for scale in scales:
            window_size = int(template_size * scale)
            if window_size < 8 or window_size > min(tex_w, tex_h):
                continue

            step = max(4, window_size // 3)

            for wy in range(0, tex_h - window_size, step):
                for wx in range(0, tex_w - window_size, step):
                    # Extract shape from this window
                    window_filled = set()
                    has_content = False

                    for ly in range(0, window_size, max(1, window_size // grid_size)):
                        for lx in range(0, window_size, max(1, window_size // grid_size)):
                            px, py = wx + lx, wy + ly
                            if px >= tex_w or py >= tex_h:
                                continue
                            idx = (py * tex_w + px) * 4
                            if idx + 3 >= len(pixels):
                                continue
                            r, g, b, a = pixels[idx], pixels[idx+1], pixels[idx+2], pixels[idx+3]
                            if a > 0.1 and (r > 0.1 or g > 0.1 or b > 0.1):
                                gx = int(lx / window_size * grid_size)
                                gy = int(ly / window_size * grid_size)
                                gx = min(gx, grid_size - 1)
                                gy = min(gy, grid_size - 1)
                                window_filled.add((gx, gy))
                                has_content = True

                    if not has_content or len(window_filled) < 5:
                        continue

                    # Compare against all rotations
                    for template_shape in template_shapes:
                        score = shape_similarity(window_filled, template_shape)
                        if score > best_score:
                            best_score = score
                            if best_score >= threshold:
                                return True, best_score

        return best_score >= threshold, best_score

    except Exception as e:
        PrettyPrint(f"Error in shape matching: {str(e)}", "warn")
        return False, 0

# Texture search/scan tool to find textures across archives
class TextureSearchOperator(Operator):
    bl_label = "Search Textures"
    bl_idname = "helldiver2.texture_search"
    bl_description = "Scan archives for textures and export them for visual inspection. Useful for finding specific textures like UI elements"

    directory: StringProperty(name="Output Directory", description="Directory to export textures to", subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    min_width: IntProperty(name="Min Width", description="Minimum texture width (0 = no minimum)", default=0, min=0)
    max_width: IntProperty(name="Max Width", description="Maximum texture width (0 = no maximum)", default=0, min=0)
    min_height: IntProperty(name="Min Height", description="Minimum texture height (0 = no minimum)", default=0, min=0)
    max_height: IntProperty(name="Max Height", description="Maximum texture height (0 = no maximum)", default=0, min=0)

    scan_all_archives: BoolProperty(name="Scan All Archives", description="Scan all archives in game folder (slow but thorough)", default=False)
    export_format: EnumProperty(
        name="Export Format",
        items=[
            ('PNG', 'PNG', 'Export as PNG (viewable)'),
            ('DDS', 'DDS', 'Export as DDS (original format)'),
        ],
        default='PNG'
    )
    generate_report: BoolProperty(name="Generate Report", description="Create a CSV report with texture metadata", default=True)

    # UI Atlas filtering
    filter_ui_atlas: BoolProperty(name="UI Atlas Filter", description="Only keep textures with black/transparent backgrounds (like UI atlases)", default=False)
    black_threshold: FloatProperty(name="Black/Transparent %", description="Minimum percentage of black/transparent pixels (0.0-1.0)", default=0.5, min=0.0, max=1.0)
    max_colors: IntProperty(name="Max Unique Colors", description="Maximum number of unique colors for UI atlas detection", default=100, min=1)

    # Template matching (color-based)
    use_template_match: BoolProperty(name="Color Match", description="Search for textures with similar colors to template", default=False)
    template_path: StringProperty(name="Template Image", description="Path to template image to search for", subtype='FILE_PATH')
    template_folder: StringProperty(name="Template Folder", description="Folder containing multiple template images to search for")
    use_template_folder: BoolProperty(name="Use Folder", description="Use a folder of templates instead of a single image", default=False)
    match_threshold: FloatProperty(name="Match Threshold", description="Minimum match quality (0.0-1.0)", default=0.8, min=0.0, max=1.0)

    # Shape matching (scale/rotation invariant)
    use_shape_match: BoolProperty(name="Shape Match", description="Search for similar shapes (works at any size/rotation)", default=False)
    shape_threshold: FloatProperty(name="Shape Threshold", description="Minimum shape similarity (0.0-1.0)", default=0.5, min=0.0, max=1.0)

    # Exact matching (perceptual hash - finds identical/near-identical textures)
    use_exact_match: BoolProperty(name="Exact Match", description="Find textures that are identical or near-identical to template (highest priority)", default=False)
    exact_threshold: FloatProperty(name="Exact Threshold", description="Minimum similarity for exact match (0.95+ for near-identical)", default=0.9, min=0.0, max=1.0)

    # Contains matching (template appears within texture)
    use_contains_match: BoolProperty(name="Contains Match", description="Find textures that contain the template image (for transparent overlays)", default=False)
    contains_threshold: FloatProperty(name="Contains Threshold", description="Minimum match quality for containment", default=0.7, min=0.0, max=1.0)

    # Resolution matching
    filter_same_resolution: BoolProperty(name="Same Resolution", description="Only check textures with same dimensions as template", default=False)
    prioritize_resolution: BoolProperty(name="Prioritize Resolution Match", description="Rank textures with matching resolution higher", default=True)

    # Parallel processing
    num_workers: IntProperty(name="Workers", description="Number of parallel workers (more = faster but uses more CPU/RAM)", default=8, min=1, max=32)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "scan_all_archives")
        row.prop(self, "num_workers")
        layout.prop(self, "export_format")
        layout.prop(self, "generate_report")

        layout.separator()
        layout.label(text="Dimension Filters (0 = no limit):")
        row = layout.row()
        row.prop(self, "min_width")
        row.prop(self, "max_width")
        row = layout.row()
        row.prop(self, "min_height")
        row.prop(self, "max_height")

        layout.separator()
        layout.label(text="UI Atlas Filter:")
        layout.prop(self, "filter_ui_atlas")
        if self.filter_ui_atlas:
            row = layout.row()
            row.prop(self, "black_threshold")
            row.prop(self, "max_colors")

        layout.separator()
        layout.label(text="Template Input:")
        row = layout.row()
        row.prop(self, "use_template_folder")
        if self.use_template_folder:
            layout.prop(self, "template_folder")
        else:
            layout.prop(self, "template_path")

        layout.separator()
        layout.label(text="Matching Modes (ranked by likelihood):")

        # Exact match - highest priority
        box = layout.box()
        box.label(text="1. Exact Match (Highest Priority)", icon='CHECKMARK')
        row = box.row()
        row.prop(self, "use_exact_match")
        if self.use_exact_match:
            row.prop(self, "exact_threshold")

        # Contains match - second priority
        box = layout.box()
        box.label(text="2. Contains Match (Template in Texture)", icon='PIVOT_BOUNDBOX')
        row = box.row()
        row.prop(self, "use_contains_match")
        if self.use_contains_match:
            row.prop(self, "contains_threshold")
            box.label(text="(For transparent overlays on backgrounds)", icon='INFO')

        # Resolution matching
        box = layout.box()
        box.label(text="3. Resolution Match", icon='TEXTURE')
        row = box.row()
        row.prop(self, "filter_same_resolution")
        row.prop(self, "prioritize_resolution")

        # Shape/Color matching - lower priority
        box = layout.box()
        box.label(text="4. Shape/Color Match", icon='IMAGE_DATA')
        row = box.row()
        row.prop(self, "use_shape_match")
        row.prop(self, "use_template_match")
        if self.use_shape_match:
            box.prop(self, "shape_threshold")
        if self.use_template_match:
            box.prop(self, "match_threshold")

    def execute(self, context):
        import time
        import shutil
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        start_time = time.time()

        # Initialize log file in output directory
        log_path = os.path.join(self.directory, "log.txt")
        SetLogFile(log_path)

        # Log all search parameters at the start
        PrettyPrint("=" * 60)
        PrettyPrint("TEXTURE SEARCH PARAMETERS")
        PrettyPrint("=" * 60)
        PrettyPrint(f"Output directory: {self.directory}")
        PrettyPrint(f"Export format: {self.export_format}")
        PrettyPrint(f"Generate report: {self.generate_report}")
        PrettyPrint(f"Scan all archives: {self.scan_all_archives}")
        PrettyPrint(f"Parallel workers: {self.num_workers}")
        PrettyPrint("")
        PrettyPrint("--- Dimension Filters ---")
        PrettyPrint(f"Min dimensions: {self.min_width}x{self.min_height}")
        PrettyPrint(f"Max dimensions: {self.max_width}x{self.max_height}")
        PrettyPrint("")
        PrettyPrint("--- Template Settings ---")
        PrettyPrint(f"Use template folder: {self.use_template_folder}")
        if self.use_template_folder:
            PrettyPrint(f"Template folder: {self.template_folder}")
        else:
            PrettyPrint(f"Template path: {self.template_path}")
        PrettyPrint("")
        PrettyPrint("--- Matching Modes ---")
        PrettyPrint(f"Exact match: {self.use_exact_match} (threshold: {self.exact_threshold:.0%})")
        PrettyPrint(f"Contains match: {self.use_contains_match} (threshold: {self.contains_threshold:.0%})")
        PrettyPrint(f"Color match: {self.use_template_match} (threshold: {self.match_threshold:.0%})")
        PrettyPrint(f"Shape match: {self.use_shape_match} (threshold: {self.shape_threshold:.0%})")
        PrettyPrint(f"Same resolution filter: {self.filter_same_resolution}")
        PrettyPrint(f"Prioritize resolution: {self.prioritize_resolution}")
        PrettyPrint("")
        PrettyPrint("--- UI Atlas Filter ---")
        PrettyPrint(f"Filter UI atlas: {self.filter_ui_atlas}")
        if self.filter_ui_atlas:
            PrettyPrint(f"Black/transparent threshold: {self.black_threshold:.0%}")
            PrettyPrint(f"Max unique colors: {self.max_colors}")
        PrettyPrint("=" * 60)
        PrettyPrint("")

        if not Global_TocManager.ActiveArchive and not self.scan_all_archives:
            PrettyPrint("ERROR: No archive loaded. Load an archive first or enable 'Scan All Archives'", "error")
            CloseLogFile()
            self.report({'ERROR'}, "No archive loaded. Load an archive first or enable 'Scan All Archives'")
            return {'CANCELLED'}

        # Check template path if any matching mode is enabled
        needs_template = self.use_template_match or self.use_shape_match or self.use_exact_match or self.use_contains_match or self.filter_same_resolution or self.prioritize_resolution

        # Collect template paths (single file or folder)
        template_paths = []
        if needs_template:
            if self.use_template_folder:
                if not self.template_folder or not os.path.isdir(self.template_folder):
                    PrettyPrint(f"ERROR: Template folder mode enabled but no valid folder specified", "error")
                    CloseLogFile()
                    self.report({'ERROR'}, "Template folder mode enabled but no valid folder specified")
                    return {'CANCELLED'}
                # Scan folder for image files
                valid_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tga', '.tiff', '.dds'}
                for filename in os.listdir(self.template_folder):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in valid_extensions:
                        template_paths.append(os.path.join(self.template_folder, filename))
                if not template_paths:
                    PrettyPrint(f"ERROR: No image files found in template folder: {self.template_folder}", "error")
                    CloseLogFile()
                    self.report({'ERROR'}, f"No image files found in template folder: {self.template_folder}")
                    return {'CANCELLED'}
                PrettyPrint(f"Found {len(template_paths)} template images in folder")
            else:
                if not self.template_path or not os.path.exists(self.template_path):
                    PrettyPrint(f"ERROR: Template matching enabled but no valid template image specified", "error")
                    CloseLogFile()
                    self.report({'ERROR'}, "Template matching enabled but no valid template image specified")
                    return {'CANCELLED'}
                template_paths = [self.template_path]

        # Pre-compute data for all templates
        templates_data = []  # List of dicts, one per template
        temp_folder = get_temp_folder()
        # Create dedicated subfolder for converted templates
        template_convert_folder = os.path.join(temp_folder, "texture_search_templates")
        if not os.path.exists(template_convert_folder):
            os.makedirs(template_convert_folder)
        converted_temps = []  # Track temp files to clean up later

        PrettyPrint(f"Processing {len(template_paths)} templates...")
        successful_conversions = 0
        failed_conversions = 0

        for tpl_idx, tpl_path in enumerate(template_paths):
            tpl_name = os.path.basename(tpl_path)
            tpl_ext = os.path.splitext(tpl_name)[1].lower()

            # Convert DDS templates to PNG for processing
            working_path = tpl_path
            if tpl_ext == '.dds':
                PrettyPrint(f"[{tpl_idx+1}/{len(template_paths)}] Converting DDS template '{tpl_name}'...")
                temp_png = os.path.join(template_convert_folder, f"tpl_{os.path.splitext(tpl_name)[0]}.png")
                result = subprocess.run([Global_texconvpath, "-y", "-o", template_convert_folder, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-alpha", tpl_path], capture_output=True)
                # texconv outputs with same base name
                expected_output = os.path.join(template_convert_folder, f"{os.path.splitext(tpl_name)[0]}.png")
                if os.path.exists(expected_output):
                    working_path = expected_output
                    converted_temps.append(expected_output)
                    successful_conversions += 1
                else:
                    failed_conversions += 1
                    stderr_msg = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else "No error message"
                    PrettyPrint(f"  FAILED: {tpl_name} - {stderr_msg}", "WARN")
                    continue

            tpl_data = {'path': working_path, 'name': tpl_name, 'original_path': tpl_path}

            # Get template dimensions for resolution filtering
            tpl_data['width'], tpl_data['height'] = get_template_dimensions(working_path)
            if tpl_data['width'] and tpl_data['height']:
                PrettyPrint(f"Template '{tpl_name}' dimensions: {tpl_data['width']}x{tpl_data['height']}")

            # Pre-compute template hash for exact matching
            tpl_data['hash'] = None
            tpl_data['histogram'] = None
            if self.use_exact_match:
                tpl_data['hash'] = compute_image_hash(working_path)
                if tpl_data['hash'] is not None:
                    PrettyPrint(f"Template '{tpl_name}' hash computed")
                if OPENCV_AVAILABLE:
                    tpl_data['histogram'] = compute_histogram(working_path)

            # Pre-extract template colors for color matching
            tpl_data['colors'] = {}
            if self.use_template_match:
                tpl_data['colors'] = extract_template_colors(working_path)
                PrettyPrint(f"Template '{tpl_name}' has {len(tpl_data['colors'])} unique color signatures")

            # Pre-extract shape silhouette and rotations for shape matching (fallback only)
            tpl_data['shapes'] = []
            if self.use_shape_match and not OPENCV_AVAILABLE:
                base_shape = extract_shape_silhouette(working_path)
                if base_shape:
                    tpl_data['shapes'] = get_all_rotations(base_shape)
                    PrettyPrint(f"Template '{tpl_name}' shape: {len(base_shape)} grid cells")

            templates_data.append(tpl_data)

        # Log template processing summary
        if self.use_template_folder:
            PrettyPrint(f"Template conversion summary: {successful_conversions} succeeded, {failed_conversions} failed, {len(templates_data)} ready for matching")
            if failed_conversions > 0:
                PrettyPrint(f"  Note: Failed templates will be skipped during search", "WARN")

        # For backwards compatibility, also set single-template variables (use first template)
        template_width, template_height = None, None
        template_hash = None
        template_histogram = None
        template_colors = {}
        template_shapes = []
        if templates_data:
            template_width = templates_data[0]['width']
            template_height = templates_data[0]['height']
            template_hash = templates_data[0]['hash']
            template_histogram = templates_data[0]['histogram']
            template_colors = templates_data[0]['colors']
            template_shapes = templates_data[0]['shapes']

        # Thread-safe counters
        lock = threading.Lock()
        counters = {
            'exported': 0, 'skipped_dims': 0, 'skipped_ui': 0,
            'skipped_color': 0, 'skipped_shape': 0, 'skipped_exact': 0,
            'skipped_contains': 0, 'skipped_resolution': 0,
            'errors': 0, 'processed': 0
        }
        report_data = []
        matches_found = []

        # Store settings for worker threads
        # Use global temp folder setting
        temp_folder = get_temp_folder()
        PrettyPrint(f"Using temp folder: {temp_folder}")
        settings = {
            'output_dir': self.directory,
            'temp_dir': temp_folder,
            'export_format': self.export_format,
            'filter_ui_atlas': self.filter_ui_atlas,
            'black_threshold': self.black_threshold,
            'max_colors': self.max_colors,
            'use_template_match': self.use_template_match,
            'template_colors': template_colors,
            'match_threshold': self.match_threshold,
            'use_shape_match': self.use_shape_match,
            'template_path': self.template_path,
            'template_shapes': template_shapes,
            'shape_threshold': self.shape_threshold,
            'generate_report': self.generate_report,
            # New matching options
            'use_exact_match': self.use_exact_match,
            'exact_threshold': self.exact_threshold,
            'template_hash': template_hash,
            'template_histogram': template_histogram,
            'use_contains_match': self.use_contains_match,
            'contains_threshold': self.contains_threshold,
            'filter_same_resolution': self.filter_same_resolution,
            'prioritize_resolution': self.prioritize_resolution,
            'template_width': template_width,
            'template_height': template_height,
            # Multi-template support
            'templates_data': templates_data,
        }

        def process_texture(task):
            """Worker function to process a single texture (thread-safe)"""
            archive_name, file_id, dds_data, width, height, tex_format = task

            try:
                templates = settings['templates_data']

                # Check resolution filter first (before any conversion - fast check)
                # Match if texture matches ANY template's resolution
                resolution_match = False
                if templates:
                    for tpl in templates:
                        if tpl['width'] and tpl['height']:
                            if width == tpl['width'] and height == tpl['height']:
                                resolution_match = True
                                break

                # If strict resolution filter is enabled and doesn't match ANY template, skip
                if settings['filter_same_resolution'] and not resolution_match:
                    return ('skipped_resolution', None)

                # Create unique temp files for this thread
                thread_id = threading.current_thread().ident
                tempdir = settings['temp_dir']
                dds_path = os.path.join(tempdir, f"tmp_{thread_id}_{file_id}.dds")
                temp_png = os.path.join(tempdir, f"tmp_{thread_id}_{file_id}.png")

                # Write DDS
                with open(dds_path, 'wb') as f:
                    f.write(dds_data)

                # Convert to PNG
                subprocess.run([Global_texconvpath, "-y", "-o", tempdir, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-alpha", dds_path], capture_output=True)

                # texconv outputs with same name as input but .png extension
                texconv_output = os.path.join(tempdir, f"tmp_{thread_id}_{file_id}.png")
                if not os.path.exists(texconv_output):
                    return ('error', None)
                temp_png = texconv_output

                if not os.path.exists(temp_png):
                    return ('error', None)

                # Apply UI atlas filter
                if settings['filter_ui_atlas']:
                    is_ui, _, _ = is_ui_atlas_texture_fast(temp_png, settings['black_threshold'], settings['max_colors'])
                    if not is_ui:
                        try: os.remove(temp_png)
                        except: pass
                        try: os.remove(dds_path)
                        except: pass
                        return ('skipped_ui', None)

                # Initialize all scores
                exact_score = 0.0
                mse_score = 0.0  # MSE validation score for exact matches
                contains_score = 0.0
                match_score = 0.0
                shape_score = 0.0
                match_type = "none"
                matched_template = None  # Track which template matched

                # Track which filters passed
                any_match_required = (settings['use_exact_match'] or settings['use_contains_match'] or
                                      settings['use_template_match'] or settings['use_shape_match'])

                # 1. EXACT MATCH - Highest priority (perceptual hash comparison)
                # Check against ALL templates, match if ANY matches
                if settings['use_exact_match']:
                    # Skip textures that are too small - they produce unreliable hashes
                    # Minimum 32x32 to have meaningful content for hashing
                    min_hash_size = 32
                    if width < min_hash_size or height < min_hash_size:
                        # Too small for reliable exact matching
                        if any_match_required and not (settings['use_contains_match'] or
                                                       settings['use_template_match'] or settings['use_shape_match']):
                            try: os.remove(temp_png)
                            except: pass
                            try: os.remove(dds_path)
                            except: pass
                            return ('skipped_exact', None)
                    else:
                        texture_hash = compute_image_hash(temp_png)
                        if texture_hash is not None:
                            for tpl in templates:
                                if tpl['hash'] is not None:
                                    # Exact match requires same resolution
                                    if tpl.get('width') and tpl.get('height'):
                                        if width != tpl['width'] or height != tpl['height']:
                                            continue  # Skip templates with different resolution
                                    # Only use perceptual hash - histogram can cause false positives
                                    score = hash_similarity(tpl['hash'], texture_hash)
                                    if score >= settings['exact_threshold'] and score > exact_score:
                                        # Validate with MSE to filter false positives
                                        # Hash similarity can match different images with similar structure
                                        mse_sim = compute_mse_similarity(temp_png, tpl['path'])
                                        if mse_sim >= 0.92:  # Require 92% SSIM+contrast similarity
                                            exact_score = score
                                            mse_score = mse_sim
                                            matched_template = tpl['name']

                    if exact_score >= settings['exact_threshold']:
                        match_type = "exact"
                    elif any_match_required and not (settings['use_contains_match'] or
                                                     settings['use_template_match'] or settings['use_shape_match']):
                        # Only exact match enabled and it failed
                        try: os.remove(temp_png)
                        except: pass
                        try: os.remove(dds_path)
                        except: pass
                        return ('skipped_exact', None)

                # 2. CONTAINS MATCH - Check if ANY template is contained within texture
                if settings['use_contains_match'] and match_type != "exact":
                    for tpl in templates:
                        found, score, _ = find_template_contained(temp_png, tpl['path'],
                                                                  threshold=settings['contains_threshold'])
                        if found and score > contains_score:
                            contains_score = score
                            matched_template = tpl['name']
                            match_type = "contains"

                    if match_type != "contains" and any_match_required and not (settings['use_template_match'] or settings['use_shape_match']):
                        # Only contains match enabled (besides exact which may have failed)
                        if not settings['use_exact_match'] or exact_score < settings['exact_threshold']:
                            try: os.remove(temp_png)
                            except: pass
                            try: os.remove(dds_path)
                            except: pass
                            return ('skipped_contains', None)

                # 3. COLOR MATCH - Check against ALL templates
                if settings['use_template_match'] and match_type not in ["exact", "contains"]:
                    for tpl in templates:
                        if tpl['colors']:
                            found, score = match_texture_to_template(temp_png, tpl['colors'],
                                                                      settings['match_threshold'])
                            if found and score > match_score:
                                match_score = score
                                matched_template = tpl['name']
                                match_type = "color"

                    if match_type != "color" and any_match_required and not settings['use_shape_match']:
                        try: os.remove(temp_png)
                        except: pass
                        try: os.remove(dds_path)
                        except: pass
                        return ('skipped_color', None)

                # 4. SHAPE MATCH - Check against ALL templates
                if settings['use_shape_match'] and match_type not in ["exact", "contains", "color"]:
                    for tpl in templates:
                        if OPENCV_AVAILABLE and cv2 is not None:
                            found, score, _, _ = find_template_opencv(temp_png, tpl['path'],
                                                                      threshold=settings['shape_threshold'],
                                                                      check_rotations=True)
                        else:
                            if tpl['shapes']:
                                found, score = find_shape_in_texture(temp_png, tpl['shapes'],
                                                                      threshold=settings['shape_threshold'])
                            else:
                                found, score = False, 0
                        if found and score > shape_score:
                            shape_score = score
                            matched_template = tpl['name']
                            match_type = "shape"

                    if match_type != "shape" and any_match_required:
                        try: os.remove(temp_png)
                        except: pass
                        try: os.remove(dds_path)
                        except: pass
                        return ('skipped_shape', None)

                # If no matching modes enabled but we got here, it's a general export
                if not any_match_required:
                    match_type = "export"

                # If all enabled filters failed, skip
                if any_match_required and match_type == "none":
                    try: os.remove(temp_png)
                    except: pass
                    try: os.remove(dds_path)
                    except: pass
                    return ('skipped_shape', None)

                # Compute composite ranking score (higher = better match)
                # Priority: exact > contains > resolution > color > shape
                rank_score = 0.0
                if match_type == "exact":
                    rank_score = 1000.0 + exact_score * 100  # 1000-1100
                elif match_type == "contains":
                    rank_score = 800.0 + contains_score * 100  # 800-900
                elif resolution_match:
                    rank_score = 600.0 + max(match_score, shape_score) * 100  # 600-700
                elif match_type == "color":
                    rank_score = 400.0 + match_score * 100  # 400-500
                elif match_type == "shape":
                    rank_score = 200.0 + shape_score * 100  # 200-300
                else:
                    rank_score = 100.0  # General export

                # Boost score if resolution matches (when prioritize_resolution is enabled)
                if settings['prioritize_resolution'] and resolution_match:
                    rank_score += 50.0

                # MATCH! Export it
                filename = f"{archive_name}_{file_id}"
                if settings['export_format'] == 'PNG':
                    png_output = os.path.join(settings['output_dir'], f"{filename}.png")
                    shutil.copy2(temp_png, png_output)
                else:
                    dds_output = os.path.join(settings['output_dir'], f"{filename}.dds")
                    shutil.copy2(dds_path, dds_output)

                # Cleanup
                try: os.remove(temp_png)
                except: pass
                try: os.remove(dds_path)
                except: pass

                result_data = {
                    'archive': archive_name,
                    'file_id': str(file_id),
                    'hex_id': hex(file_id),
                    'width': width,
                    'height': height,
                    'format': tex_format,
                    'filename': filename,
                    'match_type': match_type,
                    'matched_template': matched_template or '',
                    'exact_score': exact_score,
                    'mse_score': mse_score,
                    'contains_score': contains_score,
                    'match_score': match_score,
                    'shape_score': shape_score,
                    'resolution_match': resolution_match,
                    'rank_score': rank_score
                }
                return ('match', result_data)

            except Exception as e:
                return ('error', str(e))

        # Determine which archives to scan
        archives_to_scan = []
        if self.scan_all_archives:
            if len(Global_TocManager.SearchArchives) > 0:
                archives_to_scan = Global_TocManager.SearchArchives
            else:
                PrettyPrint("ERROR: No search archives available. Load at least one archive first to populate the search index", "error")
                CloseLogFile()
                self.report({'ERROR'}, "No search archives available. Load at least one archive first to populate the search index")
                return {'CANCELLED'}
        else:
            archives_to_scan = Global_TocManager.LoadedArchives

        total_archives = len(archives_to_scan)
        PrettyPrint(f"=== TEXTURE SEARCH STARTED (Parallel: {self.num_workers} workers) ===")
        PrettyPrint(f"Archives to scan: {total_archives}")
        PrettyPrint(f"Filters: Dimensions={self.min_width}x{self.min_height} to {self.max_width}x{self.max_height}")

        # Build match modes string
        modes = []
        if self.use_exact_match:
            modes.append(f"Exact(>={self.exact_threshold:.0%})")
        if self.use_contains_match:
            modes.append(f"Contains(>={self.contains_threshold:.0%})")
        if self.filter_same_resolution:
            modes.append("SameResolution(strict)")
        elif self.prioritize_resolution:
            modes.append("Resolution(prioritize)")
        if self.use_template_match:
            modes.append(f"Color(>={self.match_threshold:.0%})")
        if self.use_shape_match:
            modes.append(f"Shape(>={self.shape_threshold:.0%})")
        if self.filter_ui_atlas:
            modes.append("UIAtlas")

        if modes:
            PrettyPrint(f"Match modes (priority order): {' > '.join(modes)}")
        else:
            PrettyPrint(f"No matching modes enabled - exporting all textures")

        # Log template information
        if templates_data:
            if self.use_template_folder:
                PrettyPrint(f"Template folder: {self.template_folder}")
                PrettyPrint(f"Templates loaded: {len(templates_data)}")
                for tpl in templates_data:
                    dims = f"{tpl['width']}x{tpl['height']}" if tpl.get('width') and tpl.get('height') else "unknown dims"
                    PrettyPrint(f"  - {tpl['name']} ({dims})")
            else:
                PrettyPrint(f"Template: {self.template_path} ({template_width}x{template_height})")

        if self.use_shape_match or self.use_contains_match or self.use_exact_match:
            opencv_status = "OpenCV (fast/accurate)" if (OPENCV_AVAILABLE and cv2 is not None) else "Fallback (slower)"
            PrettyPrint(f"Matching engine: {opencv_status}")

        # Process archives in batches to avoid memory explosion
        import gc
        BATCH_SIZE = 50  # Process 50 archives at a time, then free memory

        total_processed = 0
        PrettyPrint(f"Processing {total_archives} archives in batches of {BATCH_SIZE}...")

        for batch_start in range(0, total_archives, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_archives)
            batch_archives = archives_to_scan[batch_start:batch_end]

            PrettyPrint(f"=== Batch {batch_start//BATCH_SIZE + 1}: Archives {batch_start+1}-{batch_end} of {total_archives} ===")

            # Collect tasks for this batch only
            batch_tasks = []

            for arch_idx, archive in enumerate(batch_archives):
                archive_name = Path(archive.Path).stem if hasattr(archive, 'Path') else "unknown"

                # Get texture entries from this archive
                tex_file_ids = []
                loaded_archive = None

                if hasattr(archive, 'TocDict'):
                    # Already a full archive with entries
                    loaded_archive = archive
                    tex_entries = list(archive.TocDict.get(TexID, {}).values())
                    for entry in tex_entries:
                        tex_file_ids.append(entry.FileID)
                elif hasattr(archive, 'TocEntries'):
                    # SearchToc - need to load the archive ONCE
                    tex_file_ids = archive.TocEntries.get(TexID, [])
                    if len(tex_file_ids) > 0:
                        try:
                            loaded_archive = Global_TocManager.LoadArchive(archive.Path, SetActive=False)
                        except Exception as e:
                            PrettyPrint(f"  Skipping archive {archive_name} - load error", 'WARN')
                            counters['errors'] += 1
                            continue

                if len(tex_file_ids) == 0 or loaded_archive is None:
                    continue

                for file_id in tex_file_ids:
                    try:
                        entry = loaded_archive.GetEntry(file_id, TexID)
                        if entry is None:
                            continue

                        if not entry.IsLoaded:
                            entry.Load(False, False)

                        if entry.LoadedData is None:
                            counters['errors'] += 1
                            continue

                        tex = entry.LoadedData
                        width = tex.Width
                        height = tex.Height
                        tex_format = tex.Format

                        # Apply dimension filters (fast, do it here)
                        if self.min_width > 0 and width < self.min_width:
                            counters['skipped_dims'] += 1
                            continue
                        if self.max_width > 0 and width > self.max_width:
                            counters['skipped_dims'] += 1
                            continue
                        if self.min_height > 0 and height < self.min_height:
                            counters['skipped_dims'] += 1
                            continue
                        if self.max_height > 0 and height > self.max_height:
                            counters['skipped_dims'] += 1
                            continue

                        # Get DDS data for parallel processing
                        dds_data = tex.ToDDS()
                        batch_tasks.append((archive_name, file_id, dds_data, width, height, tex_format))
                        counters['processed'] += 1

                    except Exception as e:
                        counters['errors'] += 1

            # Process this batch
            if len(batch_tasks) > 0:
                archive_pct = (batch_end / total_archives) * 100
                PrettyPrint(f"  Processing {len(batch_tasks)} textures... ({archive_pct:.0f}% of archives)")

                batch_total = len(batch_tasks)
                with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                    futures = {executor.submit(process_texture, task): task for task in batch_tasks}

                    batch_processed = 0
                    for future in as_completed(futures):
                        total_processed += 1
                        batch_processed += 1
                        result_type, result_data = future.result()

                        # Log progress every 50 textures or at completion
                        if batch_processed % 50 == 0 or batch_processed == batch_total:
                            pct = (batch_processed / batch_total) * 100
                            PrettyPrint(f"    {batch_processed}/{batch_total} ({pct:.0f}%) - Matches: {counters['exported']}")

                        with lock:
                            if result_type == 'match':
                                counters['exported'] += 1
                                matches_found.append(result_data)
                                # Build score info string based on match type
                                match_type = result_data.get('match_type', 'unknown')
                                score_info = f" [{match_type.upper()}]"
                                if result_data.get('resolution_match'):
                                    score_info += " [RES]"
                                if result_data.get('exact_score', 0) > 0:
                                    score_info += f" exact={result_data['exact_score']:.2f}"
                                if result_data.get('mse_score', 0) > 0:
                                    score_info += f" mse={result_data['mse_score']:.2f}"
                                if result_data.get('contains_score', 0) > 0:
                                    score_info += f" contains={result_data['contains_score']:.2f}"
                                if result_data.get('match_score', 0) > 0:
                                    score_info += f" color={result_data['match_score']:.2f}"
                                if result_data.get('shape_score', 0) > 0:
                                    score_info += f" shape={result_data['shape_score']:.2f}"
                                # Include matched template name for debugging
                                tpl_info = ""
                                if result_data.get('matched_template'):
                                    tpl_info = f" tpl={result_data['matched_template']}"
                                PrettyPrint(f"  MATCH: {result_data['file_id']} ({result_data['width']}x{result_data['height']}){score_info}{tpl_info}")
                            elif result_type == 'skipped_ui':
                                counters['skipped_ui'] += 1
                            elif result_type == 'skipped_color':
                                counters['skipped_color'] += 1
                            elif result_type == 'skipped_shape':
                                counters['skipped_shape'] += 1
                            elif result_type == 'skipped_exact':
                                counters['skipped_exact'] += 1
                            elif result_type == 'skipped_contains':
                                counters['skipped_contains'] += 1
                            elif result_type == 'skipped_resolution':
                                counters['skipped_resolution'] += 1
                            elif result_type == 'error':
                                counters['errors'] += 1

            # Free memory after each batch - unload archives loaded during this batch
            del batch_tasks
            # Clear loaded archives to free memory (we're just searching, not modifying)
            archives_to_keep = []  # Keep none - we're only searching
            Global_TocManager.LoadedArchives = archives_to_keep
            Global_TocManager.ActiveArchive = None
            gc.collect()
            PrettyPrint(f"  Batch complete. Total matches so far: {counters['exported']}")

        # Write CSV report - SORTED BY LIKELIHOOD (rank_score)
        if self.generate_report and len(matches_found) > 0:
            # Sort matches by rank_score (highest first = most likely match)
            matches_found.sort(key=lambda x: x.get('rank_score', 0), reverse=True)

            report_path = os.path.join(self.directory, "texture_search_report.csv")
            with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
                import csv
                # Always include base fields + ranking info
                fieldnames = ['rank', 'match_type', 'matched_template', 'rank_score', 'archive', 'file_id', 'hex_id',
                              'width', 'height', 'resolution_match', 'format', 'filename']
                # Add score columns based on enabled modes
                if self.use_exact_match:
                    fieldnames.append('exact_score')
                    fieldnames.append('mse_score')
                if self.use_contains_match:
                    fieldnames.append('contains_score')
                if self.use_template_match:
                    fieldnames.append('color_score')
                if self.use_shape_match:
                    fieldnames.append('shape_score')

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()

                for idx, row in enumerate(matches_found, 1):
                    # Add rank number
                    row['rank'] = idx
                    # Format scores for display
                    row['rank_score'] = f"{row.get('rank_score', 0):.1f}"
                    row['resolution_match'] = "YES" if row.get('resolution_match') else "no"
                    if self.use_exact_match:
                        row['exact_score'] = f"{row.get('exact_score', 0):.3f}"
                        row['mse_score'] = f"{row.get('mse_score', 0):.3f}"
                    if self.use_contains_match:
                        row['contains_score'] = f"{row.get('contains_score', 0):.3f}"
                    if self.use_template_match:
                        row['color_score'] = f"{row.get('match_score', 0):.3f}"
                    if self.use_shape_match:
                        row['shape_score'] = f"{row.get('shape_score', 0):.3f}"
                    writer.writerow(row)

            PrettyPrint(f"Report written to: {report_path}")
            PrettyPrint(f"Results sorted by likelihood - check rank #1 first!")

        elapsed = time.time() - start_time
        PrettyPrint(f"=== TEXTURE SEARCH COMPLETE ===")
        PrettyPrint(f"Time: {elapsed:.1f}s | Processed: {counters['processed']} | Exported: {counters['exported']}")
        skip_info = f"Skipped - Dims: {counters['skipped_dims']} | UI: {counters['skipped_ui']}"
        if self.use_exact_match:
            skip_info += f" | Exact: {counters['skipped_exact']}"
        if self.use_contains_match:
            skip_info += f" | Contains: {counters['skipped_contains']}"
        if self.filter_same_resolution:
            skip_info += f" | Resolution: {counters['skipped_resolution']}"
        skip_info += f" | Color: {counters['skipped_color']} | Shape: {counters['skipped_shape']} | Errors: {counters['errors']}"
        PrettyPrint(skip_info)

        # Cleanup converted DDS template temp files
        for temp_file in converted_temps:
            try:
                os.remove(temp_file)
            except:
                pass
        # Try to remove the template folder if empty
        try:
            os.rmdir(template_convert_folder)
        except:
            pass  # Folder not empty or doesn't exist

        summary = f"Exported {counters['exported']} textures in {elapsed:.1f}s"
        self.report({'INFO'}, summary)

        # Close log file
        PrettyPrint(f"Log saved to: {log_path}")
        CloseLogFile()

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# Mesh search tool to find meshes across archives by polygon indices fingerprint
class MeshSearchOperator(Operator):
    bl_label = "Search Mesh"
    bl_idname = "helldiver2.mesh_search"
    bl_description = "Search archives for meshes matching the selected Blender object (using polygon indices as fingerprint)"

    scan_all_archives: BoolProperty(name="Scan All Archives", description="Scan all archives in game folder", default=False)
    match_threshold: FloatProperty(name="Match Threshold", description="Minimum percentage of matching polygons (0.0-1.0)", default=0.95, min=0.0, max=1.0)
    num_workers: IntProperty(name="Workers", description="Number of parallel workers", default=8, min=1, max=32)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "scan_all_archives")
        row.prop(self, "num_workers")
        layout.prop(self, "match_threshold")

        layout.separator()
        layout.label(text="Selected Object Info:")
        obj = context.active_object
        if obj and obj.type == 'MESH':
            mesh = obj.data
            layout.label(text=f"  Name: {obj.name}")
            layout.label(text=f"  Vertices: {len(mesh.vertices)}")
            layout.label(text=f"  Polygons: {len(mesh.polygons)}")
        else:
            layout.label(text="  No mesh selected!", icon='ERROR')

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        import time
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        start_time = time.time()

        if not Global_TocManager.ActiveArchive and not self.scan_all_archives:
            self.report({'ERROR'}, "No archive loaded. Load an archive first or enable 'Scan All Archives'")
            return {'CANCELLED'}

        # Get selected mesh and extract polygon indices fingerprint
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        mesh = obj.data
        target_polys = tuple(tuple(p.vertices) for p in mesh.polygons)
        target_poly_set = set(target_polys)
        target_vert_count = len(mesh.vertices)
        target_poly_count = len(mesh.polygons)

        PrettyPrint(f"=== MESH SEARCH STARTED ===")
        PrettyPrint(f"Target mesh: {obj.name}")
        PrettyPrint(f"Target vertices: {target_vert_count}, polygons: {target_poly_count}")
        PrettyPrint(f"Match threshold: {self.match_threshold:.0%}")

        # Thread-safe storage
        lock = threading.Lock()
        matches_found = []
        counters = {'processed': 0, 'errors': 0, 'units_checked': 0}

        def compute_match_score(unit_polys):
            """Compute percentage of matching polygons"""
            if len(unit_polys) != target_poly_count:
                return 0.0
            unit_poly_set = set(unit_polys)
            matching = len(target_poly_set & unit_poly_set)
            return matching / target_poly_count if target_poly_count > 0 else 0.0

        def process_unit(task):
            """Worker function to check a single unit mesh"""
            archive_name, file_id, entry = task
            try:
                # Load without creating Blender objects
                if not entry.IsLoaded:
                    entry.Load(Reload=False, MakeBlendObject=False, LoadMaterialSlotNames=False)

                if entry.LoadedData is None:
                    return ('error', None)

                stingray_mesh = entry.LoadedData
                results = []

                # Check each RawMesh in the unit
                for mesh_idx, raw_mesh in enumerate(stingray_mesh.RawMeshes):
                    # Quick filter: vertex count must match
                    vert_count = len(raw_mesh.VertexPositions)
                    poly_count = len(raw_mesh.Indices)

                    if vert_count != target_vert_count or poly_count != target_poly_count:
                        continue

                    # Extract polygon indices
                    unit_polys = tuple(tuple(idx) for idx in raw_mesh.Indices)

                    # Compute match score
                    score = compute_match_score(unit_polys)

                    if score >= self.match_threshold:
                        results.append({
                            'archive': archive_name,
                            'file_id': file_id,
                            'file_id_hex': hex(file_id),
                            'mesh_index': mesh_idx,
                            'lod_index': raw_mesh.LodIndex,
                            'score': score,
                            'vert_count': vert_count,
                            'poly_count': poly_count,
                        })

                return ('matches', results)

            except Exception as e:
                return ('error', str(e))

        # Determine which archives to scan
        archives_to_scan = []
        if self.scan_all_archives:
            if len(Global_TocManager.SearchArchives) > 0:
                archives_to_scan = Global_TocManager.SearchArchives
            else:
                self.report({'ERROR'}, "No search archives available. Load at least one archive first")
                return {'CANCELLED'}
        else:
            archives_to_scan = Global_TocManager.LoadedArchives

        total_archives = len(archives_to_scan)
        PrettyPrint(f"Archives to scan: {total_archives}")

        # Collect all unit tasks
        all_tasks = []

        for archive in archives_to_scan:
            archive_name = Path(archive.Path).stem if hasattr(archive, 'Path') else "unknown"

            unit_file_ids = []
            loaded_archive = None

            if hasattr(archive, 'TocDict'):
                loaded_archive = archive
                unit_entries = list(archive.TocDict.get(UnitID, {}).values())
                for entry in unit_entries:
                    unit_file_ids.append(entry.FileID)
            elif hasattr(archive, 'TocEntries'):
                unit_file_ids = archive.TocEntries.get(UnitID, [])
                if len(unit_file_ids) > 0:
                    try:
                        loaded_archive = Global_TocManager.LoadArchive(archive.Path, SetActive=False)
                    except Exception as e:
                        PrettyPrint(f"  Skipping archive {archive_name} - load error", 'WARN')
                        counters['errors'] += 1
                        continue

            if len(unit_file_ids) == 0 or loaded_archive is None:
                continue

            for file_id in unit_file_ids:
                try:
                    entry = loaded_archive.GetEntry(file_id, UnitID)
                    if entry is not None:
                        all_tasks.append((archive_name, file_id, entry))
                except:
                    counters['errors'] += 1

        PrettyPrint(f"Units to check: {len(all_tasks)}")

        # Process units in parallel
        if len(all_tasks) > 0:
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {executor.submit(process_unit, task): task for task in all_tasks}

                for future in as_completed(futures):
                    counters['units_checked'] += 1

                    if counters['units_checked'] % 100 == 0:
                        PrettyPrint(f"  Checked {counters['units_checked']}/{len(all_tasks)} units...")

                    result_type, result_data = future.result()

                    if result_type == 'matches' and result_data:
                        with lock:
                            matches_found.extend(result_data)
                    elif result_type == 'error':
                        counters['errors'] += 1

        # Sort matches by score
        matches_found.sort(key=lambda x: x['score'], reverse=True)

        # Report results
        elapsed = time.time() - start_time
        PrettyPrint(f"=== MESH SEARCH COMPLETE ===")
        PrettyPrint(f"Time: {elapsed:.1f}s | Units checked: {counters['units_checked']} | Errors: {counters['errors']}")
        PrettyPrint(f"Matches found: {len(matches_found)}")

        if len(matches_found) > 0:
            PrettyPrint(f"\n=== TOP MATCHES ===")
            for i, match in enumerate(matches_found[:20]):
                friendly_name = ""
                for hash_entry in Global_ArchiveHashes:
                    if hash_entry[0] == match['file_id_hex']:
                        friendly_name = f" ({hash_entry[1]})"
                        break
                PrettyPrint(f"  #{i+1}: {match['file_id_hex']}{friendly_name}")
                PrettyPrint(f"       Archive: {match['archive']}, Mesh #{match['mesh_index']}, LOD: {match['lod_index']}")
                PrettyPrint(f"       Score: {match['score']:.1%}, Verts: {match['vert_count']}, Polys: {match['poly_count']}")

            self.report({'INFO'}, f"Found {len(matches_found)} matching meshes. Check console for details.")
        else:
            self.report({'WARNING'}, f"No matching meshes found (checked {counters['units_checked']} units)")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

# import texture from archive button
class SaveTextureFromDDSOperator(Operator, ImportHelper):
    bl_label = "Import DDS"
    bl_idname = "helldiver2.texture_savefromdds"
    bl_description = "Override Current Texture with a Selected DDS File"

    filter_glob: StringProperty(default='*.dds', options={'HIDDEN'})
    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            SaveImageDDS(self.filepath, EntryID)
        
        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()

        return{'FINISHED'}


class SaveTextureFromPNGOperator(Operator, ImportHelper):
    bl_label = "Import PNG"
    bl_idname = "helldiver2.texture_savefrompng"
    bl_description = "Override Current Texture with a Selected PNG File"

    filter_glob: StringProperty(default='*.png', options={'HIDDEN'})
    object_id: StringProperty(options={"HIDDEN"})
    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            SaveImagePNG(self.filepath, EntryID)
        
        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()

        return{'FINISHED'}

def SaveImagePNG(filepath, object_id):
    Entry = Global_TocManager.GetEntry(int(object_id), TexID)
    if Entry != None:
        if len(filepath) > 1:
            # get texture data
            Entry.Load()
            StingrayTex = Entry.LoadedData
            tempdir = get_temp_folder()
            PrettyPrint(filepath)
            PrettyPrint(StingrayTex.Format)
            subprocess.run([Global_texconvpath, "-y", "-o", tempdir, "-ft", "dds", "-dx10", "-f", StingrayTex.Format, "-sepalpha", "-alpha", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            fileName = os.path.basename(filepath).replace(".png", ".dds")
            dds_path = f"{tempdir}/{fileName}"
            PrettyPrint(dds_path)
            if not os.path.exists(dds_path):
                raise Exception(f"Failed to convert to dds texture for: {dds_path}")
            with open(dds_path, 'r+b') as f:
                StingrayTex.FromDDS(f.read())
            Toc = MemoryStream(IOMode="write")
            Gpu = MemoryStream(IOMode="write")
            Stream = MemoryStream(IOMode="write")
            StingrayTex.Serialize(Toc, Gpu, Stream)
            # add texture to entry
            Entry.SetData(Toc.Data, Gpu.Data, Stream.Data, False)

            Global_TocManager.Save(int(object_id), TexID)

def SaveImageDDS(filepath, object_id):
    Entry = Global_TocManager.GetEntry(int(object_id), TexID)
    if Entry != None:
        if len(filepath) > 1:
            PrettyPrint(f"Saving image DDS: {filepath} to ID: {object_id}")
            # get texture data
            Entry.Load()
            StingrayTex = Entry.LoadedData
            with open(filepath, 'r+b') as f:
                StingrayTex.FromDDS(f.read())
            Toc = MemoryStream(IOMode="write")
            Gpu = MemoryStream(IOMode="write")
            Stream = MemoryStream(IOMode="write")
            StingrayTex.Serialize(Toc, Gpu, Stream)
            # add texture to entry
            Entry.SetData(Toc.Data, Gpu.Data, Stream.Data, False)

            Global_TocManager.Save(int(object_id), TexID)

# Batch opacity patching tool for texture search results
class BatchOpacityPatchOperator(Operator):
    bl_label = "Batch Patch Opacity"
    bl_idname = "helldiver2.texture_batch_opacity"
    bl_description = "Modify opacity of all textures from a Texture Search output folder"

    directory: StringProperty(name="Input Directory", description="Directory containing texture files named {archive}_{file_id}.png/dds", subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    opacity: FloatProperty(
        name="Opacity",
        description="Target opacity (0.0 = fully transparent, 1.0 = fully opaque)",
        default=0.25,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )

    # Modal state variables
    _timer = None
    _texture_list = None  # List of (archive_hex, file_id, format) tuples
    _texture_index = 0
    _processed = 0
    _failed = 0
    _total = 0
    _tempdir = None
    _current_archive = None
    _opacity_value = 0.25
    _start_time = 0

    def modal(self, context, event):
        if event.type in {'ESC'}:
            self.finish(context, cancelled=True)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # Process one texture per timer tick
            if self._texture_index >= len(self._texture_list):
                self.finish(context, cancelled=False)
                return {'FINISHED'}

            # Get current texture info
            archive_hex, file_id, tex_format = self._texture_list[self._texture_index]
            self._texture_index += 1

            # Update status
            progress_pct = int((self._texture_index / self._total) * 100)
            context.workspace.status_text_set(f"Batch Opacity: {self._texture_index}/{self._total} ({progress_pct}%) - Press ESC to cancel")

            # Load archive if different from current
            if archive_hex != self._current_archive:
                archive_path = Global_gamepath + archive_hex
                try:
                    Global_TocManager.LoadArchive(archive_path, SetActive=False)
                    self._current_archive = archive_hex
                except Exception as e:
                    PrettyPrint(f"Failed to load archive {archive_hex}: {str(e)}", 'ERROR')
                    self._failed += 1
                    return {'PASS_THROUGH'}

            # Process the texture
            try:
                self.process_texture(file_id, tex_format)
                self._processed += 1
                PrettyPrint(f"Processed texture {file_id} ({self._processed}/{self._total})")
            except Exception as e:
                PrettyPrint(f"Error processing texture {file_id}: {str(e)}", 'ERROR')
                self._failed += 1

            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def process_texture(self, file_id, tex_format):
        """Process a single texture - modify its opacity and save to patch."""
        # Get the entry
        Entry = Global_TocManager.GetEntry(file_id, TexID)
        if Entry is None:
            raise Exception(f"Could not find texture entry {file_id}")

        # Load the texture
        Entry.Load()
        StingrayTex = Entry.LoadedData

        # Export to DDS then convert to PNG for processing
        dds_path = f"{self._tempdir}/opacity_temp_{file_id}.dds"
        png_path = f"{self._tempdir}/opacity_temp_{file_id}.png"
        modified_png = f"{self._tempdir}/opacity_modified_{file_id}.png"

        # Write DDS
        with open(dds_path, 'w+b') as f:
            f.write(StingrayTex.ToDDS())

        # Convert to PNG for editing
        subprocess.run([Global_texconvpath, "-y", "-o", self._tempdir, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-sepalpha", "-alpha", dds_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if not os.path.exists(png_path):
            raise Exception(f"Failed to convert texture {file_id} to PNG")

        # Modify opacity using Blender's image API
        img = bpy.data.images.load(png_path)
        pixels = list(img.pixels)  # Get a mutable copy

        # Check if this is a grayscale/no-alpha format (BC4, BC5, R8, etc.)
        tex_format = StingrayTex.Format
        is_grayscale_format = any(f in tex_format for f in ["BC4", "BC5", "R8_", "R16_", "R32_"])

        opacity = self._opacity_value
        if is_grayscale_format:
            # For grayscale formats, modify RGB values since there's no real alpha channel
            for i in range(0, len(pixels), 4):
                pixels[i] = pixels[i] * opacity      # R
                pixels[i+1] = pixels[i+1] * opacity  # G
                pixels[i+2] = pixels[i+2] * opacity  # B
        else:
            # For formats with alpha, modify alpha channel (every 4th value starting at index 3)
            for i in range(3, len(pixels), 4):
                pixels[i] = pixels[i] * opacity

        img.pixels = pixels
        img.filepath_raw = modified_png
        img.file_format = 'PNG'
        img.save()
        bpy.data.images.remove(img)

        # Convert back to DDS with original format
        subprocess.run([Global_texconvpath, "-y", "-o", self._tempdir, "-ft", "dds", "-dx10", "-f", StingrayTex.Format, "-sepalpha", "-alpha", modified_png],
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        # The output will have the same base name as input
        expected_dds = f"{self._tempdir}/opacity_modified_{file_id}.dds"
        if not os.path.exists(expected_dds):
            raise Exception(f"Failed to convert modified texture {file_id} back to DDS")

        # Load the modified DDS back into the entry
        with open(expected_dds, 'r+b') as f:
            StingrayTex.FromDDS(f.read())

        # Serialize and save
        Toc = MemoryStream(IOMode="write")
        Gpu = MemoryStream(IOMode="write")
        Stream = MemoryStream(IOMode="write")
        StingrayTex.Serialize(Toc, Gpu, Stream)
        Entry.SetData(Toc.Data, Gpu.Data, Stream.Data, False)

        Global_TocManager.Save(file_id, TexID)

        # Cleanup temp files
        for temp_file in [dds_path, png_path, modified_png, expected_dds]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    def finish(self, context, cancelled=False):
        """Clean up and report results."""
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.workspace.status_text_set(None)

        elapsed = time.time() - self._start_time
        if cancelled:
            self.report({'WARNING'}, f"Cancelled. Processed {self._processed}/{self._total} textures before cancellation.")
        else:
            self.report({'INFO'}, f"Done! Processed {self._processed} textures, {self._failed} failed. Opacity set to {int(self._opacity_value * 100)}%. Time: {elapsed:.1f}s")

    def execute(self, context):
        """Called after file browser selection - parse filenames and start modal."""
        if PatchesNotLoaded(self):
            return {'CANCELLED'}

        # Scan directory for texture files and parse filenames
        # Expected format: {archive_hex}_{file_id}.png or .dds
        texture_list = []
        valid_extensions = {'.png', '.dds'}

        try:
            for filename in os.listdir(self.directory):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in valid_extensions:
                    continue

                # Parse filename: archive_hex_file_id.ext
                basename = os.path.splitext(filename)[0]
                parts = basename.split('_')

                if len(parts) < 2:
                    PrettyPrint(f"Skipping {filename} - invalid format (expected archive_fileid)", 'WARN')
                    continue

                # Archive is everything before the last underscore, file_id is after
                archive_hex = '_'.join(parts[:-1])
                file_id_str = parts[-1]

                try:
                    file_id = int(file_id_str)
                except ValueError:
                    PrettyPrint(f"Skipping {filename} - invalid file_id '{file_id_str}'", 'WARN')
                    continue

                # Format is unknown when parsing from filename, will be detected when loading
                texture_list.append((archive_hex, file_id, ''))

        except Exception as e:
            self.report({'ERROR'}, f"Failed to scan directory: {str(e)}")
            return {'CANCELLED'}

        if not texture_list:
            self.report({'ERROR'}, "No valid texture files found. Expected format: {archive}_{file_id}.png/dds")
            return {'CANCELLED'}

        # Sort by archive to minimize reloading
        texture_list.sort(key=lambda x: x[0])

        # Initialize modal state
        self._texture_list = texture_list
        self._texture_index = 0
        self._processed = 0
        self._failed = 0
        self._total = len(texture_list)
        self._tempdir = get_temp_folder()
        self._current_archive = None
        self._opacity_value = self.opacity
        self._start_time = time.time()

        PrettyPrint(f"Starting batch opacity patch: {self._total} textures, opacity={int(self._opacity_value * 100)}%")

        # Start timer for modal processing
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)

        self.report({'INFO'}, f"Processing {self._total} textures... Press ESC to cancel")
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "opacity")
        layout.label(text=f"Opacity: {int(self.opacity * 100)}%")

#endregion

#region Operators: Materials

class SaveMaterialOperator(Operator):
    bl_label = "Save Material"
    bl_idname = "helldiver2.material_save"
    bl_description = "Saves Material"

    object_id: StringProperty()
    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            Global_TocManager.Save(int(EntryID), MaterialID)
        return{'FINISHED'}

class ImportMaterialOperator(Operator):
    bl_label = "Import Material"
    bl_idname = "helldiver2.material_import"
    bl_description = "Loads Materials into Blender Project"

    object_id: StringProperty()
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        for EntryID in EntriesIDs:
            Global_TocManager.Load(int(EntryID), MaterialID)
        return{'FINISHED'}

class AddMaterialOperator(Operator):
    bl_label = "Add Material"
    bl_idname = "helldiver2.material_add"
    bl_description = "Adds a New Material to Current Active Patch"

    global Global_Materials
    selected_material: EnumProperty(items=Global_Materials, name="Template", default=0)

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        
        CreateModdedMaterial(self.selected_material)

        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        LoadEntryLists()
        
        return{'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
class SetMaterialTemplateOperator(Operator):
    bl_label = "Set Template"
    bl_idname = "helldiver2.material_set_template"
    bl_description = "Sets the material to a modded material template"
    
    global Global_Materials
    selected_material: EnumProperty(items=Global_Materials, name="Template", default=0)

    entry_id: StringProperty()

    def execute(self, context):
        if PatchesNotLoaded(self):
            return {'CANCELLED'}
        
        PrettyPrint(f"Found: {self.entry_id}")
            
        Entry = Global_TocManager.GetEntry(int(self.entry_id), MaterialID)
        if not Entry:
            raise Exception(f"Could not find entry at ID: {self.entry_id}")

        Entry.MaterialTemplate = self.selected_material
        Entry.Load(True)
        
        PrettyPrint(f"Finished Set Template: {self.selected_material}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def CreateModdedMaterial(template, ID=None):
    path = f"{Global_materialpath}/{template}.material"
    if not os.path.exists(path):
        raise Exception(f"Selected material template: {template} does not exist")

    Entry = TocEntry()
    if ID == None:
        Entry.FileID = RandomHash16()
        PrettyPrint(f"File ID is now: {Entry.FileID}")
    else:
        Entry.FileID = ID
        PrettyPrint(f"Found pre-existing file ID: {ID}")

    Entry.TypeID = MaterialID
    Entry.MaterialTemplate = template
    Entry.IsCreated = True
    with open(path, 'r+b') as f:
        data = f.read()
    Entry.TocData_OLD   = data
    Entry.TocData       = data

    Global_TocManager.AddNewEntryToPatch(Entry)
        
    EntriesIDs = IDsFromString(str(Entry.FileID))
    for EntryID in EntriesIDs:
        Global_TocManager.Load(int(EntryID), MaterialID)

class ShowMaterialEditorOperator(Operator):
    bl_label = "Show Material Editor"
    bl_idname = "helldiver2.material_showeditor"
    bl_description = "Show List of Textures in Material"

    object_id: StringProperty()
    def execute(self, context):
        Entry = Global_TocManager.GetEntry(int(self.object_id), MaterialID)
        if Entry != None:
            if not Entry.IsLoaded: Entry.Load(False, False)
            mat = Entry.LoadedData
            if mat.DEV_ShowEditor:
                mat.DEV_ShowEditor = False
            else:
                mat.DEV_ShowEditor = True
        return{'FINISHED'}

class SetMaterialTexture(Operator, ImportHelper):
    bl_label = "Set Material Texture"
    bl_idname = "helldiver2.material_settex"

    filename_ext = ".dds"

    filter_glob: StringProperty(default="*.dds", options={'HIDDEN'})

    object_id: StringProperty(options={"HIDDEN"})
    tex_idx: IntProperty(options={"HIDDEN"})

    def execute(self, context):
        Entry = Global_TocManager.GetEntry(int(self.object_id), MaterialID)
        if Entry != None:
            if Entry.IsLoaded:
                Entry.LoadedData.DEV_DDSPaths[self.tex_idx] = self.filepath
        
        # Redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D": area.tag_redraw()
        
        return{'FINISHED'}

#endregion

#region Operators : Animation
class ImportStingrayAnimationOperator(Operator):
    bl_label = "Import Animation"
    bl_idname = "helldiver2.archive_animation_import"
    bl_description = "Loads Animation into Blender Scene"
    
    object_id: StringProperty()
    def execute(self, context):
        # check if armature selected
        armature = context.active_object
        if armature.type != "ARMATURE":
            self.report({'ERROR'}, "Please select an armature to import the animation to")
            return {'CANCELLED'}
        animation_id = self.object_id
        try:
            Global_TocManager.Load(int(animation_id), AnimationID)
        except AnimationException as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}
        except Exception as error:
            PrettyPrint(f"Encountered unknown animation error: {error}", 'error')
            self.report({'ERROR'}, f"Encountered an error whilst importing animation. See Console for more info.")
            return {'CANCELLED'}
        return{'FINISHED'}
        
class SaveStingrayAnimationOperator(Operator):
    bl_label  = "Save Animation"
    bl_idname = "helldiver2.archive_animation_save"
    bl_description = "Saves animation"
    
    def execute(self, context):
        if PatchesNotLoaded(self):
            return{'CANCELLED'}
        object = bpy.context.active_object
        if object.animation_data is None or object.animation_data.action is None:
            self.report({'ERROR'}, "Armature has no active action!")
            return {'CANCELLED'}
        if object == None or object.type != "ARMATURE":
            self.report({'ERROR'}, "Please select an armature")
            return {'CANCELLED'}
        action_name = object.animation_data.action.name
        if len(object.animation_data.action.fcurves) == 0:
            self.report({'ERROR'}, f"Action: {action_name} has no keyframe data! Make sure your animation has at least an initial keyframe with a recorded pose.")
            return {'CANCELLED'}
        entry_id = action_name.split(" ")[0].split("_")[0].split(".")[0]
        if entry_id.startswith("0x"):
            entry_id = hex_to_decimal(entry_id)
        try:
            bones_id = object['BonesID']
        except Exception as e:
            PrettyPrint(f"Encountered animation error: {e}", 'error')
            self.report({'ERROR'}, f"Armature: {object.name} is missing HD2 custom property: BonesID")
            return{'CANCELLED'}
        PrettyPrint(f"Getting Animation Entry: {entry_id}")
        animation_entry = Global_TocManager.GetEntryByLoadArchive(int(entry_id), AnimationID)
        if not animation_entry:
            self.report({'ERROR'}, f"Could not find animation entry for Action: {action_name} as EntryID: {entry_id}. Assure your action name starts with a valid ID for the animation entry.")
            return{'CANCELLED'}
        if not animation_entry.IsLoaded: animation_entry.Load(True, False)
        bones_entry = Global_TocManager.GetEntry(int(bones_id), BoneID, SearchAll=True, IgnorePatch=False)
        bones_data = bones_entry.TocData
        if not Global_TocManager.IsInPatch(animation_entry):
            animation_entry = Global_TocManager.AddEntryToPatch(int(entry_id), AnimationID)
        else:
            Global_TocManager.RemoveEntryFromPatch(int(entry_id), AnimationID)
            animation_entry = Global_TocManager.AddEntryToPatch(int(entry_id), AnimationID)
        try:
            animation_entry.LoadedData.load_from_armature(context, object, bones_data)
        except AnimationException as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        wasSaved = animation_entry.Save()
        if not wasSaved:
            self.report({"ERROR"}, f"Failed to save animation for armature {bpy.context.selected_objects[0].name}.")
            return{'CANCELLED'}
        self.report({'INFO'}, f"Saved Animation")
        return {'FINISHED'}

#region Operators: Particles
class SaveStingrayParticleOperator(Operator):
    bl_label  = "Save Particle"
    bl_idname = "helldiver2.particle_save"
    bl_description = "Saves Particle"
    bl_options = {'REGISTER', 'UNDO'} 

    object_id: StringProperty()
    def execute(self, context):
        mode = context.mode
        if mode != 'OBJECT':
            self.report({'ERROR'}, f"You are Not in OBJECT Mode. Current Mode: {mode}")
            return {'CANCELLED'}
        wasSaved = Global_TocManager.Save(int(self.object_id), ParticleID)

        # we can handle below later when we put a particle object into the blender scene

        # if not wasSaved:
        #         for object in bpy.data.objects:
        #             try:
        #                 ID = object["Z_ObjectID"]
        #                 self.report({'ERROR'}, f"Archive for entry being saved is not loaded. Object: {object.name} ID: {ID}")
        #                 return{'CANCELLED'}
        #             except:
        #                 self.report({'ERROR'}, f"Failed to find object with custom property ID. Object: {object.name}")
        #                 return{'CANCELLED'}
        # self.report({'INFO'}, f"Saved Mesh Object ID: {self.object_id}")
        return{'FINISHED'}
class ImportStingrayParticleOperator(Operator):
    bl_label = "Import Particle"
    bl_idname = "helldiver2.archive_particle_import"
    bl_description = "Loads Particles into Blender Scene"

    object_id: StringProperty()
    def execute(self, context):
        EntriesIDs = IDsFromString(self.object_id)
        Errors = []
        for EntryID in EntriesIDs:
            if len(EntriesIDs) == 1:
                Global_TocManager.Load(EntryID, ParticleID)
            else:
                try:
                    Global_TocManager.Load(EntryID, ParticleID)
                except Exception as error:
                    Errors.append([EntryID, error])

        if len(Errors) > 0:
            PrettyPrint("\nThese errors occurred while attempting to load particles...", "error")
            idx = 0
            for error in Errors:
                PrettyPrint(f"  Error {idx}: for particle {error[0]}", "error")
                PrettyPrint(f"    {error[1]}\n", "error")
                idx += 1
            raise Exception("One or more particles failed to load")
        return{'FINISHED'}
#endregion

#region Operators: Clipboard Functionality

class CopyArchiveEntryOperator(Operator):
    bl_label = "Copy Entry"
    bl_idname = "helldiver2.archive_copy"
    bl_description = "Copy Selected Entries"

    object_id: StringProperty()
    object_typeid: StringProperty()
    def execute(self, context):
        Entries = EntriesFromStrings(self.object_id, self.object_typeid)
        Global_TocManager.Copy(Entries)
        return{'FINISHED'}

class PasteArchiveEntryOperator(Operator):
    bl_label = "Paste Entry"
    bl_idname = "helldiver2.archive_paste"
    bl_description = "Paste Selected Entries"

    def execute(self, context):
        Global_TocManager.Paste()
        return{'FINISHED'}

class ClearClipboardOperator(Operator):
    bl_label = "Clear Clipboard"
    bl_idname = "helldiver2.archive_clearclipboard"
    bl_description = "Clear Selected Entries from Clipboard"

    def execute(self, context):
        Global_TocManager.ClearClipboard()
        return{'FINISHED'}

class CopyTextOperator(Operator):
    bl_label  = "Copy ID"
    bl_idname = "helldiver2.copytest"
    bl_description = "Copies Entry Information"

    text: StringProperty()
    def execute(self, context):
        cmd='echo|set /p="'+str(self.text).strip()+'"|clip'
        subprocess.check_call(cmd, shell=True)
        self.report({'INFO'}, f"Copied: {self.text}")
        return{'FINISHED'}

#endregion

#region Operators: UI/UX

class LoadArchivesOperator(Operator):
    bl_label = "Load Archives"
    bl_idname = "helldiver2.archives_import"
    bl_description = "Loads Selected Archive"

    paths_str: StringProperty(name="paths_str")
    def execute(self, context):
        global Global_TocManager
        if self.paths_str != "" and (os.path.exists(self.paths_str) or is_slim_version()):
            Global_TocManager.LoadArchive(self.paths_str)
            id = self.paths_str.replace(Global_gamepath, "")
            name = f"{GetArchiveNameFromID(id)} {id}"
            self.report({'INFO'}, f"Loaded {name}")
            return{'FINISHED'}
        else:
            message = "Archive Failed to Load"
            if not os.path.exists(self.paths_str):
                message = "Current Filepath is Invalid. Change This in Settings"
            self.report({'ERROR'}, message )
            return{'CANCELLED'}

class ManuallyLoadArchivesOperator(Operator):
    bl_label = "Load Archive By ID"
    bl_idname = "helldiver2.archives_import_manual"
    bl_description = "Loads Archives by Archive ID (comma-separated for multiple)"

    archive_id: StringProperty(name="Archive ID(s)", description="Enter archive IDs separated by commas")
    def execute(self, context):
        global Global_TocManager

        # Split by comma and strip whitespace
        archive_ids = [aid.strip() for aid in self.archive_id.split(',') if aid.strip()]

        if not archive_ids:
            self.report({'ERROR'}, "No archive IDs provided")
            return {'CANCELLED'}

        loaded_count = 0
        failed_count = 0
        loaded_names = []

        for archive_id in archive_ids:
            ID = archive_id
            if ID.startswith("0x"):
                ID = hex_to_decimal(archive_id)

            path = os.path.join(Global_gamepath, ID)

            if path != "" and (os.path.exists(path) or is_slim_version()):
                Global_TocManager.LoadArchive(path)
                name = GetArchiveNameFromID(ID)
                loaded_names.append(f"{name} ({ID})" if name else ID)
                loaded_count += 1
            else:
                PrettyPrint(f"Failed to load archive: {ID}", "warn")
                failed_count += 1

        if loaded_count > 0:
            if loaded_count == 1:
                self.report({'INFO'}, f"Loaded {loaded_names[0]}")
            else:
                self.report({'INFO'}, f"Loaded {loaded_count} archives")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Failed to load {failed_count} archive(s)")
            return {'CANCELLED'}

    def invoke(self, context, event):
        self.archive_id = ""
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "archive_id")
        layout.label(text="Separate multiple IDs with commas")

class SearchArchivesOperator(Operator):
    bl_label = "Search Found Archives"
    bl_idname = "helldiver2.search_archives"
    bl_description = "Search from Found Archives"

    SearchField : StringProperty(name="SearchField", default="")
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "SearchField", icon='VIEWZOOM')
        # Update displayed archives
        if self.PrevSearch != self.SearchField:
            self.PrevSearch = self.SearchField

            self.ArchivesToDisplay = []
            for Entry in Global_ArchiveHashes:
                if Entry[1].lower().find(self.SearchField.lower()) != -1:
                    self.ArchivesToDisplay.append([Entry[0], Entry[1]])
    
        if self.SearchField != "" and len(self.ArchivesToDisplay) == 0:
            row = layout.row(); row.label(text="No Archive IDs Found")
            row = layout.row(); row.label(text="Know an ID that's Not Here?")
            row = layout.row(); row.label(text="Make an issue on the github.")
            row = layout.row(); row.label(text="Archive ID and In Game Name")
            row = layout.row(); row.operator("helldiver2.github", icon= 'URL')

        else:
            for Archive in self.ArchivesToDisplay:
                row = layout.row()
                row.label(text=Archive[1], icon='GROUP')
                row.operator("helldiver2.archives_import", icon= 'FILE_NEW', text="").paths_str = Global_gamepath + str(Archive[0])

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        self.SearchField = ""
        self.PrevSearch = "NONE"
        self.ArchivesToDisplay = []

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

class SelectAllOfTypeOperator(Operator):
    bl_label  = "Select All"
    bl_idname = "helldiver2.select_type"
    bl_description = "Selects All of Type in Section"

    list_id: StringProperty()
    def execute(self, context):
        _list = getattr(context.scene, self.list_id)
        for item in _list:
            item.item_selected = True
        return{'FINISHED'}
    
class ImportAllOfTypeOperator(Operator):
    bl_label  = "Import All Of Type"
    bl_idname = "helldiver2.import_type"

    object_typeid: StringProperty()
    def execute(self, context):
        Entries = GetDisplayData()[0]
        for EntryInfo in Entries:
            Entry = EntryInfo[0]
            #if Entry.TypeID == int(self.object_typeid):
            DisplayEntry = Global_TocManager.GetEntry(Entry.FileID, Entry.TypeID)
            objectid = str(DisplayEntry.FileID)

            if DisplayEntry.TypeID == UnitID or DisplayEntry.TypeID == CompositeUnitID:
                EntriesIDs = IDsFromString(objectid)
                for EntryID in EntriesIDs:
                    try:
                        Global_TocManager.Load(EntryID, UnitID)
                    except Exception as error:
                        self.report({'ERROR'},[EntryID, error])

            elif DisplayEntry.TypeID == TexID:
                print("tex")
                #operator = bpy.ops.helldiver2.texture_import(object_id=objectid)
                #ImportTextureOperator.execute(operator, operator)

            elif DisplayEntry.TypeID == MaterialID:
                print("mat")
                #operator = bpy.ops.helldiver2.material_import(object_id=objectid)
                #ImportMaterialOperator.execute(operator, operator)
        return{'FINISHED'}

class SetEntryFriendlyNameOperator(Operator):
    bl_label = "Set Friendly Name"
    bl_idname = "helldiver2.archive_setfriendlyname"
    bl_description = "Change Entry Display Name"

    NewFriendlyName : StringProperty(name="NewFriendlyName", default="")
    def draw(self, context):
        layout = self.layout; row = layout.row()
        row.prop(self, "NewFriendlyName", icon='COPY_ID')
        row = layout.row()
        if murmur64_hash(str(self.NewFriendlyName).encode()) == int(self.object_id):
            row.label(text="Hash is correct")
        else:
            row.label(text="Hash is incorrect")
        row.label(text=str(murmur64_hash(str(self.NewFriendlyName).encode())))

    object_id: StringProperty()
    def execute(self, context):
        AddFriendlyName(int(self.object_id), str(self.NewFriendlyName))
        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

#endregion

#region Operators: Help

class HelpOperator(Operator):
    bl_label  = "Help"
    bl_idname = "helldiver2.help"
    bl_description = "Link to Modding Discord"

    def execute(self, context):
        url = "https://discord.gg/helldiversmodding"
        webbrowser.open(url, new=0, autoraise=True)
        return{'FINISHED'}

class ArchiveSpreadsheetOperator(Operator):
    bl_label  = "Archive Spreadsheet"
    bl_idname = "helldiver2.archive_spreadsheet"
    bl_description = "Opens Spreadsheet with Indentified Archives"

    def execute(self, context):
        url = "https://docs.google.com/spreadsheets/d/1oQys_OI5DWou4GeRE3mW56j7BIi4M7KftBIPAl1ULFw"
        webbrowser.open(url, new=0, autoraise=True)
        return{'FINISHED'}

class GithubOperator(Operator):
    bl_label  = "Github"
    bl_idname = "helldiver2.github"
    bl_description = "Opens The Github Page"

    def execute(self, context):
        url = "https://github.com/Boxofbiscuits97/HD2SDK-CommunityEdition"
        webbrowser.open(url, new=0, autoraise=True)
        return{'FINISHED'}
    
class LatestReleaseOperator(Operator):
    bl_label  = "Update Helldivers 2 SDK"
    bl_idname = "helldiver2.latest_release"
    bl_description = "Opens The Github Page to the latest release"

    def execute(self, context):
        url = "https://github.com/Boxofbiscuits97/HD2SDK-CommunityEdition/releases/latest"
        webbrowser.open(url, new=0, autoraise=True)
        return{'FINISHED'}
        
class AutoUpdateOperator(Operator):
    bl_label = "Auto Update Helldivers 2 SDK"
    bl_idname = "helldiver2.update"
    bl_description = "Updates the addon to the latest release"
    
    def execute(self, context):
        r = requests.get("https://api.github.com/repos/boxofbiscuits97/HD2SDK-CommunityEdition/releases/latest")
        if r.status_code != 200:
            self.report({'ERROR'}, "Error fetching latest update")
            return {'CANCELLED'}
        data = r.json()
        download_url = data["assets"][0]["browser_download_url"]
        r = requests.get(download_url)
        if r.status_code != 200:
            self.report({'ERROR'}, "Error fetching latest update")
            return {'CANCELLED'}
        script_dir = os.path.dirname(os.path.abspath(__file__))
        zipfilepath = os.path.join(script_dir, "temp.zip")
        for item in os.listdir(script_dir):
            item = os.path.join(script_dir, item)
            if os.path.isfile(item):
                try:
                    os.remove(item)
                except:
                    pass
            elif os.path.isdir(item):
                try:
                    shutil.rmtree(item)
                except:
                    pass
        with open(zipfilepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        z = zipfile.ZipFile(zipfilepath)
        for member in z.namelist():
            if member.startswith("HD2SDK-CommunityEdition") and not member.endswith('/'):
                relative_path = os.path.relpath(member, "HD2SDK-CommunityEdition")
                destination_path = os.path.join(script_dir, relative_path)

                # Create necessary subdirectories if they don't exist
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)

                # Extract the file (DLL has permission error to overwrite)
                try:
                    with z.open(member) as source, open(destination_path, 'wb') as target:
                        target.write(source.read())
                except:
                    pass
        z.close()
        try:
            os.remove(zipfilepath)
        except:
            pass
        bpy.ops.script.reload()
        return {'FINISHED'}

class MeshFixOperator(Operator, ImportHelper):
    bl_label = "Fix Meshes"
    bl_idname = "helldiver2.meshfixtool"
    bl_description = "Auto-fixes meshes in the currently loaded patch. Warning, this may take some time."

    directory: StringProperty(
        name="Directory",
        description="Choose a directory",
        subtype='DIR_PATH'
    )
    
    filter_folder: BoolProperty(
        default=True,
        options={'HIDDEN'}
    )
    
    use_filter_folder = True
    def execute(self, context):   
        if ArchivesNotLoaded(self):
            return {'CANCELLED'}
        path = self.directory
        output = RepatchMeshes(self, path)
        if output == {'CANCELLED'}: return {'CANCELLED'}
        
        return{'FINISHED'}
#endregion

def RepatchMeshes(self, path):
    if len(bpy.context.scene.objects) > 0:
        self.report({'ERROR'}, f"Scene is not empty! Please remove all objects in the scene before starting the repatching process!")
        return{'CANCELLED'}
    
    Global_TocManager.UnloadPatches()
    
    settings = bpy.context.scene.Hd2ToolPanelSettings
    settings.ImportLods = False
    settings.AutoLods = True
    settings.ImportStatic = False
    
    PrettyPrint(f"Searching for patch files in: {path}")
    patchPaths = []
    LoopPatchPaths(patchPaths, path)
    PrettyPrint(f"Found Patch Paths: {patchPaths}")
    if len(patchPaths) == 0:
        self.report({'ERROR'}, f"No patch files were found in selected path")
        return{'ERROR'}

    errors = []
    for path in patchPaths:
        PrettyPrint(f"Patching: {path}")
        Global_TocManager.LoadArchive(path, True, True)
        numMeshesRepatched = 0
        failed = False
        for entry in Global_TocManager.ActivePatch.TocEntries: # Fix Later
            if entry.TypeID != UnitID:
                PrettyPrint(f"Skipping {entry.FileID} as it is not a mesh entry")
                continue
            PrettyPrint(f"Repatching {entry.FileID}")
            Global_TocManager.GetEntryByLoadArchive(entry.FileID, entry.TypeID)
            settings.AutoLods = True
            settings.ImportStatic = False
            numMeshesRepatched += 1
            entry.Load(False, True)
            patchObjects = bpy.context.scene.objects
            if len(patchObjects) == 0: # Handle static meshes
                settings.AutoLods = False
                settings.ImportStatic = True
                entry.Load(False, True)
                patchObjects = bpy.context.scene.objects
            OldMeshInfoIndex = patchObjects[0]['MeshInfoIndex']
            fileID = entry.FileID
            typeID = entry.TypeID
            Global_TocManager.RemoveEntryFromPatch(fileID, typeID)
            Global_TocManager.AddEntryToPatch(fileID, typeID)
            newEntry = Global_TocManager.GetEntry(fileID, typeID)
            if newEntry:
                PrettyPrint(f"Entry successfully created")
            else:
                failed = True
                errors.append([path, fileID, "Could not create newEntry", "error"])
                continue
            newEntry.Load(False, False)
            NewMeshes = newEntry.LoadedData.RawMeshes
            NewMeshInfoIndex = ""
            for mesh in NewMeshes:
                if mesh.LodIndex == 0:
                    NewMeshInfoIndex = mesh.MeshInfoIndex
            if NewMeshInfoIndex == "": # if the index is still a string, we couldn't find it
                PrettyPrint(f"Could not find LOD 0 for mesh: {fileID}. Skipping mesh index checks", "warn")
                errors.append([path, fileID, "Could not find LOD 0 for mesh so LOD index updates did not occur. This may be intended", "warn"])
            else:
                PrettyPrint(f"Old MeshIndex: {OldMeshInfoIndex} New MeshIndex: {NewMeshInfoIndex}")
                if OldMeshInfoIndex != NewMeshInfoIndex:
                    PrettyPrint(f"Swapping mesh index to new index", "warn")
                    patchObjects[0]['MeshInfoIndex'] = NewMeshInfoIndex
            for object in patchObjects:
                object.select_set(True)
            newEntry.Save()
            for object in bpy.context.scene.objects:
                bpy.data.objects.remove(object)

        if not failed:
            Global_TocManager.PatchActiveArchive()
            PrettyPrint(f"Repatched {numMeshesRepatched} meshes in patch: {path}")
        else:
            PrettyPrint(f"Faield to repatch meshes in patch: {path}", "error")
        Global_TocManager.UnloadPatches()
    
    if len(errors) == 0:
        PrettyPrint(f"Finished repatching {len(patchPaths)} modsets")
        self.report({'INFO'}, f"Finished Repatching meshes with no errors")
    else:
        for error in errors:
            PrettyPrint(f"Failed to patch mesh: {error[1]} in patch: {error[0]} Error: {error[2]}", error[3])
        self.report({'ERROR'}, f"Failed to patch {len(errors)} meshes. Please check logs to see the errors")

def LoopPatchPaths(list, filepath):
    for path in os.listdir(filepath):
        path = f"{filepath}/{path}"
        if Path(path).is_dir():
            PrettyPrint(f"Looking in folder: {path}")
            LoopPatchPaths(list, path)
            continue
        if "patch_" in path:
            PrettyPrint(f"Adding Path: {path}")
            strippedpath = path.replace(".gpu_resources", "").replace(".stream", "")
            if strippedpath not in list:
                list.append(strippedpath)
        else:
            PrettyPrint(f"Path: {path} is not a patch file. Ignoring file.", "warn")
            
#region Operators: Context Menu

stored_custom_properties = {}
class CopyCustomPropertyOperator(Operator):
    bl_label = "Copy HD2 Properties"
    bl_idname = "helldiver2.copy_custom_properties"
    bl_description = "Copies Custom Property Data for Helldivers 2 Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global stored_custom_properties
        
        selectedObjects = context.selected_objects
        if len(selectedObjects) == 0:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}
        PrettyPrint(selectedObjects)

        obj = context.active_object
        stored_custom_properties.clear()
        for key, value in obj.items():
            if key not in obj.bl_rna.properties:  # Skip built-in properties
                stored_custom_properties[key] = value

        self.report({'INFO'}, f"Copied {len(stored_custom_properties)} custom properties")
        return {'FINISHED'}

class PasteCustomPropertyOperator(Operator):
    bl_label = "Paste HD2 Properties"
    bl_idname = "helldiver2.paste_custom_properties"
    bl_description = "Pastes Custom Property Data for Helldivers 2 Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global stored_custom_properties

        selectedObjects = context.selected_objects
        if len(selectedObjects) == 0:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}

        obj = context.active_object
        if not stored_custom_properties:
            self.report({'WARNING'}, "No custom properties to paste")
            return {'CANCELLED'}

        for key, value in stored_custom_properties.items():
            obj[key] = value

        for area in bpy.context.screen.areas:
            area.tag_redraw()

        self.report({'INFO'}, f"Pasted {len(stored_custom_properties)} custom properties")
        return {'FINISHED'}

def CustomPropertyContext(self, context):
    layout = self.layout
    layout.separator()
    layout.label(text=Global_SectionHeader)
    layout.separator()
    layout.operator("helldiver2.copy_hex_id", icon='COPY_ID')
    layout.operator("helldiver2.copy_decimal_id", icon='COPY_ID')
    layout.separator()
    layout.operator("helldiver2.copy_custom_properties", icon= 'COPYDOWN')
    layout.operator("helldiver2.paste_custom_properties", icon= 'PASTEDOWN')
    layout.separator()
    layout.operator("helldiver2.archive_animation_save", icon='ARMATURE_DATA')
    if bpy.context.object.type == "ARMATURE":
        if bpy.context.object.get("StateMachineID", None) is not None:
            layout.operator("helldiver2.search_animations", text="Show Animations for this Armature", icon='VIEWZOOM').state_machine_id = bpy.context.object.get("StateMachineID")
    layout.operator("helldiver2.archive_unit_batchsave", icon= 'FILE_BLEND')
    
def CustomBoneContext(self, context):
    layout = self.layout
    layout.separator()
    layout.label(text=Global_SectionHeader)
    layout.separator()
    layout.operator("helldiver2.set_bone_animated", text="Set Bone Animated", icon='ARMATURE_DATA').value = True
    layout.operator("helldiver2.set_bone_animated", text="Set Bone Not Animated", icon='ARMATURE_DATA').value = False
    layout.operator("helldiver2.add_light", icon='OUTLINER_OB_LIGHT')
    #layout.operator("helldiver2.set_bone_ragdoll", text="Set Jiggle Bone", icon="ARMATURE_DATA").value = True
    #layout.operator("helldiver2.set_bone_ragdoll", text="Set Not Jiggle Bone", icon="ARMATURE_DATA").value = False
    
class SearchArmatureAnimationsOperator(Operator):
    bl_label = "Search Animations"
    bl_idname = "helldiver2.search_animations"
    bl_description = "Show only animations for this armature"
    
    state_machine_id: StringProperty(default="0")
    
    def execute(self, context):
        context.scene.Hd2ToolPanelSettings.SearchField = self.state_machine_id
        global Global_Foldouts
        for key in Global_Foldouts.keys():
            Global_Foldouts[key] = (key == str(AnimationID))
        return {"FINISHED"}
    
class SetBoneAnimatedOperator(Operator):
    bl_label = "Set bone animated state"
    bl_idname = "helldiver2.set_bone_animated"
    bl_description = "Sets selected bones' animated state"
    
    value: BoolProperty(default=True)
    def execute(self, context):
        if bpy.context.object.mode != "EDIT":
            return {"FINISHED"}
        for bone in bpy.context.selected_bones:
            bone["Animated"] = self.value
        return {"FINISHED"}
        
class SetBoneRagdollOperator(Operator):
    bl_label = "Set bone ragdoll state"
    bl_idname = "helldiver2.set_bone_ragdoll"
    bl_description = "Sets bone to jiggle"
    
    value: BoolProperty(default=True)
    def execute(self, context):
        if bpy.context.object.mode != "EDIT":
            return {"FINISHED"}
        for bone in bpy.context.selected_bones:
            bone["Jiggle"] = self.value
            if self.value:
                bone["Weight"] = 0.0
                bone["Gravity"] = -9.8
                bone["Param 3"] = 0.0
                bone["Param 4"] = 0.0
                bone["Param 5"] = 0.0
                bone["Param 6"] = 0.0
                bone["Param 7"] = 0.0
                bone["Param 8"] = 0.0
                bone["Param 9"] = 0.0
            else:
                bone.pop("Weight")
                bone.pop("Gravity")
                bone.pop("Param 3")
                bone.pop("Param 4")
                bone.pop("Param 5")
                bone.pop("Param 6")
                bone.pop("Param 7")
                bone.pop("Param 8")
                bone.pop("Param 9")
                
        return {"FINISHED"}

class AddLightOperator(Operator):
    bl_label = "Add HD2 Light"
    bl_idname = "helldiver2.add_light"
    bl_description = "Adds a HD2 light to the selected bone"
    
    def execute(self, context):
        if bpy.context.object.mode != "EDIT":
            return {"FINISHED"}
        bone = bpy.context.active_bone
        armature = bpy.context.active_object
        light_name = f"Light_{r.randint(1, 0xffffffff)}"
        
        blend_light = bpy.data.lights.new(name = light_name, type="SPOT")
        blend_light.use_custom_distance = True
        blend_light.cutoff_distance = 50.0
        blend_light.energy = 1000.0
        blend_light.show_cone = True
        blend_light['Volumetric'] = False
        
        light_object = bpy.data.objects.new(name = light_name, object_data = blend_light)
        light_object.lock_rotation = (True, True, True)
        light_object.lock_location = (True, True, True)
        light_object.lock_scale = (True, True, True)
        light_object.parent = armature
        light_object.parent_type = 'BONE'
        light_object.parent_bone = bone.name
        light_object.matrix_parent_inverse = light_object.matrix_parent_inverse.inverted() @ mathutils.Matrix.Rotation(1.57079632679, 4, 'X')
        
        bpy.context.collection.objects.link(light_object)
        return {"FINISHED"}

class CopyArchiveIDOperator(Operator):
    bl_label = "Copy Archive ID"
    bl_idname = "helldiver2.copy_archive_id"
    bl_description = "Copies the Active Archive's ID to Clipboard"

    def execute(self, context):
        if ArchivesNotLoaded(self):
            return {'CANCELLED'}
        archiveID = str(Global_TocManager.ActiveArchive.Name)
        bpy.context.window_manager.clipboard = archiveID
        self.report({'INFO'}, f"Copied Archive ID: {archiveID}")

        return {'FINISHED'}
    
class CopyHexIDOperator(Operator):
    bl_label = "Copy Hex ID"
    bl_idname = "helldiver2.copy_hex_id"
    bl_description = "Copy the Hexidecimal ID of the selected mesh for the Diver tool"

    def execute(self, context):
        object = context.active_object
        if not object:
            self.report({"ERROR"}, "No object is selected")
        try:
            ID = int(object["Z_ObjectID"])
        except:
            self.report({'ERROR'}, f"Object: {object.name} has not Helldivers property ID")
            return {'CANCELLED'}

        try:
            hexID = hex(ID)
        except:
            self.report({'ERROR'}, f"Object: {object.name} ID: {ID} cannot be converted to hex")
            return {'CANCELLED'}
        
        CopyToClipboard(hexID)
        self.report({'INFO'}, f"Copied {object.name}'s property of {hexID}")
        return {'FINISHED'}

class CopyDecimalIDOperator(Operator):
    bl_label = "Copy ID"
    bl_idname = "helldiver2.copy_decimal_id"
    bl_description = "Copy the decimal ID of the selected mesh"

    def execute(self, context):
        object = context.active_object
        if not object:
            self.report({"ERROR"}, "No object is selected")
        try:
            ID = str(object["Z_ObjectID"])
        except:
            self.report({'ERROR'}, f"Object: {object.name} has not Helldivers property ID")
            return {'CANCELLED'}
        
        CopyToClipboard(ID)
        self.report({'INFO'}, f"Copied {object.name}'s property of {ID}")
        return {'FINISHED'}

class EntrySectionOperator(Operator):
    bl_label = "Collapse Section"
    bl_idname = "helldiver2.collapse_section"
    bl_description = "Fold Current Section"

    type: StringProperty(default = "")

    def execute(self, context):
        global Global_Foldouts
        try:
            Global_Foldouts[str(self.type)] = not Global_Foldouts[str(self.type)]
        except KeyError:
            pass
        #for i in range(len(Global_Foldouts)):
        #    if Global_Foldouts[i][0] == str(self.type):
        #        Global_Foldouts[i][1] = not Global_Foldouts[i][1]
        #        PrettyPrint(f"Folding foldout: {Global_Foldouts[i]}")
        return {'FINISHED'}
#endregion

#region Menus and Panels

def LoadEntryLists():
    archive = Global_TocManager.ActiveArchive
    patch = Global_TocManager.ActivePatch
    for t in Global_TypeIDs:
        getattr(bpy.context.scene, f"list_{t}").clear()
    state_machine_warning = False
    if archive and not bpy.context.scene.Hd2ToolPanelSettings.PatchOnly:
        for entry_type in archive.TocDict.keys():
            try:
                l = getattr(bpy.context.scene, f"list_{entry_type}")
            except AttributeError:
                continue
            for entry_id in sorted(archive.TocDict[entry_type].keys()):
                Entry = archive.TocDict[entry_type][entry_id]
                if patch:
                    try:
                        Entry = patch.TocDict[entry_type][entry_id]
                    except KeyError:
                        pass
                new_item = l.add()
                new_item.item_name = str(Entry.FileID)
                new_item.item_type = str(Entry.TypeID)
                if Entry.TypeID == MaterialID:
                    if not Entry.IsLoaded: Entry.Load(True, False)
                    new_item.item_filter_name = f"{new_item.item_name}," + ",".join([str(tex_id) for tex_id in Entry.LoadedData.TexIDs])
                elif Entry.TypeID == AnimationID:
                    try:
                        new_item.item_filter_name = f"{new_item.item_name}," + ",".join([str(state_machine_id) for state_machine_id in Global_AnimationMapping[Entry.FileID]])
                    except KeyError:
                        state_machine_warning = True
                        new_item.item_filter_name = new_item.item_name
                else:
                    new_item.item_filter_name = new_item.item_name
    if patch:
        for entry_type in patch.TocDict.keys():
            try:
                l = getattr(bpy.context.scene, f"list_{entry_type}")
            except AttributeError:
                continue
            for entry_id in sorted(patch.TocDict[entry_type].keys()):
                Entry = patch.TocDict[entry_type][entry_id]
                # skip adding entry if not in patchonly mode AND archive contains entry
                if (not bpy.context.scene.Hd2ToolPanelSettings.PatchOnly) and (archive and entry_type in archive.TocDict and Entry.FileID in archive.TocDict[entry_type]): continue
                new_item = l.add()
                new_item.item_name = str(Entry.FileID)
                new_item.item_type = str(Entry.TypeID)
                if Entry.TypeID == MaterialID:
                    if not Entry.IsLoaded: Entry.Load(True, False)
                    new_item.item_filter_name = f"{new_item.item_name}," + ",".join([str(tex_id) for tex_id in Entry.LoadedData.TexIDs])
                elif Entry.TypeID == AnimationID:
                    try:
                        new_item.item_filter_name = f"{new_item.item_name}," + ",".join([str(state_machine_id) for state_machine_id in Global_AnimationMapping[Entry.FileID]])
                    except KeyError:
                        state_machine_warning = True
                        new_item.item_filter_name = new_item.item_name
                else:
                    new_item.item_filter_name = new_item.item_name
    if state_machine_warning:
        PrettyPrint("State machine not loaded for all animations; filtering animations by armature may not work.", "warn")
        
    ChangeSearchString(bpy.context.scene.Hd2ToolPanelSettings, bpy.context)

def LoadedArchives_callback(scene, context):
    return [(Archive.Name, GetArchiveNameFromID(Archive.Name) if GetArchiveNameFromID(Archive.Name) != "" else Archive.Name, Archive.Name) for Archive in Global_TocManager.LoadedArchives]

def Patches_callback(scene, context):
    return [(Archive.Name, Archive.Name, Archive.Name) for Archive in Global_TocManager.Patches]
    
def ChangeLoadedArchive(self, context):
    Global_TocManager.SetActiveByName(self.LoadedArchives)
    
def ChangeActivePatch(self, context):
    Global_TocManager.SetActivePatchByName(self.Patches)

def ChangePatchOnly(self, context):
    LoadEntryLists()
    
def ChangeSearchString(self, context):
    for t in Global_TypeIDs:
        setattr(bpy.context.scene, f"filter_{t}", self.SearchField)
        list_data = getattr(bpy.context.scene, f"list_{t}")
        filter_string = self.SearchField
        if filter_string.startswith("0x"):
            filter_string = str(hex_to_decimal(filter_string))
        flt_flags = bpy.types.UI_UL_list.filter_items_by_name(filter_string, 1073741824, list_data, "item_filter_name")
        if not flt_flags:
            flt_flags = [1] * len(list_data)
        #flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(data, "item_name")
        for item in list_data:
            item.item_visible = not all([flag == 0 for flag in flt_flags])
            break

def get_conflict_patches(self, context):
    """Dynamic enum callback - returns patches that have this conflicting entry"""
    if not self.patches:
        return [("NONE", "None", "No patches")]
    patches = self.patches.split(",")
    return [(p, p, p) for p in patches]

class ConflictItem(PropertyGroup):
    """Stores information about a conflicting entry when combining patches"""
    file_id: StringProperty(name="FileID")
    type_id: StringProperty(name="TypeID")
    friendly_name: StringProperty(name="Name")
    patches: StringProperty(name="Patches")  # Comma-separated patch names
    selected_patch: EnumProperty(
        name="Winner",
        items=get_conflict_patches,
        description="Select which patch's version to use"
    )

class Hd2ToolPanelSettings(PropertyGroup):
    # Patches
    Patches   : EnumProperty(name="Patches", items=Patches_callback, update=ChangeActivePatch)
    PatchOnly : BoolProperty(name="Show Patch Entries Only", description = "Filter list to entries present in current patch", default = False, update=ChangePatchOnly)
    # Archive
    ContentsExpanded : BoolProperty(default = True)
    LoadedArchives   : EnumProperty(name="LoadedArchives", items=LoadedArchives_callback, update=ChangeLoadedArchive)
    # Settings
    MenuExpanded     : BoolProperty(default = False)

    ShowExtras       : BoolProperty(name="Extra Entry Types", description = "Shows all Extra entry types.", default = False)
    FriendlyNames    : BoolProperty(name="Show Friendly Names", description="Enable friendly names for entries if they have any. Disabling this option can greatly increase UI preformance if a patch has a large number of entries.", default = True)

    ImportMaterials  : BoolProperty(name="Import Materials", description = "Fully import materials by appending the textures utilized, otherwise create placeholders", default = True)
    ImportLods       : BoolProperty(name="Import LODs", description = "Import LODs", default = False)
    ImportGroup0     : BoolProperty(name="Import Group 0 Only", description = "Only import the first vertex group, ignore others", default = True)
    ImportCulling    : BoolProperty(name="Import Culling Bounds", description = "Import Culling Bodies", default = False)
    ImportStatic     : BoolProperty(name="Import Static Meshes", description = "Import Static Meshes", default = False)
    KeepFilediverObjects : BoolProperty(name="Keep Filediver Objects", description = "Keep filediver objects after Import with Shader for debugging purposes", default = False)
    MakeCollections  : BoolProperty(name="Make Collections", description = "Make new collection when importing meshes", default = False)
    Force3UVs        : BoolProperty(name="Force 3 UV Sets", description = "Force at least 3 UV sets, some materials require this", default = True)
    Force1Group      : BoolProperty(name="Force 1 Group", description = "Force mesh to only have 1 vertex group", default = True)
    AutoLods         : BoolProperty(name="Auto LODs", description = "Automatically generate LOD entries based on LOD0, does not actually reduce the quality of the mesh", default = True)
    RemoveGoreMeshes : BoolProperty(name="Remove Gore Meshes", description = "Automatically delete all of the verticies with the gore material when loading a model", default = False)
    SaveBonePositions: BoolProperty(name="Save Animation Bone Positions", description = "Include bone positions in animation (may mess with additive animations being applied)", default = True)
    ImportArmature   : BoolProperty(name="Import Armatures", description = "Import unit armature data", default = True)
    MergeArmatures   : BoolProperty(name="Merge Armatures", description = "Merge new armatures to the selected armature", default = False)
    ParentArmature   : BoolProperty(name="Parent Armatures", description = "Make imported armatures the parent of the imported mesh", default = True)
    SplitUVIslands   : BoolProperty(name="Split UV Islands", description = "Split mesh by UV islands when saving", default = False)
    # Search
    SearchField      : StringProperty(default = "", update=ChangeSearchString)

    # Tools
    EnableTools           : BoolProperty(name="Special Tools", description = "Enable advanced SDK Tools", default = False)
    UnloadEmptyArchives   : BoolProperty(name="Unload Empty Archives", description="Unload Archives that do not Contain any Textures, Materials, or Meshes", default = True)
    DeleteOnLoadArchive   : BoolProperty(name="Nuke Files on Archive Load", description="Delete all Textures, Materials, and Meshes in project when selecting a new archive", default = False)
    UnloadPatches         : BoolProperty(name="Unload Previous Patches", description="Unload Previous Patches when bulk loading")
    LoadFoundArchives     : BoolProperty(name="Load Found Archives", description="Load the archives found when search by entry ID", default=True)

    AutoSaveUnitMaterials : BoolProperty(name="Autosave Unit Materials", description="Save unsaved material entries applied to meshes when the unit is saved", default = True)
    SaveNonSDKMaterials   : BoolProperty(name="Save Non-SDK Materials", description="Toggle if non-SDK materials should be autosaved when saving a mesh", default = False)
    SaveUnsavedOnWrite    : BoolProperty(name="Save Unsaved on Write", description="Save all entries that are unsaved when writing a patch", default = True)
    PatchBaseArchiveOnly  : BoolProperty(name="Patch Base Archive Only", description="When enabled, it will allow patched to only be created if the base archive is selected. This is helpful for new users.", default = True)
    LegacyWeightNames     : BoolProperty(name="Legacy Weight Names", description="Brings back the old naming system for vertex groups using the X_Y schema", default = False)
    
    SaveTexturesWithMaterial: BoolProperty(name="Save Textures with Material", description="Save a material\'s referenced textures to the patch when said material is saved. When disabled, new random IDs will not be given each time the material is saved", default = True)
    GenerateRandomTextureIDs: BoolProperty(name="Generate Random Texture IDs", description="Give a material\'s referenced textures new random IDs when said material is saved", default = True)
    OnlySaveCustomTextures:   BoolProperty(name="Save Only Custom Textures", description="Only save the labeled texture nodes on a SDK material preset", default = True)

    # Combine Patches conflict resolution
    combine_conflicts: CollectionProperty(type=ConflictItem)

    def get_settings_dict(self):
        dict = {}
        dict["MenuExpanded"] = self.MenuExpanded
        dict["ShowExtras"] = self.ShowExtras
        dict["Force3UVs"] = self.Force3UVs
        dict["Force1Group"] = self.Force1Group
        dict["AutoLods"] = self.AutoLods
        return dict
        
class ListItem(PropertyGroup):
    
    item_name: StringProperty(
        name="Name",
        description = "id",
        default = "0"
    )
    
    item_type: StringProperty(
        name="Type",
        description="type",
        default="0"
    )
    
    item_filter_name: StringProperty(
        name="Filter Name",
        description="Name to use when filtering",
        default=""
    )
    
    item_selected: BoolProperty(
        name="Selected",
        description="Indicates if item is selected",
        default=False
    )
    
    item_visible: BoolProperty(
        name="Visible",
        description="Indicates if item is visible in list",
        default=True
    )
    
class RagdollProperty(PropertyGroup):
    
    weight: FloatProperty(
        name="Weight",
        description="Bone Weight",
        default=0.0
    )
    
    gravity: FloatProperty(
        name="Gravity",
        description="Strength of Gravity",
        default=-9.8
    )
    
    param3: FloatProperty(
        name="Param 3",
        description="Unknown Param",
        default=0
    )
    
    param4: FloatProperty(
        name="Param 4",
        description="Unknown Param",
        default=0
    )
    
    param5: FloatProperty(
        name="Param 5",
        description="Unknown Param",
        default=0
    )
    
    param6: FloatProperty(
        name="Param 6",
        description="Unknown Param",
        default=0
    )
    
    param7: FloatProperty(
        name="Param 7",
        description="Unknown Param",
        default=0
    )
    
    param8: FloatProperty(
        name="Param 8",
        description="Unknown Param",
        default=0
    )
    
    param9: FloatProperty(
        name="Param 9",
        description="Unknown Param",
        default=0
    )
    
class MY_UL_List(UIList):
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            entry_type = int(item.item_type)
            try:
                type_icon = Global_IconDict[entry_type]
            except KeyError:
                type_icon = "QUESTION"
            if entry_type == MaterialID:
                entry = Global_TocManager.GetEntry(int(item.item_name), int(item.item_type))
                if entry and entry.MaterialTemplate:
                    type_icon = "NODE_MATERIAL"
            friendly_name = GetFriendlyNameFromID(int(item.item_name))
            current_list_index = getattr(context.scene, f"index_{item.item_type}")
            op = row.operator("helldiver2.archive_entry", icon=type_icon, text=friendly_name, emboss=item.item_selected, depress=item.item_selected)
            op.list_id = f"list_{item.item_type}" #"active_propname.replace("index", "list").replace("_dummy", "")
            op.list_index = index
            #row.label(text=friendly_name, icon = type_icon, depress=True)
            if entry_type == UnitID:
                row.operator("helldiver2.archive_unit_save", icon='FILE_BLEND', text="").object_id = item.item_name
                # row.operator("helldiver2.save_mesh_baked_textures", icon='RENDER_RESULT', text="")  # Disabled - not ready
                row.operator("helldiver2.archive_unit_import", icon='IMPORT', text="").object_id = item.item_name
            elif entry_type == TexID:
                row.operator("helldiver2.texture_saveblendimage", icon='FILE_BLEND', text="").object_id = item.item_name
                row.operator("helldiver2.texture_import", icon='IMPORT', text="").object_id = item.item_name
            elif entry_type == MaterialID:
                row.operator("helldiver2.material_save", icon='FILE_BLEND', text="").object_id = item.item_name
                row.operator("helldiver2.material_import", icon='IMPORT', text="").object_id = item.item_name
                #row.operator("helldiver2.material_showeditor", icon='MOD_LINEART', text="").object_id = str(Entry.FileID)
                #self.draw_material_editor(Entry, box, row)
            elif entry_type == AnimationID:
                row.operator("helldiver2.archive_animation_import", icon="IMPORT", text="").object_id = item.item_name
            Entry = Global_TocManager.GetEntry(int(item.item_name), int(item.item_type))
            if Entry is None:
                return
            if Global_TocManager.IsInPatch(Entry):
                props = row.operator("helldiver2.archive_removefrompatch", icon='FAKE_USER_ON', text="")
                props.object_id     = item.item_name
                props.object_typeid = item.item_type
            else:
                props = row.operator("helldiver2.archive_addtopatch", icon='FAKE_USER_OFF', text="")
                props.object_id     = item.item_name
                props.object_typeid = item.item_type
            if Entry.IsModified:
                props = row.operator("helldiver2.archive_undo_mod", icon='TRASH', text="")
                props.object_id     = item.item_name
                props.object_typeid = item.item_type
            if Global_TocManager.IsInPatch(Entry) and Global_TocManager.ActiveArchive and not Global_TocManager.ActiveArchive.GetEntry(Entry.FileID, Entry.TypeID):
                props = row.operator("helldiver2.archive_removefrompatch", icon='X', text="")
                props.object_id     = str(Entry.FileID)
                props.object_typeid = str(Entry.TypeID)
        elif self.layout_type in {'GRID'}: 
            layout.alignment = 'CENTER'
            layout.label(text="", icon = "FILE_IMAGE")
            
    def filter_items(self, context, data, propname):
        # Get the filter string from a property, for example
        # Assuming you have a StringProperty named 'filter_string' on your UILIST instance
        list_data = getattr(data, propname)
        flt_flags = []
        flt_neworder = []
        if self.filter_name:
            filter_string = self.filter_name
        else:
            filter_string = getattr(data, propname.replace("list", "filter"))
        if filter_string.startswith("0x"):
            filter_string = str(hex_to_decimal(filter_string))
        flt_flags = bpy.types.UI_UL_list.filter_items_by_name(filter_string, self.bitflag_filter_item, list_data, "item_filter_name")
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(list_data)
        #flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(data, "item_name")
        return flt_flags, flt_neworder

class HellDivers2ToolsPanel(Panel):
    bl_label = f"Helldivers 2 SDK: Community Edition v{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"
    bl_idname = "SF_PT_Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Modding"

    def draw_material_editor(self, Entry, layout, row):
        if Entry.IsLoaded:
            mat = Entry.LoadedData
            for i, t in enumerate(mat.TexIDs):
                row = layout.row(); row.separator(factor=2.0)
                ddsPath = mat.DEV_DDSPaths[i]
                if ddsPath != None: filepath = Path(ddsPath)
                label = filepath.name if ddsPath != None else str(t)
                if Entry.MaterialTemplate != None:
                    label = TextureTypeLookup[Entry.MaterialTemplate][i] + ": " + label
                material_texture_entry = row.operator("helldiver2.material_texture_entry", icon='FILE_IMAGE', text=label, emboss=False)
                material_texture_entry.object_id = str(t)
                material_texture_entry.texture_index = str(i)
                material_texture_entry.material_id = str(Entry.FileID)
                # props = row.operator("helldiver2.material_settex", icon='FILEBROWSER', text="")
                # props.object_id = str(Entry.FileID)
                # props.tex_idx = i
            for i, variable in enumerate(mat.ShaderVariables):
                row = layout.row(); row.separator(factor=2.0)
                split = row.split(factor=0.5)
                row = split.column()
                row.alignment = 'RIGHT'
                name = variable.ID
                if variable.name != "": name = variable.name
                row.label(text=f"{variable.klassName}: {name}", icon='OPTIONS')
                row = split.column()
                row.alignment = 'LEFT'
                sections = len(variable.values)
                if sections == 3: sections = 4 # add an extra for the color picker
                row = row.split(factor=1/sections)
                for j, value in enumerate(variable.values):
                    ShaderVariable = row.operator("helldiver2.material_shader_variable", text=str(round(value, 2)))
                    ShaderVariable.value = value
                    ShaderVariable.object_id = str(Entry.FileID)
                    ShaderVariable.variable_index = i
                    ShaderVariable.value_index = j
                if len(variable.values) == 3:
                    ColorPicker = row.operator("helldiver2.material_shader_variable_color", text="", icon='EYEDROPPER')
                    ColorPicker.object_id = str(Entry.FileID)
                    ColorPicker.variable_index = i

    def draw_state_machine_editor(self, state_machine_entry, bones_entry, layout, row):
        if state_machine_entry.IsLoaded:
            state_machine = state_machine_entry.LoadedData
            i = len(state_machine.layers) - 1
            for i, blend_mask in enumerate(state_machine.blend_masks):
                if f"blend_mask{i}" not in Global_Foldouts:
                    Global_Foldouts[f"blend_mask{i}"] = False
                blend_mask_show = Global_Foldouts[f"blend_mask{i}"]
                row = layout.row()
                split = row.split()
                fold_icon = "DOWNARROW_HLT" if blend_mask_show else "RIGHTARROW"
                sub = split.row(align=True)
                
                sub.operator("helldiver2.collapse_section", text=f"Blend Mask {i}", icon=fold_icon, emboss=False).type = f"blend_mask{i}"
                if blend_mask_show:
                    for j, weight in enumerate(blend_mask.bone_weights):
                        row = layout.row()
                        split = row.split()
                        row.alignment = "CENTER"
                        text=f"Bone {j}: Weight {weight}"
                        if bones_entry and bones_entry.IsLoaded:
                            try:
                                text = f"{bones_entry.LoadedData.Names[j]}"
                            except IndexError:
                                pass
                        split.label(text=text)
                        display_weight = round(weight, 2)
                        op = split.operator("helldiver2.blend_mask_weight", text=f"Weight: {display_weight}")
                        op.object_id = str(state_machine_entry.FileID)
                        op.bone_index = j
                        op.bone_weight = weight
                        op.blend_mask_index = i
                i -= 1

            # draw the values for the bone blend masks for each layer

    def draw_unit_editor(self, Entry, layout):
        """Draw the Unit Editor panel showing all editable unit values"""
        import struct

        if not Entry.IsLoaded:
            return

        mesh_file = Entry.LoadedData
        object_id = str(Entry.FileID)

        # === LOD Thresholds Section ===
        lod_data = mesh_file.UnreversedLODGroupListData
        if lod_data and len(lod_data) >= 4:
            row = layout.row()
            row.label(text=f"LOD Data ({len(lod_data)} bytes)", icon='MOD_DECIM')

            num_floats = len(lod_data) // 4
            floats = struct.unpack(f'<{num_floats}f', lod_data[:num_floats * 4])

            for i, f in enumerate(floats):
                if -1e6 < f < 1e6:
                    row = layout.row()
                    row.separator(factor=2.0)

                    indicator = ""
                    if f == 0.0:
                        indicator = " (always visible)"
                    elif 0.0 < f <= 1.0:
                        indicator = f" ({f*100:.1f}% screen)"

                    split = row.split(factor=0.4)
                    split.label(text=f"LOD[{i}]{indicator}")

                    op = split.operator("helldiver2.unit_lod_value", text=f"{f:.6f}")
                    op.object_id = object_id
                    op.value_index = i
                    op.value = f

            row = layout.row()
            row.separator(factor=2.0)
            row.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text="Set All to 0 (Always Visible)").object_id = object_id

        layout.separator()

        # === UnkHeaderData1 Section ===
        if mesh_file.UnkHeaderData1 and len(mesh_file.UnkHeaderData1) > 0:
            row = layout.row()
            row.label(text=f"UnkHeaderData1 ({len(mesh_file.UnkHeaderData1)} bytes)", icon='FILE_HIDDEN')

            num_floats = len(mesh_file.UnkHeaderData1) // 4
            if num_floats > 0:
                floats = struct.unpack(f'<{num_floats}f', mesh_file.UnkHeaderData1[:num_floats * 4])
                for i, f in enumerate(floats[:16]):  # Limit to first 16
                    if -1e6 < f < 1e6:
                        row = layout.row()
                        row.separator(factor=2.0)
                        split = row.split(factor=0.4)
                        split.label(text=f"Hdr1[{i}]")
                        op = split.operator("helldiver2.unit_header_value", text=f"{f:.6f}")
                        op.object_id = object_id
                        op.field_name = "UnkHeaderData1"
                        op.value_index = i
                        op.value = f

        layout.separator()

        # === MeshInfo Section ===
        if mesh_file.MeshInfoArray:
            row = layout.row()
            row.label(text=f"MeshInfo ({len(mesh_file.MeshInfoArray)} meshes)", icon='MESH_DATA')

            for i, mesh_info in enumerate(mesh_file.MeshInfoArray):
                # Foldout for each mesh
                foldout_key = f"unit_mesh_{object_id}_{i}"
                if foldout_key not in Global_Foldouts:
                    Global_Foldouts[foldout_key] = False

                row = layout.row()
                row.separator(factor=2.0)
                lod_label = f"LOD{mesh_info.LodIndex}" if mesh_info.LodIndex >= 0 else "Main"
                fold_icon = "DOWNARROW_HLT" if Global_Foldouts[foldout_key] else "RIGHTARROW"
                row.operator("helldiver2.collapse_section", text=f"Mesh {i} ({lod_label})", icon=fold_icon, emboss=False).type = foldout_key

                if Global_Foldouts[foldout_key]:
                    col = layout.column()

                    # unk1 (uint64)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="unk1")
                    op = split.operator("helldiver2.unit_meshinfo_uint64", text=f"{mesh_info.unk1} (0x{mesh_info.unk1:016x})")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "unk1"
                    op.value = mesh_info.unk1

                    # unk2 (32 bytes - bounding box)
                    if len(mesh_info.unk2) == 32:
                        floats = struct.unpack('<8f', mesh_info.unk2)
                        row = col.row()
                        row.separator(factor=4.0)
                        split = row.split(factor=0.3)
                        split.label(text="unk2 (bbox)")
                        bbox_text = f"Min({floats[0]:.1f},{floats[1]:.1f},{floats[2]:.1f}) Max({floats[4]:.1f},{floats[5]:.1f},{floats[6]:.1f})"
                        op = split.operator("helldiver2.unit_bbox_value", text=bbox_text)
                        op.object_id = object_id
                        op.mesh_index = i

                    # unk3 (uint32)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="unk3")
                    op = split.operator("helldiver2.unit_meshinfo_uint32", text=f"{mesh_info.unk3} (0x{mesh_info.unk3:08x})")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "unk3"
                    op.value = mesh_info.unk3

                    # unk4 (uint32)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="unk4")
                    op = split.operator("helldiver2.unit_meshinfo_uint32", text=f"{mesh_info.unk4} (0x{mesh_info.unk4:08x})")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "unk4"
                    op.value = mesh_info.unk4

                    # LodIndex (int32)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="LodIndex")
                    op = split.operator("helldiver2.unit_meshinfo_int32", text=f"{mesh_info.LodIndex}")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "LodIndex"
                    op.value = mesh_info.LodIndex

                    # MeshID (uint32)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="MeshID")
                    op = split.operator("helldiver2.unit_meshinfo_uint32", text=f"{mesh_info.MeshID} (0x{mesh_info.MeshID:08x})")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "MeshID"
                    op.value = mesh_info.MeshID

                    # unk6 (40 bytes)
                    if len(mesh_info.unk6) == 40:
                        floats = struct.unpack('<10f', mesh_info.unk6)
                        row = col.row()
                        row.separator(factor=4.0)
                        split = row.split(factor=0.3)
                        split.label(text="unk6 (40B)")
                        op = split.operator("helldiver2.unit_meshinfo_unk6", text=f"[{floats[0]:.2f}, {floats[1]:.2f}, ...]")
                        op.object_id = object_id
                        op.mesh_index = i

                    # unk8 (uint64)
                    row = col.row()
                    row.separator(factor=4.0)
                    split = row.split(factor=0.3)
                    split.label(text="unk8")
                    op = split.operator("helldiver2.unit_meshinfo_uint64", text=f"{mesh_info.unk8} (0x{mesh_info.unk8:016x})")
                    op.object_id = object_id
                    op.mesh_index = i
                    op.field_name = "unk8"
                    op.value = mesh_info.unk8

        # Save button
        layout.separator()
        row = layout.row()
        row.operator("helldiver2.save_unit_data", icon='FILE_BLEND', text="Save Unit Data").object_id = object_id

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        global OnCorrectBlenderVersion
        if not OnCorrectBlenderVersion:
            row.label(text="Using Incorrect Blender Version!")
            row = layout.row()
            row.label(text="Please Use Blender 4.0.X to 4.3.X")
            return
        
        if bpy.app.version[1] > 0:
            row.label(text="Warning! Soft Supported Blender Version. Issues may Occur.", icon='ERROR')


        row = layout.row()
        row.alignment = 'CENTER'
        global Global_addonUpToDate
        global Global_latestAddonVersion
        global Global_gamepathIsValid

        if Global_addonUpToDate == None:
            row.label(text="Addon Failed to Check latest Version")
        elif not Global_addonUpToDate:
            row.label(text="Addon is Outdated!")
            row.label(text=f"Latest Version: {Global_latestAddonVersion}")
            row = layout.row()
            row.alignment = 'CENTER'
            row.scale_y = 2
            row.operator("helldiver2.update", icon = 'URL')
            row.separator()

        # Draw Settings, Documentation and Spreadsheet
        settings_box = layout.box()
        row = settings_box.row()
        row.prop(scene.Hd2ToolPanelSettings, "MenuExpanded",
            icon="DOWNARROW_HLT" if scene.Hd2ToolPanelSettings.MenuExpanded else "RIGHTARROW",
            icon_only=True, emboss=False, text="Settings")
        row.label(icon="SETTINGS")
        
        if scene.Hd2ToolPanelSettings.MenuExpanded or not Global_gamepathIsValid:
            row = settings_box.grid_flow(columns=2)
            row = settings_box.row(); row.separator(); row.label(text="Display Types"); box = row.box(); row = box.grid_flow(columns=1)
            row.prop(scene.Hd2ToolPanelSettings, "ShowExtras")
            row.prop(scene.Hd2ToolPanelSettings, "FriendlyNames")
            row = settings_box.row(); row.separator(); row.label(text="Import Options"); box = row.box(); row = box.grid_flow(columns=1)
            row.prop(scene.Hd2ToolPanelSettings, "ImportMaterials")
            row.prop(scene.Hd2ToolPanelSettings, "ImportLods")
            row.prop(scene.Hd2ToolPanelSettings, "ImportGroup0")
            row.prop(scene.Hd2ToolPanelSettings, "MakeCollections")
            row.prop(scene.Hd2ToolPanelSettings, "ImportCulling")
            row.prop(scene.Hd2ToolPanelSettings, "ImportStatic")
            row.prop(scene.Hd2ToolPanelSettings, "RemoveGoreMeshes")
            row.prop(scene.Hd2ToolPanelSettings, "ParentArmature")
            row.prop(scene.Hd2ToolPanelSettings, "KeepFilediverObjects")
            row.prop(scene.Hd2ToolPanelSettings, "ImportArmature")
            row = settings_box.row(); row.separator(); row.label(text="Export Options"); box = row.box(); row = box.grid_flow(columns=1)
            row.prop(scene.Hd2ToolPanelSettings, "Force3UVs")
            row.prop(scene.Hd2ToolPanelSettings, "Force1Group")
            row.prop(scene.Hd2ToolPanelSettings, "AutoLods")
            row.prop(scene.Hd2ToolPanelSettings, "SaveBonePositions")
            row.prop(scene.Hd2ToolPanelSettings, "SaveTexturesWithMaterial")
            row.prop(scene.Hd2ToolPanelSettings, "GenerateRandomTextureIDs")
            row.prop(scene.Hd2ToolPanelSettings, "OnlySaveCustomTextures")
            row.prop(scene.Hd2ToolPanelSettings, "SplitUVIslands")
            row = settings_box.row(); row.separator(); row.label(text="Other Options"); box = row.box(); row = box.grid_flow(columns=1)
            row.prop(scene.Hd2ToolPanelSettings, "SaveNonSDKMaterials")
            row.prop(scene.Hd2ToolPanelSettings, "SaveUnsavedOnWrite")
            row.prop(scene.Hd2ToolPanelSettings, "AutoSaveUnitMaterials")
            row.prop(scene.Hd2ToolPanelSettings, "PatchBaseArchiveOnly")
            row.prop(scene.Hd2ToolPanelSettings, "LegacyWeightNames")
            row.prop(scene.Hd2ToolPanelSettings, "MergeArmatures")

            #Custom Searching tools
            row = settings_box.row(); row.separator(); row.label(text="Special Tools"); box = row.box(); row = box.grid_flow(columns=1)
            # Draw Bulk Loader Extras
            row.prop(scene.Hd2ToolPanelSettings, "EnableTools")
            if scene.Hd2ToolPanelSettings.EnableTools:
                row = settings_box.row(); box = row.box(); row = box.grid_flow(columns=1)
                #row.label()
                row.label(text="WARNING! Developer Tools, Please Know What You Are Doing!")
                row.prop(scene.Hd2ToolPanelSettings, "UnloadEmptyArchives")
                row.prop(scene.Hd2ToolPanelSettings, "UnloadPatches")
                row.prop(scene.Hd2ToolPanelSettings, "LoadFoundArchives")
                #row.prop(scene.Hd2ToolPanelSettings, "DeleteOnLoadArchive")
                row = box.row()
                row.operator("helldiver2.search_by_entry", icon= 'FILEBROWSER')
                row.operator("helldiver2.bulk_load", icon= 'IMPORT', text="Bulk Load")
                row.operator("helldiver2.search_by_entry_input", icon= 'VIEWZOOM')
                row = box.row()
                row.operator("helldiver2.texture_search", icon= 'TEXTURE', text="Texture Search")
                row.operator("helldiver2.texture_batch_opacity", icon= 'MOD_OPACITY', text="Batch Opacity")
                row = box.row()
                row.operator("helldiver2.fix_ninja_ripper", icon= 'ORIENTATION_GIMBAL', text="Fix Ninja Ripper Imports")
                row.operator("helldiver2.mesh_search", icon= 'MESH_DATA', text="Mesh Search")
                row = box.row()
                row.operator("helldiver2.audit_unit_lod", icon= 'VIEWZOOM', text="Audit Unit LOD Values")
                #row = box.grid_flow(columns=1)
                #row.operator("helldiver2.meshfixtool", icon='MODIFIER')
                search = box.row()
                search.label(text=Global_searchpath)
                search.operator("helldiver2.change_searchpath", icon='FILEBROWSER')
                settings_box.separator()
            row = settings_box.row()
            row.label(text=Global_gamepath)
            row.operator("helldiver2.change_filepath", icon='FILEBROWSER')
            # Filediver path setting
            row = settings_box.row()
            filediver_label = Global_filediverpath if Global_filediverpath else "Filediver: Not Set"
            row.label(text=filediver_label)
            row.operator("helldiver2.change_filediverpath", icon='FILEBROWSER')
            settings_box.separator()

        if not Global_gamepathIsValid:
            row = layout.row()
            row.label(text="Current Selected game filepath to data folder is not valid!")
            row = layout.row()
            row.label(text="Please select your game directory in the settings!")
            return

        # Draw Archive Import/Export Buttons
        row = layout.row(); row = layout.row()
        row.operator("helldiver2.help", icon='HELP', text="Discord")
        row.operator("helldiver2.archive_spreadsheet", icon='INFO', text="Archive IDs")
        row.operator("helldiver2.github", icon='URL', text= "")
        row = layout.row(); row = layout.row()
        row.operator("helldiver2.archive_import_default", icon= 'SOLO_ON', text="")
        row.operator("helldiver2.search_archives", icon= 'VIEWZOOM')
        row.operator("helldiver2.archive_unloadall", icon= 'FILE_REFRESH', text="")
        row = layout.row()
        row.prop(scene.Hd2ToolPanelSettings, "LoadedArchives", text="Archives")
        if scene.Hd2ToolPanelSettings.EnableTools:
            row.scale_x = 0.33
            ArchiveNum = "0/0"
            if Global_TocManager.ActiveArchive != None:
                Archiveindex = Global_TocManager.LoadedArchives.index(Global_TocManager.ActiveArchive) + 1
                Archiveslength = len(Global_TocManager.LoadedArchives)
                ArchiveNum = f"{Archiveindex}/{Archiveslength}"
            row.operator("helldiver2.next_archive", icon= 'RIGHTARROW', text=ArchiveNum)
            row.scale_x = 1
        row.operator("helldiver2.archives_import_manual", icon= 'VIEWZOOM', text= "")
        row.operator("helldiver2.archive_import", icon= 'FILEBROWSER', text= "").is_patch = False
        row = layout.row()
        #if len(Global_TocManager.LoadedArchives) > 0:
        #    Global_TocManager.SetActiveByName(scene.Hd2ToolPanelSettings.LoadedArchives)


        # Draw Patch Stuff
        row = layout.row(); row = layout.row()

        row.operator("helldiver2.archive_createpatch", icon= 'COLLECTION_NEW', text="New Patch")
        row.operator("helldiver2.archive_export", icon= 'DISC', text="Write Patch")
        row.operator("helldiver2.export_patch", icon= 'EXPORT')
        row.operator("helldiver2.patches_unloadall", icon= 'FILE_REFRESH', text="")

        row = layout.row()
        row.prop(scene.Hd2ToolPanelSettings, "Patches", text="Patches")
        #if len(Global_TocManager.Patches) > 0:
        #    Global_TocManager.SetActivePatchByName(scene.Hd2ToolPanelSettings.Patches)
        row.operator("helldiver2.rename_patch", icon='GREASEPENCIL', text="")
        row.operator("helldiver2.archive_import", icon= 'FILEBROWSER', text="").is_patch = True

        # Patch utility buttons
        row = layout.row()
        row.operator("helldiver2.combine_patches", icon='AUTOMERGE_ON', text="Combine Patches")
        row.operator("helldiver2.repatch_mod", icon='FILE_REFRESH', text="Repatch Units")
        row.operator("helldiver2.repatch_folder", icon='FILE_FOLDER', text="Repatch Folder")

        # Draw Archive Contents
        
        #contents_header, contents_panel = layout.panel("hd2_panel_archive_contents", default_closed=False)
        contents_header = layout.row()
        
        title = "No Archive Loaded"
        if Global_TocManager.ActiveArchive != None:
            ArchiveID = Global_TocManager.ActiveArchive.Name
            name = GetArchiveNameFromID(ArchiveID)
            title = f"{name}    ID: {ArchiveID}"
        if Global_TocManager.ActivePatch != None and scene.Hd2ToolPanelSettings.PatchOnly:
            name = Global_TocManager.ActivePatch.Name
            title = f"Patch: {name}    File: {Global_TocManager.ActivePatch.Name}"
            
        #contents_header.label(text=title)
        contents_header.prop(scene.Hd2ToolPanelSettings, "ContentsExpanded",
            icon="DOWNARROW_HLT" if scene.Hd2ToolPanelSettings.ContentsExpanded else "RIGHTARROW",
            icon_only=True, emboss=False, text=title)
        contents_header.prop(scene.Hd2ToolPanelSettings, "PatchOnly", text="")
        contents_header.operator("helldiver2.copy_archive_id", icon='COPY_ID', text="")
        contents_header.operator("helldiver2.archive_object_dump_import_by_id", icon='PACKAGE', text="")
        
        #if not contents_panel:
        #    return
        #layout = contents_panel


        # Get Display Data
        DisplayData = GetDisplayData()
        DisplayTocEntries = DisplayData[0]
        DisplayTocTypes   = DisplayData[1]

        # Draw Contents
        NewFriendlyNames = []
        NewFriendlyIDs = []
        if not scene.Hd2ToolPanelSettings.ContentsExpanded: return
        if len(DisplayTocEntries) == 0: return

        # Draw Search Bar
        row = layout.row(); #row = layout.row()
        row.prop(scene.Hd2ToolPanelSettings, "SearchField", icon='VIEWZOOM', text="")
        global Global_Foldouts
        for Type in sorted(DisplayTocTypes, key=lambda e: e.TypeID):
            ui_list = getattr(scene, f"list_{Type.TypeID}")
            if len(ui_list) == 0:
                continue
            if not ui_list[0].item_visible:
                continue
            if Global_Foldouts.get(str(Type.TypeID), None) is None: # move to only init these keys once
                fold = Type.TypeID in [MaterialID, TexID, UnitID]
                Global_Foldouts[str(Type.TypeID)] = fold
            show = Global_Foldouts.get(str(Type.TypeID), False)
            fold_icon = "DOWNARROW_HLT" if show else "RIGHTARROW"
            # Get Type Icon
            type_icon = 'FILE'
            showExtras = scene.Hd2ToolPanelSettings.ShowExtras
            if not showExtras and Type.TypeID not in [AnimationID, ParticleID, UnitID, TexID, MaterialID, StateMachineID]:
                continue
            try:
                type_icon = Global_IconDict[Type.TypeID]
            except KeyError:
                type_icon = "QUESTION"
            if len(getattr(context.scene, f"list_{Type.TypeID}")) == 0:
                continue
                
            # Draw Type Header
            box = layout.box(); row = box.row()
            typeName = GetTypeNameFromID(Type.TypeID)
            split = row.split()
            
            sub = split.row(align=True)
            sub.operator("helldiver2.collapse_section", text=f"{typeName}: {str(Type.TypeID)}", icon=fold_icon, emboss=False).type = str(Type.TypeID)

            # Skip drawling entries if section hidden
            if not show: 
                sub.label(icon=type_icon)
                continue
            
            #sub.operator("helldiver2.import_type", icon='IMPORT', text="").object_typeid = str(Type.TypeID)
            sub.operator("helldiver2.select_type", icon='RESTRICT_SELECT_OFF', text="").list_id = f"list_{Type.TypeID}"
            # Draw Add Material Button
            
            if typeName == "material": sub.operator("helldiver2.material_add", icon='FILE_NEW', text="")
            # Draw Type Body
            if show:
                box.template_list("MY_UL_List", f"list_{Type.TypeID}", scene, f"list_{Type.TypeID}", scene, f"index_{Type.TypeID}_dummy", rows=10)
                if Type.TypeID == StateMachineID:
                    if "state_machine_editor" not in Global_Foldouts: # move to only init keys once
                        Global_Foldouts["state_machine_editor"] = False
                    state_machine_editor_show = Global_Foldouts["state_machine_editor"]
                    row = box.box()
                    split = row.split()
                    fold_icon = "DOWNARROW_HLT" if state_machine_editor_show else "RIGHTARROW"
                    sub = split.row(align=True)
                    
                    header_label = "State Machine Editor"
                    mat_item = None
                    if state_machine_editor_show:
                        mat_list = getattr(context.scene, f"list_{Type.TypeID}")
                        mat_index = getattr(context.scene, f"index_{Type.TypeID}")
                        if mat_index < len(mat_list):
                            mat_item = mat_list[mat_index]
                            Entry = Global_TocManager.GetEntry(int(mat_item.item_name), int(mat_item.item_type), SearchAll=True, IgnorePatch=False)
                            BonesEntry = Global_TocManager.GetEntry(int(mat_item.item_name), BoneID, SearchAll=True, IgnorePatch=False)
                            if Entry:
                                if not Entry.IsLoaded:
                                    Entry.Load(True, False)
                                if BonesEntry:
                                    if not BonesEntry.IsLoaded:
                                        BonesEntry.Load(True, False)
                                self.draw_state_machine_editor(Entry, BonesEntry, row.row().column(align=True), None)
                                header_label = f"State Machine Editor: {mat_item.item_name}"
                    sub.operator("helldiver2.collapse_section", text=header_label, icon=fold_icon, emboss=False).type = "state_machine_editor"
                    if state_machine_editor_show and mat_item: sub.operator("helldiver2.state_machine_save", icon='FILE_BLEND', text="").object_id = mat_item.item_name
                    #if material_editor_show and mat_item: sub.operator("helldiver2.material_save", icon='FILE_BLEND', text="").object_id = mat_item.item_name
                    # add operator to save state machine
                if Type.TypeID == UnitID:
                    # draw unit editor
                    if "unit_editor" not in Global_Foldouts:
                        Global_Foldouts["unit_editor"] = False
                    unit_editor_show = Global_Foldouts["unit_editor"]
                    row = box.box()
                    split = row.split()
                    fold_icon = "DOWNARROW_HLT" if unit_editor_show else "RIGHTARROW"
                    sub = split.row(align=True)

                    header_label = "Unit Editor"
                    unit_item = None
                    if unit_editor_show:
                        unit_list = getattr(context.scene, f"list_{Type.TypeID}")
                        unit_index = getattr(context.scene, f"index_{Type.TypeID}")
                        if unit_index < len(unit_list):
                            unit_item = unit_list[unit_index]
                            Entry = Global_TocManager.GetEntry(int(unit_item.item_name), int(unit_item.item_type))
                            if Entry:
                                if not Entry.IsLoaded:
                                    Entry.Load(True, False, True)
                                self.draw_unit_editor(Entry, row.row().column(align=True))
                                header_label = f"Unit Editor: {unit_item.item_name}"
                    sub.operator("helldiver2.collapse_section", text=header_label, icon=fold_icon, emboss=False).type = "unit_editor"
                    if unit_editor_show and unit_item:
                        sub.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text="").object_id = unit_item.item_name
                if Type.TypeID == MaterialID:
                    # draw material editor
                    if "material_editor" not in Global_Foldouts: # move to only init this key once
                        Global_Foldouts["material_editor"] = False
                    material_editor_show = Global_Foldouts["material_editor"]
                    row = box.box()
                    split = row.split()
                    fold_icon = "DOWNARROW_HLT" if material_editor_show else "RIGHTARROW"
                    sub = split.row(align=True)
                    
                    #material_editor_body = row.column()
                    #material_editor_header, material_editor_panel = panel_body.panel(f"hd2_panel_material_editor", default_closed=True)
                    header_label = "Material Editor"
                    mat_item = None
                    if material_editor_show:
                        mat_list = getattr(context.scene, f"list_{Type.TypeID}")
                        mat_index = getattr(context.scene, f"index_{Type.TypeID}")
                        if mat_index < len(mat_list):
                            mat_item = mat_list[mat_index]
                            Entry = Global_TocManager.GetEntry(int(mat_item.item_name), int(mat_item.item_type))
                            if Entry:
                                if not Entry.IsLoaded:
                                    Entry.Load(True, False)
                                self.draw_material_editor(Entry, row.row().column(align=True), None)
                                header_label = f"Material Editor: {mat_item.item_name}"
                    sub.operator("helldiver2.collapse_section", text=header_label, icon=fold_icon, emboss=False).type = "material_editor"
                    if material_editor_show and mat_item: sub.operator("helldiver2.material_save", icon='FILE_BLEND', text="").object_id = mat_item.item_name
        if scene.Hd2ToolPanelSettings.FriendlyNames:  
            Global_TocManager.SavedFriendlyNames = NewFriendlyNames
            Global_TocManager.SavedFriendlyNameIDs = NewFriendlyIDs

class WM_MT_button_context(Menu):
    bl_label = "Entry Context Menu"

    def draw_entry_buttons(row, Entry):
        if not Entry.IsSelected:
            Global_TocManager.SelectEntries([Entry])

        # Combine entry strings to be passed to operators
        FileIDStr = ""
        TypeIDStr = ""
        for SelectedEntry in Global_TocManager.SelectedEntries:
            FileIDStr += str(SelectedEntry.FileID)+","
            TypeIDStr += str(SelectedEntry.TypeID)+","
        # Get common class
        AreAllUnits    = True
        AreAllTextures  = True
        AreAllMaterials = True
        AreAllParticles = True
        SingleEntry = True
        NumSelected = len(Global_TocManager.SelectedEntries)
        if len(Global_TocManager.SelectedEntries) > 1:
            SingleEntry = False
        for SelectedEntry in Global_TocManager.SelectedEntries:
            if SelectedEntry.TypeID == UnitID:
                AreAllTextures = False
                AreAllMaterials = False
                AreAllParticles = False
            elif SelectedEntry.TypeID == TexID:
                AreAllUnits = False
                AreAllMaterials = False
                AreAllParticles = False
            elif SelectedEntry.TypeID == MaterialID:
                AreAllTextures = False
                AreAllUnits = False
                AreAllParticles = False
            elif SelectedEntry.TypeID == ParticleID:
                AreAllTextures = False
                AreAllUnits = False
                AreAllMaterials = False
            else:
                AreAllUnits = False
                AreAllTextures = False
                AreAllMaterials = False
                AreAllParticles = False
        
        RemoveFromPatchName = "Remove From Patch" if SingleEntry else f"Remove {NumSelected} From Patch"
        AddToPatchName = "Add To Patch" if SingleEntry else f"Add {NumSelected} To Patch"
        ImportUnitName = "Import Unit" if SingleEntry else f"Import {NumSelected} Units"
        ImportTextureName = "Import Texture" if SingleEntry else f"Import {NumSelected} Textures"
        ImportMaterialName = "Import Material" if SingleEntry else f"Import {NumSelected} Materials"
        ImportParticleName = "Import Particle" if SingleEntry else f"Import {NumSelected} Particles"
        DumpObjectName = "Export Object Dump" if SingleEntry else f"Export {NumSelected} Object Dumps"
        ImportDumpObjectName = "Import Object Dump" if SingleEntry else f"Import {NumSelected} Object Dumps"
        SaveTextureName = "Save Blender Texture" if SingleEntry else f"Save Blender {NumSelected} Textures"
        SaveMaterialName = "Save Material" if SingleEntry else f"Save {NumSelected} Materials"
        SaveParticleName = "Save Particle" if SingleEntry else f"Save {NumSelected} Particles"
        UndoName = "Undo Modifications" if SingleEntry else f"Undo {NumSelected} Modifications"
        CopyName = "Copy Entry" if SingleEntry else f"Copy {NumSelected} Entries"
        
        # Draw seperator
        row.separator()
        row.label(text=Global_SectionHeader)

        # Draw copy button
        row.separator()
        props = row.operator("helldiver2.archive_copy", icon='COPYDOWN', text=CopyName)
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        if len(Global_TocManager.CopyBuffer) != 0:
            row.operator("helldiver2.archive_paste", icon='PASTEDOWN', text="Paste "+str(len(Global_TocManager.CopyBuffer))+" Entries")
            row.operator("helldiver2.archive_clearclipboard", icon='TRASH', text="Clear Clipboard")
        if SingleEntry:
            props = row.operator("helldiver2.archive_duplicate", icon='DUPLICATE', text="Duplicate Entry")
            props.object_id     = str(Entry.FileID)
            props.object_typeid = str(Entry.TypeID)
        
        if Global_TocManager.IsInPatch(Entry):
            props = row.operator("helldiver2.archive_removefrompatch", icon='X', text=RemoveFromPatchName)
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr
        else:
            props = row.operator("helldiver2.archive_addtopatch", icon='PLUS', text=AddToPatchName)
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr

        # Draw import buttons
        # TODO: Add generic import buttons
        row.separator()
        if AreAllUnits:
            row.operator("helldiver2.archive_unit_import", icon='IMPORT', text=ImportUnitName).object_id = FileIDStr
            if Global_filediverpathIsValid:
                row.operator("helldiver2.import_mesh_with_shader", icon='SHADING_RENDERED', text="With Shader").object_id = FileIDStr
        elif AreAllTextures:
            row.operator("helldiver2.texture_import", icon='IMPORT', text=ImportTextureName).object_id = FileIDStr
        elif AreAllMaterials:
            row.operator("helldiver2.material_import", icon='IMPORT', text=ImportMaterialName).object_id = FileIDStr
        #elif AreAllParticles:
            #row.operator("helldiver2.archive_particle_import", icon='IMPORT', text=ImportParticleName).object_id = FileIDStr
        # Draw export buttons
        row.separator()

        props = row.operator("helldiver2.archive_object_dump_import", icon='PACKAGE', text=ImportDumpObjectName)
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        props = row.operator("helldiver2.archive_object_dump_export", icon='PACKAGE', text=DumpObjectName)
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        # Draw dump import button
        # if AreAllMaterials and SingleEntry: row.operator("helldiver2.archive_object_dump_import", icon="IMPORT", text="Import Raw Dump").object_id = FileIDStr
        # Draw save buttons
        row.separator()
        if AreAllUnits:
            if SingleEntry:
                row.operator("helldiver2.archive_unit_save", icon='FILE_BLEND', text="Save Unit").object_id = str(Entry.FileID)
                # row.operator("helldiver2.save_mesh_baked_textures", icon='RENDER_RESULT', text="Bake & Save")  # Disabled - not ready
                row.operator("helldiver2.override_all_helmets", icon='MOD_CLOTH', text="Override All Helmets").object_id = str(Entry.FileID)
                row.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text="Always Visible").object_id = str(Entry.FileID)
            else:
              row.operator("helldiver2.archive_unit_batchsave", icon='FILE_BLEND', text=f"Save {NumSelected} Units")
              row.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text=f"Always Visible ({NumSelected})").object_id = FileIDStr
              # row.operator("helldiver2.save_mesh_baked_textures", icon='RENDER_RESULT', text="Bake & Save")  # Disabled - not ready
        elif AreAllTextures:
            row.operator("helldiver2.texture_saveblendimage", icon='FILE_BLEND', text=SaveTextureName).object_id = FileIDStr
            row.separator()
            row.operator("helldiver2.texture_savefromdds", icon='FILE_IMAGE', text=f"Import {NumSelected} DDS Textures").object_id = FileIDStr
            row.operator("helldiver2.texture_savefrompng", icon='FILE_IMAGE', text=f"Import {NumSelected} PNG Textures").object_id = FileIDStr
            row.separator()
            row.operator("helldiver2.texture_batchexport", icon='OUTLINER_OB_IMAGE', text=f"Export {NumSelected} DDS Textures").object_id = FileIDStr
            row.operator("helldiver2.texture_batchexport_png", icon='OUTLINER_OB_IMAGE', text=f"Export {NumSelected} PNG Textures").object_id = FileIDStr
        elif AreAllMaterials:
            row.operator("helldiver2.material_save", icon='FILE_BLEND', text=SaveMaterialName).object_id = FileIDStr
            if SingleEntry:
                row.operator("helldiver2.material_set_template", icon='MATSHADERBALL').entry_id = str(Entry.FileID)
                if Entry.LoadedData != None:
                    row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Parent Material Entry ID").text = str(Entry.LoadedData.ParentMaterialID)
        #elif AreAllParticles:
            #row.operator("helldiver2.particle_save", icon='FILE_BLEND', text=SaveParticleName).object_id = FileIDStr
        # Draw copy ID buttons
        if SingleEntry:
            row.separator()
            row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry ID").text = str(Entry.FileID)
            row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry Hex ID").text = str(hex(Entry.FileID))
            row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Type ID").text  = str(Entry.TypeID)
            row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Friendly Name").text  = GetFriendlyNameFromID(Entry.FileID)
            if Global_TocManager.IsInPatch(Entry):
                props = row.operator("helldiver2.archive_entryrename", icon='TEXT', text="Rename")
                props.object_id     = str(Entry.FileID)
                props.object_typeid = str(Entry.TypeID)
        if Entry.IsModified:
            row.separator()
            props = row.operator("helldiver2.archive_undo_mod", icon='TRASH', text=UndoName)
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr

        if SingleEntry:
            row.operator("helldiver2.archive_setfriendlyname", icon='WORDWRAP_ON', text="Set Friendly Name").object_id = str(Entry.FileID)
            
    def draw_material_editor_context_buttons(layout, FileID, MaterialID, TextureIndex):
        row = layout
        row.separator()
        row.label(text=Global_SectionHeader)
        row.separator()
        row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry ID").text = str(FileID)
        row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry Hex ID").text = str(hex(int(FileID)))
        row.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Type ID").text  = str(TexID)
        props = row.operator("helldiver2.archive_entryrename", icon='TEXT', text="Rename")
        props.object_id     = str(FileID)
        props.object_typeid = str(TexID)
        props.material_id = str(MaterialID)
        props.texture_index = str(TextureIndex)
        
    def draw_ui_list_buttons(layout, _list, list_item):
        selected_items = [item for item in _list if item.item_selected]
        FileIDStr = ",".join([item.item_name for item in selected_items])
        TypeIDStr = ",".join([item.item_type for item in selected_items])
        item_type = int(list_item.item_type)
        item_typename = GetTypeNameFromID(item_type)
        entry_string = "Entry" if len(selected_items) == 1 else "Entries"
        Entry = Global_TocManager.GetEntry(int(list_item.item_name), int(list_item.item_type))
        
        layout.separator()
        layout.label(text=Global_SectionHeader)

        # Draw copy buttons
        layout.separator()
        props = layout.operator("helldiver2.archive_copy", icon='COPYDOWN', text=f"Copy {len(selected_items)} Entr{'ies' if len(selected_items) > 1 else 'y'}")
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        if len(Global_TocManager.CopyBuffer) != 0:
            layout.operator("helldiver2.archive_paste", icon='PASTEDOWN', text="Paste "+str(len(Global_TocManager.CopyBuffer))+" Entries")
            layout.operator("helldiver2.archive_clearclipboard", icon='TRASH', text="Clear Clipboard")
        if len(selected_items) == 1:
            props = layout.operator("helldiver2.archive_duplicate", icon='DUPLICATE', text="Duplicate Entry")
            props.object_id     = list_item.item_name
            props.object_typeid = list_item.item_type
        if Global_TocManager.ActivePatch and Global_TocManager.ActivePatch.GetEntry(int(list_item.item_name), int(list_item.item_type)):
            props = layout.operator("helldiver2.archive_removefrompatch", icon='X', text=f"Remove {len(selected_items)} {entry_string} From Patch")
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr
        else:
            props = layout.operator("helldiver2.archive_addtopatch", icon='PLUS', text=f"Add {len(selected_items)} {entry_string} To Patch")
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr

        # Draw import buttons
        # TODO: Add generic import buttons
        layout.separator()
        if item_type == UnitID:
            layout.operator("helldiver2.archive_unit_import", icon='IMPORT', text=f"Import {len(selected_items)} Mesh{'es' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            if Global_filediverpathIsValid:
                layout.operator("helldiver2.import_mesh_with_shader", icon='SHADING_RENDERED', text=f"Import {len(selected_items)} Mesh{'es' if len(selected_items) > 1 else ''} with Shader").object_id = FileIDStr
        elif item_type == TexID:      layout.operator("helldiver2.texture_import",      icon='IMPORT', text=f"Import {len(selected_items)} Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
        elif item_type == MaterialID: layout.operator("helldiver2.material_import",     icon='IMPORT', text=f"Import {len(selected_items)} Material{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
        #elif AreAllParticles:
            #layout.operator("helldiver2.archive_particle_import", icon='IMPORT', text=ImportParticleName).object_id = FileIDStr
            
        # Draw export buttons
        layout.separator()
        props = layout.operator("helldiver2.archive_object_dump_import", icon='PACKAGE', text=f"Import {len(selected_items)} Object Dump{'s' if len(selected_items) > 1 else ''}")
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        props = layout.operator("helldiver2.archive_object_dump_export", icon='PACKAGE', text=f"Export {len(selected_items)} Object Dump{'s' if len(selected_items) > 1 else ''}")
        props.object_id     = FileIDStr
        props.object_typeid = TypeIDStr
        # Draw dump import button
        # if AreAllMaterials and SingleEntry: layout.operator("helldiver2.archive_object_dump_import", icon="IMPORT", text="Import Raw Dump").object_id = FileIDStr
        # Draw save buttons
        layout.separator()
        if item_type == UnitID:
            if len(selected_items) == 1:
                layout.operator("helldiver2.archive_unit_save", icon='FILE_BLEND', text="Save Mesh").object_id = list_item.item_name
                # layout.operator("helldiver2.save_mesh_baked_textures", icon='RENDER_RESULT', text="Bake & Save")  # Disabled - not ready
                layout.operator("helldiver2.override_all_helmets", icon='MOD_CLOTH', text="Override All Helmets").object_id = list_item.item_name
                layout.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text="Always Visible").object_id = list_item.item_name
            else:
                layout.operator("helldiver2.archive_unit_batchsave", icon='FILE_BLEND', text=f"Save {len(selected_items)} Meshes")
                layout.operator("helldiver2.make_always_visible", icon='HIDE_OFF', text=f"Always Visible ({len(selected_items)})").object_id = FileIDStr
                # layout.operator("helldiver2.save_mesh_baked_textures", icon='RENDER_RESULT', text="Bake & Save")  # Disabled - not ready
        elif item_type == TexID:
            layout.operator("helldiver2.texture_saveblendimage", icon='FILE_BLEND', text=f"Save {len(selected_items)} Blender Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            layout.separator()
            layout.operator("helldiver2.texture_savefromdds", icon='FILE_IMAGE', text=f"Import {len(selected_items)} DDS Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            layout.operator("helldiver2.texture_savefrompng", icon='FILE_IMAGE', text=f"Import {len(selected_items)} PNG Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            layout.separator()
            layout.operator("helldiver2.texture_batchexport", icon='OUTLINER_OB_IMAGE', text=f"Export {len(selected_items)} DDS Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            layout.operator("helldiver2.texture_batchexport_png", icon='OUTLINER_OB_IMAGE', text=f"Export {len(selected_items)} PNG Texture{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
        elif item_type == MaterialID:
            layout.operator("helldiver2.material_save", icon='FILE_BLEND', text=f"Save {len(selected_items)} Material{'s' if len(selected_items) > 1 else ''}").object_id = FileIDStr
            if len(selected_items) == 1:
                if Entry and Entry.LoadedData:
                    layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Parent Material Entry ID").text = str(Entry.LoadedData.ParentMaterialID)
            #if SingleEntry:
            #    layout.operator("helldiver2.material_set_template", icon='MATSHADERBALL').entry_id = str(Entry.FileID)
            #    if Entry.LoadedData != None:
            #        layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Parent Material Entry ID").text = str(Entry.LoadedData.ParentMaterialID)
        #elif AreAllParticles:
            #layout.operator("helldiver2.particle_save", icon='FILE_BLEND', text=SaveParticleName).object_id = FileIDStr
        # Draw copy ID buttons
        if len(selected_items) == 1:
            layout.separator()
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry ID").text = list_item.item_name
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry Hex ID").text = str(hex(int(list_item.item_name)))
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Type ID").text  = list_item.item_type
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Friendly Name").text  = GetFriendlyNameFromID(int(list_item.item_name))
            if Global_TocManager.IsInPatch(Entry):
                props = layout.operator("helldiver2.archive_entryrename", icon='TEXT', text="Rename")
                props.object_id     = list_item.item_name
                props.object_typeid = list_item.item_type
        else:
            layout.separator()
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry ID").text = ",".join([item.item_name for item in selected_items])
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Entry Hex ID").text = ",".join([str(hex(int(item.item_name))) for item in selected_items])
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Type ID").text  = list_item.item_type
            layout.operator("helldiver2.copytest", icon='COPY_ID', text="Copy Friendly Name").text  = GetFriendlyNameFromID(int(list_item.item_name))
        if Entry.IsModified:
            layout.separator()
            props = layout.operator("helldiver2.archive_undo_mod", icon='TRASH', text=f"Undo {len(selected_items)} Modification{'s' if len(selected_items) > 1 else ''}")
            props.object_id     = FileIDStr
            props.object_typeid = TypeIDStr

        if len(selected_items) == 1:
            layout.operator("helldiver2.archive_setfriendlyname", icon='WORDWRAP_ON', text="Set Friendly Name").object_id = list_item.item_name
        
    def draw(self, context):
        value = getattr(context, "button_operator", None)
        menuName = type(value).__name__
        if menuName == "HELLDIVER2_OT_archive_entry":
            layout = self.layout
            list_index = getattr(value, "list_index")
            list_id = getattr(value, "list_id")
            _list = getattr(context.scene, list_id)
            list_item = _list[list_index]
            WM_MT_button_context.draw_ui_list_buttons(layout, _list, list_item)
        elif menuName == "HELLDIVER2_OT_material_texture_entry":
            layout = self.layout
            FileID = getattr(value, "object_id")
            MaterialID = getattr(value, "material_id")
            TextureIndex = getattr(value, "texture_index")
            WM_MT_button_context.draw_material_editor_context_buttons(layout, FileID, MaterialID, TextureIndex)
        elif menuName == "":
            layout = self.layout
            FileID = getattr(value, "object_id")
            TypeID = getattr(value, "object_typeid")
            WM_MT_button_context.draw_entry_buttons(layout, Global_TocManager.GetEntry(int(FileID), int(TypeID)))
            

#endregion

classes = (
    LoadArchiveOperator,
    PatchArchiveOperator,
    ImportStingrayUnitOperator,
    SaveStingrayUnitOperator,
    UnitLodValueOperator,
    UnitBboxValueOperator,
    UnitHeaderValueOperator,
    UnitMeshInfoUint32Operator,
    UnitMeshInfoInt32Operator,
    UnitMeshInfoUint64Operator,
    UnitMeshInfoUnk6Operator,
    MakeUnitAlwaysVisibleOperator,
    SaveUnitDataOperator,
    AuditUnitLodValuesOperator,
    ImportStingrayAnimationOperator,
    SaveStingrayAnimationOperator,
    ImportMaterialOperator,
    ImportTextureOperator,
    ExportTextureOperator,
    DumpArchiveObjectOperator,
    ImportDumpOperator,
    ConflictItem,
    Hd2ToolPanelSettings,
    HellDivers2ToolsPanel,
    UndoArchiveEntryModOperator,
    AddMaterialOperator,
    SaveMaterialOperator,
    SaveTextureFromBlendImageOperator,
    ShowMaterialEditorOperator,
    SetMaterialTexture,
    SearchArchivesOperator,
    LoadArchivesOperator,
    CopyArchiveEntryOperator,
    PasteArchiveEntryOperator,
    ClearClipboardOperator,
    SaveTextureFromDDSOperator,
    HelpOperator,
    ArchiveSpreadsheetOperator,
    UnloadArchivesOperator,
    ArchiveEntryOperator,
    CreatePatchFromActiveOperator,
    AddEntryToPatchOperator,
    RemoveEntryFromPatchOperator,
    CopyTextOperator,
    BatchExportTextureOperator,
    BatchSaveStingrayUnitOperator,
    OverrideAllHelmetsOperator,
    SelectAllOfTypeOperator,
    RenamePatchEntryOperator,
    DuplicateEntryOperator,
    SetEntryFriendlyNameOperator,
    DefaultLoadArchiveOperator,
    BulkLoadOperator,
    FixNinjaRipperOperator,
    ImportAllOfTypeOperator,
    UnloadPatchesOperator,
    GithubOperator,
    ChangeFilepathOperator,
    CopyCustomPropertyOperator,
    PasteCustomPropertyOperator,
    CopyArchiveIDOperator,
    ExportPatchAsZipOperator,
    CombinePatchesOperator,
    RepatchModOperator,
    RepatchFolderOperator,
    RenamePatchOperator,
    NextArchiveOperator,
    MaterialTextureEntryOperator,
    EntrySectionOperator,
    SaveTextureFromPNGOperator,
    SearchByEntryIDOperator,
    ChangeSearchpathOperator,
    ChangeFilediverPathOperator,
    ImportMeshWithShaderOperator,
    SaveMeshWithBakedTexturesOperator,
    ExportTexturePNGOperator,
    BatchExportTexturePNGOperator,
    TextureSearchOperator,
    BatchOpacityPatchOperator,
    MeshSearchOperator,
    CopyDecimalIDOperator,
    CopyHexIDOperator,
    GenerateEntryIDOperator,
    SetMaterialTemplateOperator,
    LatestReleaseOperator,
    AutoUpdateOperator,
    MaterialShaderVariableEntryOperator,
    MaterialShaderVariableColorEntryOperator,
    MeshFixOperator,
    ImportStingrayParticleOperator,
    SaveStingrayParticleOperator,
    ImportDumpByIDOperator,
    SearchByEntryIDInput,
    ManuallyLoadArchivesOperator,
    SetBoneAnimatedOperator,
    SearchArmatureAnimationsOperator,
    StateMachineBlendMaskWeightOperator,
    StateMachineSaveOperator,
    SetBoneRagdollOperator,
    AddLightOperator,
)

Global_TocManager = TocManager()

class DotDict(dict):
        
    def __getattr__(self, name):
        return dict.__getitem__(self, name)
        
    def __setattr__(self, name, value):
        dict.__setitem__(self, name, value)
    
def SetSelected(t):
    def wrapper(scene, value):
        scene[f"index_{t}_dummy"] = 5000000
    return wrapper


def register():
    if not os.path.exists(Global_texconvpath): raise Exception("Texconv is not found, please install Texconv in /deps/")
    CheckBlenderVersion()
    CheckAddonUpToDate()
    InitializeConfig()
    UpdateArchiveHashes()
    LoadTypeHashes()
    LoadNameHashes()
    LoadArchiveHashes()
    LoadShaderVariables(Global_variablespath)
    LoadBoneHashes(Global_bonehashpath, Global_BoneNames)
    for cls in classes:
        bpy.utils.register_class(cls)
    Scene.Hd2ToolPanelSettings = PointerProperty(type=Hd2ToolPanelSettings)
    bpy.utils.register_class(WM_MT_button_context)
    bpy.types.VIEW3D_MT_object_context_menu.append(CustomPropertyContext)
    bpy.types.VIEW3D_MT_armature_context_menu.append(CustomBoneContext)
    bpy.utils.register_class(MY_UL_List)
    bpy.utils.register_class(ListItem)
    for t in Global_TypeIDs: # make all this into an item in another collection property
        setattr(bpy.types.Scene, f"list_{t}", CollectionProperty(type = ListItem))
        setattr(bpy.types.Scene, f"index_{t}", IntProperty(name = f"index_{t}", default = 0))
        setattr(bpy.types.Scene, f"filter_{t}", StringProperty(name = f"filter_{t}", default = ""))
        setattr(bpy.types.Scene, f"index_{t}_dummy", IntProperty(name = f"index_{t}_dummy", default = 5000000, set=SetSelected(t)))
    bpy.types.Scene.new_id_entry = StringProperty(name="new_id_entry", default="")

def unregister():
    bpy.utils.unregister_class(WM_MT_button_context)
    del Scene.Hd2ToolPanelSettings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.types.VIEW3D_MT_object_context_menu.remove(CustomPropertyContext)
    bpy.types.VIEW3D_MT_armature_context_menu.remove(CustomBoneContext)
    for t in Global_TypeIDs:
        delattr(bpy.types.Scene, f"list_{t}")
        delattr(bpy.types.Scene, f"index_{t}")
    bpy.utils.unregister_class(MY_UL_List)
    bpy.utils.unregister_class(ListItem)

if __name__=="__main__":
    register()
