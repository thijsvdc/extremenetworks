'''
This script is provided free of charge by Extreme. We hope such scripts are
helpful when used in conjunction with Extreme products and technology and can
be used as examples to modify and adapt for your ultimate requirements.
Extreme will not provide any official support for these scripts. If you do
have any questions or queries about any of these scripts you may post on
Extreme's community website "The Hub" (https://community.extremenetworks.com/)
under the scripting category.

ANY SCRIPTS PROVIDED BY EXTREME ARE HEREBY PROVIDED "AS IS", WITHOUT WARRANTY
OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL EXTREME OR ITS THIRD PARTY LICENSORS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE USE OR DISTRIBUTION OF SUCH
SCRIPTS.
'''

# --> Insert here script description, version and metadata <--

##########################################################################################
# XMC Script: Change mgmt VLAN                                                           #
# Original script written by Ludovico Stevens, TME Extreme Networks                      #
# Adapted by Thijs Vandecasteele, Senior Network Engineer Orange Cyberdefense Belgium    #
##########################################################################################

__version__ = '2.0'

# 1.0   - Initial
# 1.1   - Some extra IP validation checks
# 1.2   - Now works properly even in regular BEB (non-DVR Leaf) case
#       - For regular BEB, IP shortcuts is checked
#       - For regular BEB, non-GRT VRF L3VSN config is checked
#       - If a mgmt clip does not exist, the new one is created, and rollback performed if not reachable
# 1.3   - Deletion of mgmt vlan interface in DVR Leaf case can't be done, so we now just delete just the IP on it
# 1.4   - Can be run against multiple VSP switches
#       - Can re-name the VSP at the same time; both SNMP and ISIS sys-names are changed
#       - Decision whether to delete existing mgmt VLAN IP is configurable
#       - Only runs on VOSS 8.2 or later
# 1.5   - Option to delete existing mgmt VLAN IP was not working
#       - CLI session is now established to newly created CLIP IP within script, as check all good, after deleting/re-adding to XMC
#       - Deletion of existing mgmt VLAN IP is now done only if/once a CLI session can be established to new CLIP IP
#       - Switch config is now saved from CLI session on newly created CLIP IP
#       - When deleting the switch from NAC, now the switch is also deleted from any Location Groups too
# 1.6   - System Name input field was mandatory; now is optional
# 1.7   - Increased retries after re-adding switch to XMC/XIQ-SE to 20 from 10 (XIQ-SE is slower than XMC due to XIQ reporting)
# 1.8   - Updated with latest version of function libraries
#       - Able to re-try device addition into XIQ-SE; as sometimes the addition seems to fail
# 1.9   - Above change was not working; not easy to reproduce and thus test...
# --- end of original script by Ludovico
# 2.0   - Initial changes to convert base script from CLIP mgmt to VLAN mgmt


'''
#@MetaDataStart
#@DetailDescriptionStart
#######################################################################################
# 
# Given one or more VSP switches already in XMC, this script will ask user to provide
# a clip IP and VRF which will then be configured as mgmt clip on the switch. If the
# switch already has a mgmt clip, the existing mgmt clip will be deleted and replaced
# with the new one. If the switch has a mgmt vlan IP, this can be deleted if the user
# selects to do so in the script input pull-down.
# Since the switch is effectively deleted and re-added to XMC, the script allows the
# switch sysname to be changed at the same time, which will automatically be reflected
# once the switch is re-added to XMC. Furthermore, the sysname change is perfomed not
# only on the snmp-server name (prompt), but also for the ISIS sys-name.
# Before attempting to change the IP on the switch, the script will first of all make
# sure that the new IP address provided is not already known by XMC and that it does
# not exist on the network (does not reply to ping).
# On a regular BEB (not a DVR Leaf) if the new mgmt clip is on GRT, IP Shortcuts will
# also get automatically enabled if not already enabled. However no ISIS source-address
# will be set.
# Checks are made to ensure that if the VRF provided is non-GRT on a regular BEB, that
# the VRF already has L3VSN enabled (which in turn implies that IP Shortcuts is enabled)
# Otherwise the script will error and make no changes. Likewise, on a DVR Leaf, the
# script will only accept to create a mgmt clip in GRT, and will error otherwise.
#
# If a mgmt clip does not already exist, the script takes a safe approach by creating
# the new mgmt clip and making sure that this is reachable by XMC before proceeding
# any further. If the newly created mgmt clip is not reachable after 10 seconds, the
# changes are rolled back and the script will error.
# But if a mgmt clip does already exist, then the only way to change it is to go
# ahead and delete it and create the new mgmt clip IP; but in this case, if the new IP
# is not reachable after the change, then the switch will be lost.
# Once the new clip mgmt IP is set, the switch is deleted from XMC's database as well
# as XMC Control if there, and also from any NAC Location Groups. It is then re-added
# to the same site, with the same admin profile, with the newly configured clip mgmt
# IP mgmt address.
# The script then waits a further 10 seconds, before attempting to open a session on
# the new clip IP. This session is used to delete the existing mgmt VLAN IP, if user
# had selected the 'delete' pull-down, and to save the config on the switch. 
#
#######################################################################################
#@DetailDescriptionEnd
# ( = &#40;
# ) = &#41;
# , = &#44;
# < = &lt;
# > = &gt;
#@SectionStart (description = "Change accordingly")
#    @VariableFieldLabel (
#        description = "New mgmt VLAN IP",
#        type = string,
#        required = yes,
#        name = "userInput_ip",
#        scope = device
#    )
#    @VariableFieldLabel (
#        description = "New mgmt VLAN ID",
#        type = string,
#        required = yes,
#        name = "userInput_vid",
#        scope = device
#    )
#    @VariableFieldLabel (
#        description = "New mgmt VLAN I-SID",
#        type = string,
#        required = yes,
#        name = "userInput_isid",
#        scope = device
#    )
#    @VariableFieldLabel (
#        description = "New mgmt VLAN gateway",
#        type = string,
#        required = yes,
#        name = "userInput_dgw",
#        scope = device
#    )
#    @VariableFieldLabel (
#        description = "System Name",
#        type = string,
#        required = no,
#        name = "userInput_sysname",
#        scope = device
#    )
#    @VariableFieldLabel (
#        description = "SNMP Location",
#        type = string,
#        required = no,
#        name = "userInput_snmpLoc",
#        scope = device
#    )
#@SectionEnd
#@SectionStart (description = "Sanity / Debug")
#    @VariableFieldLabel (
#        description = "Sanity: enable if you do not trust this script and wish to first see what it does. In sanity mode config commands are not executed",
#        type = string,
#        required = no,
#        validValues = [Enable, Disable],
#        name = "userInput_sanity",
#    )
#    @VariableFieldLabel (
#        description = "Debug: enable if you need to report a problem to the script author",
#        type = string,
#        required = no,
#        validValues = [Enable, Disable],
#        name = "userInput_debug",
#    )
#@SectionEnd
#@MetaDataEnd
'''



##########################################################
# Ludo Standard library; Version 4.00                    #
# Written by Ludovico Stevens, TME Extreme Networks      #
##########################################################
Debug = False    # Enables debug messages
Sanity = False   # If enabled, config commands are not sent to host (show commands are operational)

##########################################################
try:
    emc_vars
    execution = 'xmc'
except: # If not running on XMC Jython...
    # These lines only needed to run XMC Python script locally (on my laptop)
    # They can also be pasted to XMC, but will not execute
    import sys
    import json
    import java.util
    import emc_cli      # Own local replica
    import emc_nbi      # Own local replica
    import emc_results  # Own local replica
    execution = 'dev'
    if len(sys.argv) > 1: # Json file as 1st argv
        emc_vars = json.load(open(sys.argv[1]))
    else:
        emc_vars = json.load(open('emc_vars.json'))
##########################################################

#
# IMPORTS:
#
import re

#
# Base functions
#
import time                         # Used by exitError
ExitErrorSleep = 10

def debug(debugOutput): # v1 - Use function to include debugging in script; set above Debug variable to True or False to turn on or off debugging
    if Debug:
        print debugOutput

def exitError(errorOutput, sleep=ExitErrorSleep): # v3 - Exit script with error message and setting status appropriately
    if 'workflowMessage' in emc_vars: # Workflow
        time.sleep(sleep) # When workflow run on multiple devices, want ones that error to be last to complete, so THEY set the workflow message
        emc_results.put("deviceMessage", errorOutput)
        emc_results.put("activityMessage", errorOutput)
        emc_results.put("workflowMessage", errorOutput)
    emc_results.setStatus(emc_results.Status.ERROR)
    raise RuntimeError(errorOutput)

def abortError(cmd, errorOutput): # v1 - A CLI command failed, before bombing out send any rollback commands which may have been set
    print "Aborting script due to error on previous command"
    try:
        rollbackStack()
    finally:
        print "Aborting because this command failed: {}".format(cmd)
        exitError(errorOutput)

def scriptName(): # v1 - Returns the assigned name of the Script or Workflow
    name = None
    if 'workflowName' in emc_vars: # Workflow
        name = emc_vars['workflowName']
    elif 'javax.script.filename' in emc_vars: # Script
        nameMatch = re.search(r'\/([^\/\.]+)\.py$', emc_vars['javax.script.filename'])
        name = nameMatch.group(1) if nameMatch else None
    return name


#
# Family functions
#
Family = None # This needs to get set by setFamily()
FamilyChildren = { # Children will be rolled into parent family for these scripts
    'Extreme Access Series' : 'VSP Series',
    'Unified Switching VOSS': 'VSP Series',
    'Unified Switching EXOS': 'Summit Series',
    'Universal Platform VOSS': 'VSP Series',
    'Universal Platform EXOS': 'Summit Series',
    'Universal Platform Fabric Engine': 'VSP Series',
    'Universal Platform Switch Engine': 'Summit Series',
}

def setFamily(cliDict={}, family=None): # v2 - Set global Family variable; automatically handles family children, as far as this script is concerned
    global Family
    if family:
        Family = family
    elif emc_vars["family"] in FamilyChildren:
        Family = FamilyChildren[emc_vars["family"]]
    else:
        Family = emc_vars["family"]
    print "Using family type '{}' for this script".format(Family)
    if cliDict and Family not in cliDict:
        exitError('This scripts only supports family types: {}'.format(", ".join(list(cliDict.keys()))))
    return Family


#
# CLI Rollback functions
#
RollbackStack = []

def rollbackStack(): # v1 - Execute all commands on the rollback stack
    if RollbackStack:
        print "Applying rollback commands to undo partial config and return device to initial state"
        while RollbackStack:
            sendCLI_configChain(RollbackStack.pop(), True)

def rollbackCommand(cmd): # v1 - Add a command to the rollback stack; these commands will get popped and executed should we need to abort
    RollbackStack.append(cmd)
    cmdList = map(str.strip, re.split(r'[;\n]', cmd)) # cmd could be a configChain
    cmdList = [x for x in cmdList if x] # Weed out empty elements 
    cmdOneLiner = " / ".join(cmdList)
    print "Pushing onto rollback stack: {}\n".format(cmdOneLiner)

def rollBackPop(number=0): # v1 - Remove entries from RollbackStack
    global RollbackStack
    if number == 0:
        RollbackStack = []
        print "Rollback stack emptied"
    else:
        del RollbackStack[-number:]
        print "Rollback stack popped last {} entries".format(number)


#
# CLI functions
#
RegexPrompt = re.compile('.*[\?\$%#>]\s?$')
RegexError  = re.compile(
    '^%|\x07|error|invalid|cannot|unable|bad|not found|not exist|not allowed|no such|out of range|incomplete|failed|denied|can\'t|ambiguous|do not|unrecognized',
    re.IGNORECASE | re.MULTILINE
)
RegexContextPatterns = { # Ported from acli.pl
    'ERS Series' : [
        re.compile('^(?:interface |router \w+$|route-map (?:\"[\w\d\s\.\+-]+\"|[\w\d\.-]+) \d+$|ip igmp profile \d+$|wireless|application|ipv6 dhcp guard policy |ipv6 nd raguard policy )'), # level0
        re.compile('^(?:security|crypto|ap-profile |captive-portal |network-profile |radio-profile )'), # level1
        re.compile('^(?:locale)'), # level2
    ],
    'VSP Series' : [
        re.compile('^ *(?:interface |router \w+$|router vrf|route-map (?:\"[\w\d\s\.\+-]+\"|[\w\d\.-]+) \d+$|application|i-sid \d+|wireless|logical-intf isis \d+|mgmt [\dcvo]|ovsdb$)'), # level0
        re.compile('^ *(?:route-map (?:\"[\w\d\s\.\+-]+\"|[\w\d\.-]+) \d+$)'), # level1
    ],
}
RegexExitInstance = re.compile('^ *(?:exit|back|end)(?:\s|$)')
Indent = 3 # Number of space characters for each indentation
LastError = None
ConfigHistory = []

def cleanOutput(outputStr): # v2 - Remove echoed command and final prompt from output
    if RegexError.match(outputStr): # Case where emc_cli.send timesout: "Error: session exceeded timeout: 30 secs"
        return outputStr
    lastLine = outputStr.splitlines()[-1:][0]
    if RegexPrompt.match(lastLine):
        lines = outputStr.splitlines()[1:-1]
    else:
        lines = outputStr.splitlines()[1:]
    return '\n'.join(lines)

def configChain(chainStr): # v1 - Produces a list of a set of concatenated commands (either with ';' or newlines)
    chainStr = re.sub(r'\n(\w)(\n|\s*;|$)', chr(0) + r'\1\2', chainStr) # Mask trailing "\ny" or "\nn" on commands before making list
    cmdList = map(str.strip, re.split(r'[;\n]', chainStr))
    cmdList = filter(None, cmdList) # Filter out empty lines, if any
    cmdList = [re.sub(r'\x00(\w)(\n|$)', r'\n\1\2', x) for x in cmdList] # Unmask after list made
    return cmdList

def parseRegexInput(cmdRegexStr): # v1 - Parses input command regex for both sendCLI_showRegex() and xmcLinuxCommand()
    # cmdRegexStr format: <type>://<cli-show-command> [& <additional-show-cmd>]||<regex-to-capture-with>
    if re.match(r'\w+(?:-\w+)?://', cmdRegexStr):
        mode, cmdRegexStr = map(str.strip, cmdRegexStr.split('://', 1))
    else:
        mode = None
    cmd, regex = map(str.strip, cmdRegexStr.split('||', 1))
    cmdList = map(str.strip, cmd.split('&'))
    return mode, cmdList, regex

def formatOutputData(data, mode): # v2 - Formats output data for both sendCLI_showRegex() and xmcLinuxCommand()
    if not mode                 : value = data                                   # Legacy behaviour same as list
    elif mode == 'bool'         : value = bool(data)                             # No regex capturing brackets required
    elif mode == 'str'          : value = str(data[0]) if data else None         # Regex should have 1 capturing bracket at most
    elif mode == 'str-lower'    : value = str(data[0]).lower() if data else None # Same as str but string made all lowercase
    elif mode == 'str-upper'    : value = str(data[0]).upper() if data else None # Same as str but string made all uppercase
    elif mode == 'str-join'     : value = ''.join(data)                          # Regex with max 1 capturing bracket, joins list to string
    elif mode == 'int'          : value = int(data[0]) if data else None         # Regex must have 1 capturing bracket at most
    elif mode == 'list'         : value = data                                   # If > 1 capturing brackets, will be list of tuples
    elif mode == 'list-reverse' : value = list(reversed(data))                   # Same as list but in reverse order
    elif mode == 'list-diagonal': value = [data[x][x] for x in range(len(data))] # Regex pat1|pat2 = list of tuples; want [0][0],[1][1],etc
    elif mode == 'tuple'        : value = data[0] if data else ()                # Regex > 1 capturing brackets, returns 1st tuple
    elif mode == 'dict'         : value = dict(data)                             # Regex must have 2 capturing brackets exactly
    elif mode == 'dict-reverse' : value = dict(map(reversed, data))              # Same as dict, but key/values will be flipped
    elif mode == 'dict-both'    : value = dict(data), dict(map(reversed, data))  # Returns 2 dict: dict + dict-reverse
    elif mode == 'dict-diagonal': value = dict((data[x][x*2],data[x][x*2+1]) for x in range(len(data))) # {[0][0]:[0][1], [1][2]:[1][3], etc}
    else:
        RuntimeError("formatOutputData: invalid scheme type '{}'".format(mode))
    return value

def sendCLI_showCommand(cmd, returnCliError=False, msgOnError=None): # v1 - Send a CLI show command; return output
    global LastError
    resultObj = emc_cli.send(cmd)
    if resultObj.isSuccess():
        outputStr = cleanOutput(resultObj.getOutput())
        if outputStr and RegexError.search("\n".join(outputStr.split("\n")[:4])): # If there is output, check for error in 1st 4 lines only (timestamp banner might shift it by 3 lines)
            if returnCliError: # If we asked to return upon CLI error, then the error message will be held in LastError
                LastError = outputStr
                if msgOnError:
                    print "==> Ignoring above error: {}\n\n".format(msgOnError)
                return None
            abortError(cmd, outputStr)
        LastError = None
        return outputStr
    else:
        exitError(resultObj.getError())

def sendCLI_showRegex(cmdRegexStr, debugKey=None, returnCliError=False, msgOnError=None): # v1 - Send show command and extract values from output using regex
    # Regex is by default case-sensitive; for case-insensitive include (?i) at beginning of regex on input string
    mode, cmdList, regex = parseRegexInput(cmdRegexStr)
    for cmd in cmdList:
        # If cmdList we try each command in turn until one works; we don't want to bomb out on cmds before the last one in the list
        ignoreCliError = True if len(cmdList) > 1 and cmd != cmdList[-1] else returnCliError
        outputStr = sendCLI_showCommand(cmd, ignoreCliError, msgOnError)
        if outputStr:
            break
    if not outputStr: # returnCliError true
        return None
    data = re.findall(regex, outputStr, re.MULTILINE)
    debug("sendCLI_showRegex() raw data = {}".format(data))
    # Format we return data in depends on what '<type>://' was pre-pended to the cmd & regex
    value = formatOutputData(data, mode)
    if Debug:
        if debugKey: debug("{} = {}".format(debugKey, value))
        else: debug("sendCLI_showRegex OUT = {}".format(value))
    return value

def sendCLI_configCommand(cmd, returnCliError=False, msgOnError=None, waitForPrompt=True): # v2 - Send a CLI config command
    global LastError
    cmdStore = re.sub(r'\n.+$', '', cmd) # Strip added CR+y or similar
    if Sanity:
        print "SANITY> {}".format(cmd)
        ConfigHistory.append(cmdStore)
        LastError = None
        return True
    resultObj = emc_cli.send(cmd, waitForPrompt)
    if resultObj.isSuccess():
        outputStr = cleanOutput(resultObj.getOutput())
        if outputStr and RegexError.search("\n".join(outputStr.split("\n")[:4])): # If there is output, check for error in 1st 4 lines only
            if returnCliError: # If we asked to return upon CLI error, then the error message will be held in LastError
                LastError = outputStr
                if msgOnError:
                    print "==> Ignoring above error: {}\n\n".format(msgOnError)
                return False
            abortError(cmd, outputStr)
        ConfigHistory.append(cmdStore)
        LastError = None
        return True
    else:
        exitError(resultObj.getError())

def sendCLI_configChain(chainStr, returnCliError=False, msgOnError=None, waitForPrompt=True, abortOnError=True): # v2 - Send a semi-colon separated list of config commands
    cmdList = configChain(chainStr)
    successStatus = True
    for cmd in cmdList[:-1]: # All but last
        success = sendCLI_configCommand(cmd, returnCliError, msgOnError)
        if not success:
            successStatus = False
            if abortOnError:
                return False
    # Last now
    success = sendCLI_configCommand(cmdList[-1], returnCliError, msgOnError, waitForPrompt)
    if not success:
        return False
    return successStatus

def printConfigSummary(): # v1 - Print summary of all config commands executed with context indentation
    emc_cli.close()
    if not len(ConfigHistory):
        print "No configuration was performed"
        return
    print "The following configuration was successfully performed on switch:"
    indent = ''
    level = 0
    if Family in RegexContextPatterns:
        maxLevel = len(RegexContextPatterns[Family])
    for cmd in ConfigHistory:
        if Family in RegexContextPatterns:
            if RegexContextPatterns[Family][level].match(cmd):
                print "-> {}{}".format(indent, cmd)
                if level + 1 < maxLevel:
                    level += 1
                indent = ' ' * Indent * level
                continue
            elif RegexExitInstance.match(cmd):
                if level > 0:
                    level -= 1
                indent = ' ' * Indent * level
        print "-> {}{}".format(indent, cmd)


#
# CLI warp buffer functions (requires CLI functions)
#
import os                           # Used by warpBuffer_execute
WarpBuffer = []

def warpBuffer_add(chainStr): # v1 - Preload WarpBuffer with config or configChains; buffer can then be executed with warpBuffer_execute()
    global WarpBuffer
    cmdList = configChain(chainStr)
    for cmd in cmdList:
        cmdAdd = re.sub(r'\n.+$', '', cmd) # Strip added CR+y or similar (these are not required when sourcing from file on VOSS and do not work on ERS anyway)
        WarpBuffer.append(cmdAdd)

def warpBuffer_execute(chainStr=None, returnCliError=False, msgOnError=None, waitForPrompt=True): # v3 - Appends to existing WarpBuffer and then executes it
    # Same as sendCLI_configChain() but all commands are placed in a script file on the switch and then sourced there
    # Apart from being fast, this approach can be used to make config changes which would otherwise result in the switch becomming unreachable
    # Use of this function assumes that the connected device (VSP) is already in privExec + config mode
    global WarpBuffer
    global LastError
    xmcTftpRoot = '/tftpboot'
    xmcServerIP = emc_vars["serverIP"]
    switchIP = emc_vars["deviceIP"]
    userName = emc_vars["userName"]
    tftpCheck = {
        'VSP Series':    'bool://show boot config flags||^flags tftpd true',
        'Summit Series': 'bool://show process tftpd||Ready',
        'ERS Series':    True, # Always enabled
    }
    tftpActivate = {
        'VSP Series':    'boot config flags tftpd',
        'Summit Series': 'start process tftpd',
    }
    tftpDeactivate = {
        'VSP Series':    'no boot config flags tftpd',
        'Summit Series': 'terminate process tftpd graceful',
    }
    tftpExecute = { # XMC server IP (TFTP server), Script file to fetch and execute
        'VSP Series':    'copy "{0}:{1}" /intflash/.script.src -y; source .script.src debug',
        'Summit Series': 'tftp get {0} "{1}" .script.xsf; run script .script.xsf',
        'ERS Series':    'configure network address {0} filename "{1}"',
    }

    if chainStr:
        warpBuffer_add(chainStr)
    if Family not in tftpCheck:
        exitError('Sourcing commands via TFTP only supported in family types: {}'.format(", ".join(list(tftpCheck.keys()))))

    # Determine whether switch can do TFTP
    if tftpCheck[Family] == True:
        tftpEnabled = True
    else:
        tftpEnabled = sendCLI_showRegex(tftpCheck[Family])
    if not tftpEnabled:
        if Sanity:
            print "SANITY> {}".format(tftpActivate[Family])
            ConfigHistory.append(tftpActivate[Family])
        else:
            sendCLI_configCommand(tftpActivate[Family], returnCliError, msgOnError) # Activate TFTP now
        warpBuffer_add(tftpDeactivate[Family])      # Restore TFTP state on completion

    if Sanity:
        for cmd in WarpBuffer:
            print "SANITY(warp)> {}".format(cmd)
            ConfigHistory.append(cmd)
        LastError = None
        return True

    # Write the commands to a file under XMC's TFTP root directory
    tftpFileName = userName + '.' + scriptName().replace(' ', '_') + '.' + switchIP.replace('.', '_')
    tftpFilePath = xmcTftpRoot + '/' + tftpFileName
    try:
        with open(tftpFilePath, 'w') as f:
            if Family == 'VSP Series': # Always add these 2 lines, as VSP source command does not inherit current context
                f.write("enable\n")
                f.write("config term\n")
            for cmd in WarpBuffer:
                f.write(cmd + "\n")
            f.write("\n") # Make sure we have an empty line at the end, or VSP sourcing won't process last line...
            debug("warpBuffer - write of TFTP config file : {}".format(tftpFilePath))
    except Exception as e: # Expect IOError
        print "{}: {}".format(type(e).__name__, str(e))
        exitError("Unable to write to TFTP file '{}'".format(tftpFilePath))

    # Make the switch fetch the file and execute it
    success = sendCLI_configChain(tftpExecute[Family].format(xmcServerIP, tftpFileName), returnCliError, msgOnError, waitForPrompt)
    # Clean up by deleting the file from XMC TFTP directory
    os.remove(tftpFilePath)
    debug("warpBuffer - delete of TFTP config file : {}".format(tftpFilePath))

    if not success: # In this case some commands might have executed, before the error; these won't be captured in ConfigHistory
        WarpBuffer = []
        return False
    ConfigHistory.extend(WarpBuffer)
    WarpBuffer = []
    LastError = None
    return True


#
# XMC GraphQl NBI functions
#
from java.util import LinkedHashMap # Used by nbiQuery
LastNbiError = None

def recursionKeySearch(nestedDict, returnKey): # v1 - Used by both nbiQuery() and nbiMutation()
    for key, value in nestedDict.iteritems():
        if key == returnKey:
            return True, value
    for key, value in nestedDict.iteritems():
        if isinstance(value, (dict, LinkedHashMap)): # XMC Python is Jython where a dict is in fact a java.util.LinkedHashMap
            foundKey, foundValue = recursionKeySearch(value, returnKey)
            if foundKey:
                return True, foundValue
        return [None, None] # If we find nothing

def nbiQuery(jsonQueryDict, debugKey=None, returnKeyError=False, **kwargs): # v4 - Makes a GraphQl query of XMC NBI; if returnKey provided returns that key value, else return whole response
    global LastNbiError
    jsonQuery = jsonQueryDict['json']
    for key in kwargs:
        jsonQuery = jsonQuery.replace('<'+key+'>', kwargs[key])
    returnKey = jsonQueryDict['key'] if 'key' in jsonQueryDict else None
    response = emc_nbi.query(jsonQuery)
    debug("nbiQuery response = {}".format(response))
    if 'errors' in response: # Query response contains errors
        if returnKeyError: # If we asked to return upon NBI error, then the error message will be held in LastNbiError
            LastNbiError = response['errors'][0].message
            return None
        abortError("nbiQuery for\n{}".format(jsonQuery), response['errors'][0].message)
    LastNbiError = None

    if returnKey: # If a specific key requested, we find it
        foundKey, returnValue = recursionKeySearch(response, returnKey)
        if foundKey:
            if Debug:
                if debugKey: debug("{} = {}".format(debugKey, returnValue))
                else: debug("nbiQuery {} = {}".format(returnKey, returnValue))
            return returnValue
        if returnKeyError:
            return None
        # If requested key not found, raise error
        abortError("nbiQuery for\n{}".format(jsonQuery), 'Key "{}" was not found in query response'.format(returnKey))

    # Else, return the full response
    if Debug:
        if debugKey: debug("{} = {}".format(debugKey, response))
        else: debug("nbiQuery response = {}".format(response))
    return response

def nbiMutation(jsonQueryDict, returnKeyError=False, debugKey=None, **kwargs): # v4 - Makes a GraphQl mutation query of XMC NBI; returns true on success
    global LastNbiError
    jsonQuery = jsonQueryDict['json']
    for key in kwargs:
        jsonQuery = jsonQuery.replace('<'+key+'>', kwargs[key])
    returnKey = jsonQueryDict['key'] if 'key' in jsonQueryDict else None
    if Sanity:
        print "SANITY - NBI Mutation:\n{}\n".format(jsonQuery)
        LastNbiError = None
        return True
    print "NBI Mutation Query:\n{}\n".format(jsonQuery)
    response = emc_nbi.query(jsonQuery)
    debug("nbiQuery response = {}".format(response))
    if 'errors' in response: # Query response contains errors
        if returnKeyError: # If we asked to return upon NBI error, then the error message will be held in LastNbiError
            LastNbiError = response['errors'][0].message
            return None
        abortError("nbiQuery for\n{}".format(jsonQuery), response['errors'][0].message)

    def recursionStatusSearch(nestedDict):
        for key, value in nestedDict.iteritems():
            if key == 'status':
                if 'message' in nestedDict:
                    return True, value, nestedDict['message']
                else:
                    return True, value, None
        for key, value in nestedDict.iteritems():
            if isinstance(value, (dict, LinkedHashMap)): # XMC Python is Jython where a dict is in fact a java.util.LinkedHashMap
                foundKey, foundValue, foundMsg = recursionStatusSearch(value)
                if foundKey:
                    return True, foundValue, foundMsg
            return [None, None, None] # If we find nothing

    foundKey, returnStatus, returnMessage = recursionStatusSearch(response)
    if foundKey:
        debug("nbiMutation status = {} / message = {}".format(returnStatus, returnMessage))
    elif not returnKeyError:
        # If status key not found, raise error
        abortError("nbiMutation for\n{}".format(jsonQuery), 'Key "status" was not found in query response')

    if returnStatus == "SUCCESS":
        LastNbiError = None
        if returnKey: # If a specific key requested, we find it
            foundKey, returnValue = recursionKeySearch(response, returnKey)
            if foundKey:
                if Debug:
                    if debugKey: debug("{} = {}".format(debugKey, returnValue))
                    else: debug("nbiQuery {} = {}".format(returnKey, returnValue))
                return returnValue
            if returnKeyError:
                return None
            # If requested key not found, raise error
            abortError("nbiMutation for\n{}".format(jsonQuery), 'Key "{}" was not found in mutation response'.format(returnKey))
        return True
    else:
        LastNbiError = returnMessage
        return False


#
# IP address processing functions
#

def ipToNumber(dottedDecimalStr): # v1 - Method to convert an IP/Mask dotted decimal address into a long number; can also use for checking validity of IP addresses
    try: # bytearray ensures that IP bytes are valid (1-255)
        ipByte = list(bytearray([int(byte) for byte in dottedDecimalStr.split('.')]))
    except:
        return None
    if len(ipByte) != 4:
        return None
    debug("ipByte = {}".format(ipByte))
    ipNumber = (ipByte[0]<<24) + (ipByte[1]<<16) + (ipByte[2]<<8) + ipByte[3]
    debug("dottedDecimalStr {} = ipNumber {}".format(dottedDecimalStr, hex(ipNumber)))
    return ipNumber

def numberToIp(ipNumber): # v1 - Method to convert a long number into an IP/Mask dotted decimal address
    dottedDecimalStr = '.'.join( [ str(ipNumber >> (i<<3) & 0xFF) for i in range(4)[::-1] ] )
    debug("ipNumber {} = dottedDecimalStr {}".format(hex(ipNumber), dottedDecimalStr))
    return dottedDecimalStr

def maskToNumber(mask): # v1 - Method to convert a mask (dotted decimal or Cidr number) into a long number
    if isinstance(mask, int) or re.match(r'^\d+$', mask): # Mask as number
        if int(mask) > 0 and int(mask) <= 32:
            maskNumber = (2**32-1) ^ (2**(32-int(mask))-1)
        else:
            maskNumber = None
    else:
        maskNumber = ipToNumber(mask)
    if maskNumber:
        debug("maskNumber = {}".format(hex(maskNumber)))
    return maskNumber

def subnetMask(ip, mask): # v1 - Return the IP subnet and Mask in dotted decimal and cidr formats for the provided IP address and mask
    ipNumber = ipToNumber(ip)
    maskNumber = maskToNumber(mask)
    subnetNumber = ipNumber & maskNumber
    ipSubnet = numberToIp(subnetNumber)
    ipDottedMask = numberToIp(maskNumber)
    ipCidrMask = bin(maskNumber).count('1')
    debug("ipSubnet = {} / ipDottedMask = {} / ipCidrMask = {}".format(ipSubnet, ipDottedMask, ipCidrMask))
    return ipSubnet, ipDottedMask, ipCidrMask


#
# Save Config functions (requires CLI functions)
#
import time                         # Used by vossSaveConfigRetry & vossWaitNoUsersConnected

def vossSaveConfigRetry(waitTime=10, retries=3, returnCliError=False): # v2 - On VOSS a save config can fail, if another CLI session is doing "show run", so we need to be able to backoff and retry
    # Only supported for family = 'VSP Series'
    global LastError
    cmd = 'save config'
    if Sanity:
        print "SANITY> {}".format(cmd)
        ConfigHistory.append(cmd)
        LastError = None
        return True

    retryCount = 0
    while retryCount <= retries:
        resultObj = emc_cli.send(cmd, True)
        if resultObj.isSuccess():
            outputStr = cleanOutput(resultObj.getOutput())
            if outputStr and re.search(r'Save config to file \S+ successful', outputStr): # Check for message indicating successful save
                ConfigHistory.append(cmd)
                LastError = None
                return True
            # If we get here, then the save did not happen, possibly because: "Another show or save in progress.  Please try the command later."
            retryCount += 1
            if retries > 0:
                print "==> Save config did not happen. Waiting {} seconds before retry...".format(waitTime)
                time.sleep(waitTime)
                print "==> Retry {}\n".format(retryCount)
        else:
            exitError(resultObj.getError())

    if returnCliError: # If we asked to return upon CLI error, then the error message will be held in LastError
        LastError = outputStr
        return False
    exitError(outputStr)


#
# Syslog functions
#
import socket                       # Used by addXmcSyslogEvent

def addXmcSyslogEvent(severity, message, ip=None): # v1 - Adds a syslog event to XMC (only needed for Scripts)
    severityHash = {'emerg': 0, 'alert': 1, 'crit': 2, 'err': 3, 'warning': 4, 'notice': 5, 'info': 6, 'debug': 7}
    severityLevel = severityHash[severity] if severity in severityHash else 6
    session = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    session.connect(('127.0.0.1', 514))
    if ip:
        session.send("<{}> XMC Script {} / Device: {} / {}".format(severityLevel,scriptName(),ip,message))
    else:
        session.send("<{}> XMC Script {} / {}".format(severityLevel,scriptName(),ip,message))
    session.close()


#
# INIT: Init Debug & Sanity flags based on input combos
#
try:
    if emc_vars['userInput_sanity'].lower() == 'enable':
        Sanity = True
    elif emc_vars['userInput_sanity'].lower() == 'disable':
        Sanity = False
except:
    pass
try:
    if emc_vars['userInput_debug'].lower() == 'enable':
        Debug = True
    elif emc_vars['userInput_debug'].lower() == 'disable':
        Debug = False
except:
    pass


# --> Insert Ludo Threads library here if required <--


# --> XMC Python script actually starts here <--


#
# Variables:
#

CLI_Dict = {
    'VSP Series': {
        'disable_more_paging'        : 'terminal more disable',
        'enable_context'             : 'enable',
        'config_context'             : 'config term',
        'end_config'                 : 'end',
        'get_mgmt_ip_mask'           : 'int://show mgmt ip||{}\/(\d\d?) ', # IP address
        'get_dvr_type'               : 'str-lower://show dvr||^Role\s+:\s+(Leaf|Controller)',
        'check_vrf_exists'           : 'bool://show ip vrf||^{} ', # VRF name
        'check_vrf_l3vsn'            : 'bool://show ip ipvpn vrf {0}||^{0} +\d+ +enabled', # VRF name
        'list_mgmt_interfaces'       : 'list://show mgmt interface||^\d +\S+ +([A-Z]+) ',
        'list_mgmt_ips'              : 'dict://show mgmt ip||^\d +(\S+) +(\d+\.\d+\.\d+\.\d+)/\d',
        'delete_mgmt_clip'           : 'no mgmt clip',
        'delete_mgmt_vlan'           : 'no mgmt vlan',
        'delete_mgmt_vlan_dvr_leaf'  : 'mgmt vlan; no ip address {}; exit', # IP address
        'enable_ip_shortcuts'        : 'router isis; spbm 1 ip enable; exit',
        'disable_ip_shortcuts'       : 'router isis; no spbm 1 ip enable; exit',
        'create_mgmt_clip'           : # VRF name, IP address
                                       '''
                                       mgmt clip vrf {0}
                                          ip address {1}/32
                                          enable
                                       exit
                                       ''',
        'change_sys_name'            : # Sys-name
                                       '''
                                       snmp-server name {0}
                                       router isis
                                          sys-name {0}
                                       exit
                                       ''',
        'change_mgmt_vlan'           : # newVlanID, newVlanISID, newIp, currentIpMask, newVlanDGW
                                       '''
                                       no mgmt vlan
                                       vlan create {0} name NET-Mgmt type port 0
                                       vlan i-sid {0} {1}
                                       mgmt vlan {0}
                                          ip address {2} {3}
                                          ip route 0.0.0.0/0 next-hop {4}
                                          enable
                                       exit
                                       ''',
        'set_snmp_loc'               : # snmpLoc
                                       '''
                                       snmp-server location "{0}"
                                       ''',
    },
}


NBI_Query = { # GraphQl query / NBI_Query['key'].replace('<IP>', var)
    'nbiAccess': {
        'json': '''
                {
                  administration {
                    serverInfo {
                      version
                    }
                  }
                }
                ''',  
        'key': 'version'
    },
    'checkSwitchXmcDb': {
        'json': '''
                {
                  network {
                    device(ip:"<IP>") {
                      id
                    }
                  }
                }
                ''',
        'key': 'device'
    },
    'getSitePath': {
        'json': '''
                {
                  network {
                    device(ip: "<IP>") {
                      sitePath
                    }
                  }
                }
                ''',
        'key': 'sitePath'
    },
    'getDeviceAdminProfile': {
        'json': '''
                {
                  network {
                    device(ip:"<IP>") {
                      deviceData {
                        profileName
                      }
                    }
                  }
                }
                ''',
        'key': 'profileName'
    },
    'delete_device': {
        'json': '''
                mutation {
                  network {
                    deleteDevices(input:{
                      removeData: true
                      devices: {
                        ipAddress:"<IP>"
                      }
                    }) {
                      status
                      message
                    }
                  }
                }
                ''',
    },
    'checkSwitchNacConfig': {
        'json': '''
                {
                  accessControl {
                    switch(ipAddress: "<IP>") {
                      ipAddress
                    }
                  }
                }
                ''',
        'key': 'switch'
    },
    'getNacLocationGroups': {
        'json': '''
                {
                  accessControl {
                    groupNamesByType(typeString: "LOCATION")
                  }
                }
                ''',
        'key': 'groupNamesByType'
    },
    'accessControlDeleteSwitch': {
        'json': '''
                mutation {
                  accessControl {
                    deleteSwitch(input: {
                      searchKey: "<IP>"
                    }) {
                      message
                      status
                    }
                  }
                }
                ''',
    },
    'accessControlRemoveSwitchFromLocation': {
        'json': '''
                mutation {
                  accessControl {
                    removeEntryFromGroup(input: {
                      group: "<LOCATIONGROUP>"
                      value: "<IP>"
                    }) {
                      message
                      status
                    }
                  }
                }
                ''',
    },
    'create_device': {
        'json': '''
                mutation {
                  network {
                    createDevices(input:{
                      devices: {
                        ipAddress:"<IP>"
                        siteLocation:"<SITE>"
                        profileName:"<PROFILE>"
                      }
                    }) {
                      status
                      message
                    }
                  }
                }
                ''',
    },
    'check_device': {
        'json': '''
                {
                  network {
                    device(ip: "<IP>") {
                      down
                    }
                  }
                }
                ''',
        'key': 'device'
    },
}


#
# Other Custom Functions:
#
def extractSpbmGlobal(): # v1 - Tricky command to extract from, as it is different across VOSS, VSP8600 and XA
    # Only supported for family = 'VSP Series'
    cmd = 'list://show isis spbm||(?:(B-VID) +PRIMARY +(NICK) +LSDB +(IP)(?: +(IPV6))?(?: +(MULTICAST))?|^\d+ +(?:(\d+)-(\d+) +\d+ +)?(?:([\da-f]\.[\da-f]{2}\.[\da-f]{2}) +)?(?:disable|enable) +(disable|enable)(?: +(disable|enable))?(?: +(disable|enable))?|^\d+ +(?:primary|secondary) +([\da-f:]+)(?: +([\da-f\.]+))?)'
    data = sendCLI_showRegex(cmd)
    # VOSS:[(u'B-VID', u'NICK', u'IP', u'IPV6', u'MULTICAST', u'', u'', u'', u'', u'', u'', u'', u''), (u'', u'', u'', u'', u'', u'4051', u'4052', u'0.00.75', u'enable', u'disable', u'disable', u'', u''),           (u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'00:00:00:00:00:00', u'')]
    # V86: [(u'B-VID', u'NICK', u'IP', u'', u'MULTICAST', u'', u'', u'', u'', u'', u'', u'', u''),     (u'', u'', u'', u'', u'', u'4051', u'4052', u'0.00.11', u'enable',             u'disable', u'', u'', u''),      (u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'', u'82:bb:00:00:11:ff', u'82bb.0000.1200')]
    # XA:  [(u'B-VID', u'NICK', u'IP', u'', u'', u'', u'', u'', u'', u'', u'', u'', u''),              (u'', u'', u'', u'', u'', u'4051', u'4052', u'0.00.46', u'enable',                         u'', u'', u'', u'')]
    dataDict = {
        'SpbmInstance' : False,
        'BVIDs'        : [],
        'Nickname'     : None,
        'IP'           : None,
        'IPV6'         : None,
        'Multicast'    : None,
        'SmltVirtBmac' : None,
        'SmltPeerBmac' : None,
    }
    if len(data) > 1: # If we did not just match the banner line
        dataDict['SpbmInstance'] = True
        if data[1][5] and data[1][6]:
            dataDict['BVIDs'] = [data[1][5],data[1][6]]
        else:
            dataDict['BVIDs'] = []
        dataDict['Nickname'] = data[1][7]
        dataDict['IP'] = data[1][8]
        if data[0][3] == 'IPV6':
            dataDict['IPV6'] = data[1][9]
            if data[0][4] == 'MULTICAST':
                dataDict['Multicast'] = data[1][10]
        else:
            if data[0][4] == 'MULTICAST':
                dataDict['Multicast'] = data[1][9]
    if len(data) == 3: # We got SMLT data (on XA we don't have the line)
        if data[2][11] and data[2][11] != '00:00:00:00:00:00':
            dataDict['SmltVirtBmac'] = data[2][11]
            dataDict['SmltPeerBmac'] = data[2][12]
    debug("extractSpbmGlobal() = {}".format(dataDict))
    return dataDict


#
# Main:
#
def main():
    print "{} version {} on XMC version {}".format(scriptName(), __version__, emc_vars["serverVersion"])
    nbiAccess = nbiQuery(NBI_Query['nbiAccess'], returnKeyError=True)
    if nbiAccess == None:
        exitError('This XMC Script requires access to the GraphQl North Bound Interface (NBI). Make sure that XMC is running with an Advanced license and that your user profile is authorized for Northbound API.')

    #
    # Obtain Info on switch and from XMC
    #
    setFamily() # Sets global Family variable
    currentIp           = emc_vars["deviceIP"]
    newIp               = emc_vars["userInput_ip"].strip()
    newSysName          = emc_vars["userInput_sysname"].strip()
    newVlanID           = emc_vars["userInput_vid"].strip()
    newVlanISID         = emc_vars["userInput_isid"].strip()
    newVlanDGW          = emc_vars["userInput_dgw"].strip()
    snmpLoc             = emc_vars["userInput_snmpLoc"].strip()

    print "Information provided by User:"
    print " - New VLAN IP = {}".format(newIp)
    print " - New VLAN ID = {}".format(newVlanID)
    print " - New VLAN I-SID = {}".format(newVlanISID)
    print " - New VLAN Gateway = {}".format(newVlanDGW)
    print " - New System Name = {}".format(newSysName)
    print " - SNMP Location = {}".format(snmpLoc)
    

    vossVersion = emc_vars["deviceSoftwareVer"]

    print "Switch information:"
    print " - VOSS software version = {}".format(vossVersion)
    print

    # VOSS version validation
    if re.match(r'(?:[1-7]\.|8\.[01]\.)', vossVersion):
        exitError('This script only works on VSPs running VOSS 8.2 or later')

    # IP validation
    if not ipToNumber(newIp):
        exitError('Invalid VLAN IP address {}'.format(newIp))
    if newIp == currentIp:
        exitError('Given IP {} is already used to manange the switch'.format(newIp))

    # Sys-name validation
    if re.search(r'\s', newSysName):
        exitError('System Name provided must not contain any spaces: "{}"'.format(newSysName))

    # Check if given IP is already in XMC
    checkNewIpInXmc = nbiQuery(NBI_Query['checkSwitchXmcDb'], IP=newIp)
    if checkNewIpInXmc:
        exitError("Given IP address {} is already in XMC's database".format(newIp))

    # Check if given IP is already out there
    response = os.system("ping -c 1 " + newIp)
    if response == 0: # Response from ping
        exitError("Given IP address {} is already on the network (replies to ping)".format(newIp))

    # Get the site path for device
    sitePath = nbiQuery(NBI_Query['getSitePath'], IP=currentIp)

    # Find the Admin Profile which was in use for this device
    adminProfile = nbiQuery(NBI_Query['getDeviceAdminProfile'], IP=currentIp)

    # Disable more paging
    sendCLI_showCommand(CLI_Dict[Family]['disable_more_paging'])

    # Enter privExec
    sendCLI_showCommand(CLI_Dict[Family]['enable_context'])

    # Get the mask of the IP we are using now
    currentIpMask = sendCLI_showRegex(CLI_Dict[Family]['get_mgmt_ip_mask'].format(currentIp))
    if not currentIpMask:
        exitError("Cannot determine mask of existing IP {}".format(currentIp))

    # Compare subnets for same mask (when moving from mgmt vlan IP to clip IP, ensure the clip IP is not in vlan IP subnet)
    if subnetMask(currentIp, currentIpMask)[0] == subnetMask(newIp, currentIpMask)[0]:
        exitError("New IP {} seems to be in same subnet of existing IP {}".format(newIp, currentIp))

    # Verify whether mgmt clip is already set
    mgmtIfList = sendCLI_showRegex(CLI_Dict[Family]['list_mgmt_interfaces'])
    mgmtIpDict = sendCLI_showRegex(CLI_Dict[Family]['list_mgmt_ips'])

    # Enter Config context
    sendCLI_configCommand(CLI_Dict[Family]['config_context'])

#    if 'CLIP' in mgmtIfList: # Here a mgmt clip already exists, and we are trying to change it
#        # Queue delete of existing mgmt clip
#        warpBuffer_add(CLI_Dict[Family]['delete_mgmt_clip'])
#
#        # Queue creation of new mgmt clip
#        warpBuffer_add(CLI_Dict[Family]['create_mgmt_clip'].format(newVrf, newIp))
#
#    else: # Here no mgmt clip exists, so we can take a safer approach...
#        # For GRT + regular BEB + IP Shortcuts not enabled, we enable IP Shortcuts
#        if (not dvrNodeType == 'leaf' and not spbmGlobalDict['IP'] == 'enable'):
#            sendCLI_configChain(CLI_Dict[Family]['enable_ip_shortcuts'])
#            rollbackCommand(CLI_Dict[Family]['disable_ip_shortcuts'])
#
#        # Go ahead and create the new mgmt clip
#        sendCLI_configChain(CLI_Dict[Family]['create_mgmt_clip'].format(newVrf, newIp))
#        rollbackCommand(CLI_Dict[Family]['delete_mgmt_clip'])
#
#        # Now check if the IP is reachable by XMC
#        print "Waiting up to 10secs for new CLIP Mgmt IP to reply to ping"
    
    # Send commands to script to change the mgmt VLAN
    warpBuffer_add(CLI_Dict[Family]['change_mgmt_vlan'].format(newVlanID, newVlanISID, newIp, currentIpMask, newVlanDGW))

    if not Sanity:
        time.sleep(10)
        retries = 0
        response = None
        while not retries > 25:
            response = os.system("ping -c 1 " + newIp)
            if response == 0: # Response from ping
                break
            retries += 1
            print " - {} timeout".format(retries)
        if response == 1: # No response from ping
            abortError("ping {}".format(newIp), "Newly configured VLAN IP {} not reachable by XMC; rolling back changes".format(newIp))
        print " - reply from {}".format(newIp)

    # Queue change of sys-name
    if newSysName:
        warpBuffer_add(CLI_Dict[Family]['change_sys_name'].format(newSysName))

    # Queue change of SNMP location
    if snmpLoc:
        warpBuffer_add(CLI_Dict[Family]['set_snmp_loc'].format(snmpLoc))

    # Execute queued buffer
    warpBuffer_execute(waitForPrompt=False)
    addXmcSyslogEvent('info', "Changed IP address to {}".format(newIp), currentIp)

    # Close the connection
    if not Sanity:
        emc_cli.close()

    # Delete the old IP from XMC
    if not nbiMutation(NBI_Query['delete_device'], IP=currentIp):
        exitError("Failed to delete IP '{}' from XMC's database".format(currentIp))
    addXmcSyslogEvent('info', "Deleted device from XMC database", currentIp)
    print "Deleted device {} from XMC database".format(currentIp)

    # Check whether switch was added to AccessControl
    switchNacExists = nbiQuery(NBI_Query['checkSwitchNacConfig'], IP=currentIp)
    # Sample of what we should get back
    # "switch": {
    #         "ipAddress": "10.8.4.2"
    # }
    # Or we get None
    if switchNacExists:
        if not nbiMutation(NBI_Query['accessControlDeleteSwitch'], IP=currentIp): # Delete the switch from AccessControl
            exitError("Failed to delete existing switch IP '{}' in NAC Engine Group".format(currentIp))
        addXmcSyslogEvent('info', "Deleted device from XMC Control", currentIp)
        print "Deleted device {} from XMC NAC engine".format(currentIp)

        # Check whether switch was added to any NAC Location Groups
        # For this we need to get a list of all Location Groups
        nacLocationGroups = nbiQuery(NBI_Query['getNacLocationGroups'])
        # Sample of what we should get back
        # "groupNamesByType": [
        #   "Branch3",
        #   "Branch2",
        #   "Branch1",
        # ]
        # Or we get []

        # And then we methodically delete the switch from all those groups
        for group in nacLocationGroups:
            # Delete the switch from Location Group
            if nbiMutation(NBI_Query['accessControlRemoveSwitchFromLocation'], LOCATIONGROUP=group, IP=currentIp):
                addXmcSyslogEvent('info', "Deleted device from XMC Control Location Group: {}".format(group), currentIp)
                print "Deleted device {} from Location Group: {}".format(currentIp, group)
            # We don't check for errors, as we don't expect to find the IP in all location groups

    # Create the new IP device in XMC
    deviceReAdded = False
    addRetries = 0
    while not deviceReAdded and addRetries < 2: # We can try twice, as sometimes XIQ-SE fails to add the device...
        if not nbiMutation(NBI_Query['create_device'], IP=newIp, SITE=sitePath, PROFILE=adminProfile):
            exitError("Failed to add new device IP '{}' to XMC Site '{}' with admin profile '{}'".format(newIp, sitePath, adminProfile))
        addXmcSyslogEvent('info', "Added device to XMC Site {}".format(sitePath), newIp)
        print "Re-added device to XMC using new CLIP IP {} and admin profile '{}'".format(newIp, adminProfile)
        addRetries += 1

        # Wait enough time for XMC to process the newly re-added switch
        print "Waiting for device to be re-added to XMC's database"
        if Sanity:
            deviceReAdded = True
        else:
            retries = 0
            while not retries > 20:
                time.sleep(5)
                if nbiQuery(NBI_Query['check_device'], IP=newIp):
                    # Sample of what we should get back
                    # "device": {
                    #   "down": false
                    # }
                    # Or we get null
                    deviceReAdded = True
                    break
                retries += 1
                print " - retry {}".format(retries)
        print

    # Try and re-open session against the new CLIP IP
    print "Device is re-added to XMC; attempting to re-connect on new VLAN IP"
    if not Sanity:
        emc_cli.setIpAddress(newIp)

    # Enter privExec
    sendCLI_showCommand(CLI_Dict[Family]['enable_context'])

    # Save the config
    vossSaveConfigRetry(waitTime=10, retries=3)

    # Print summary of config performed
    printConfigSummary()
    print "Deleted IP '{}' from XMC's database".format(currentIp)
    if switchNacExists:
        print "Deleted IP '{}' in NAC Engine Group".format(currentIp)
    print "Added new device IP '{}' to XMC Site '{}' with admin profile '{}'".format(newIp, sitePath, adminProfile)

main()
