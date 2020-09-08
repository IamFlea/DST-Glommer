import datetime
import re
import http.client
import traceback
import json 
import os
import sys
from collections import namedtuple


###############################################################################
# Moderators server
_DISCORD_WEBHOOK_URL_ = ""
# Public servers
_DISCORD_WEBHOOK_URLS_PUBLIC_ = [
    # Don't Fight Together
    "",
    # DST EU
    "",
]

_PATH_LATEST_VERSION_FILENAME_ = '/path/to/file/with/version'

################################################################################

### 
# website
_KLEI_UPDATES_URL_ = 'forums.kleientertainment.com'
_KLEI_UPDATES_PATH_ = '/game-updates/dst/'
_KLEI_UPDATES_PORT_ = 443

# negative - errors 
# positive - new stuff
EXIT_CODE = {
    'PARSE_ERROR' : -4,
    'FILE_NOT_UPDATED' : -3,
    'DISCORD_UNAVAILABLE' : -2,
    'UNKNOWN_ERROR' : -1,
    'ALL_OK' : 0,
    'TEXT_FILE_NOT_FOUND' : 1,
    'NEW_TEST_VERSION' : 2,
    'NEW_RELEASE_VERSION' : 3,
}

watchdog = 0
def sendToDiscord(message, hook=_DISCORD_WEBHOOK_URL_):
    # your webhook URL
    global watchdog
    if watchdog >= 5:
        print("Skipping message:", message)
        watchdog = 0
        return
    # compile the form data (BOUNDARY can be anything)
    formdata = "------:::BOUNDARY:::\r\nContent-Disposition: form-data; name=\"content\"\r\n\r\n" + message + "\r\n------:::BOUNDARY:::--"
  
    # get the connection and make the request
    try:
        connection = http.client.HTTPSConnection("discordapp.com")
        connection.request("POST", hook, formdata, {
            'content-type': "multipart/form-data; boundary=----:::BOUNDARY:::",
            'cache-control': "no-cache",
            })
        response = connection.getresponse()
        if response.status < 300:
            watchdog = 0
            return
    except:
        pass
    print("[HOOK] Tryinig to send data again in a second!")
    time.sleep(1)
    watchdog += 1
    sendToDiscord(message, hook) 
    # LOOP

# returns versions from file   release and dev (test)
def getSavedVersion(): 
    with open(_PATH_LATEST_VERSION_FILENAME_, 'r') as f:
        versionRelease = int(f.readline())
        versionDev = int(f.readline())
    #print(versionRelease, versionDev)
    return int(versionRelease), int(versionDev)

def saveVersion(versionRelease, versionDev):
    with open(_PATH_LATEST_VERSION_FILENAME_, 'w') as f:
        f.write(str(versionRelease))
        f.write('\n')
        f.write(str(versionDev))

def downloadFile():
    # Creates the connection
    conn = http.client.HTTPSConnection(_KLEI_UPDATES_URL_, _KLEI_UPDATES_PORT_)
    conn.request("GET", _KLEI_UPDATES_PATH_)

    # Get response
    res =  conn.getresponse()

    # If everything is all right, then parse data, else returns the stuff 
    if res.status == 200: 
        data = res.read()
        conn.close()
        return data
    else:
        conn.close()
        raise Exception(str(datetime.datetime.now()) +" " + res.status +" "+ res.reason)

hotfix = False
VersionInfo = namedtuple('VersionInfo', 'id hotfix version isDev isRelease url')
release = VersionInfo(0,0,0,0,0, '')
dev = VersionInfo(0,0,0,0,0, '')
_webpage = ''
def parseVersion(webpage):
    global release, dev, _webpage
    regex = r'\z<td><a href="/changelist/(\d+)/">';
    webpage = webpage.decode("utf-8")
    _webpage = webpage
    pattern = re.compile(r'\<li class="cCmsRecord_row((.|\n)+?(?=(\</li\>)))')
    matches = re.findall(pattern, webpage)
    release_highest = 0
    dev_highest = 0
    for i, match in enumerate(matches): 

        match = match[0]
        url = re.findall(r"\<a href='([^']*)'", match)
        
        version = re.findall(r"h3 class='ipsType_sectionHead ipsType_break'\>([\s\d]+)", match)
        version = int(version[0])
        result = VersionInfo(
                i, 
                "Hotfix" in match, 
                version, 
                "Test" in match, 
                "Release<" in match,
                url[0]
        )
        if result.isDev and dev_highest < version:
            dev_highest = version
            dev = result
        if result.isRelease and release_highest < version:
            release_highest = version
            release = result

def fromFile():
    return getSavedVersion()


""" Checks the version of the game """    
def checkVersion():
    global release, dev, EXIT_CODE
    data = downloadFile()
    parseVersion(data)

    # Get version saved in path: `_PATH_LATEST_VERSION_FILENAME_`
    try:
        savedVersionRelease, savedVersionDev = getSavedVersion()
    except (FileNotFoundError, ValueError):
        return EXIT_CODE['TEXT_FILE_NOT_FOUND']

    # Compare versions, save changes
    if release.version != savedVersionRelease:
        return EXIT_CODE['NEW_RELEASE_VERSION']
    elif dev.version != savedVersionDev:
        return EXIT_CODE['NEW_TEST_VERSION']
    else:
        return EXIT_CODE['ALL_OK']

# returns date time without miliseconds
def datetimeWithoutMS(): 
    date = str(datetime.datetime.now())
    date, _ = date.split('.');
    return date

def createMessage():
    result = f"**Release update available**: {release.version}"
    result += ' Hotfix' if release.hotfix else ''
    result += '\nPlease `!reset` servers, and write here if you reseted.'
    return result

def main():
    # Get result from the version
    try:
        result = checkVersion()
    except:
        traceback.print_exc() # Needs to log stdout and stderr
        result = EXIT_CODE['PARSE_ERROR']
    #print(release.version, dev.version)
    MSG = {
        EXIT_CODE['PARSE_ERROR'] : "Parse error",
        EXIT_CODE['FILE_NOT_UPDATED'] : f"Couldn't save into `{_PATH_LATEST_VERSION_FILENAME_}`! (Sorry for spam)",
        EXIT_CODE['DISCORD_UNAVAILABLE'] : "Couldn't send message through discord",
        EXIT_CODE['UNKNOWN_ERROR'] : "Unknown error",
        EXIT_CODE['ALL_OK'] : "No change",  
        EXIT_CODE['NEW_RELEASE_VERSION'] :  createMessage(),
        EXIT_CODE['NEW_TEST_VERSION'] : f"Test version available: {dev.version}",
        EXIT_CODE['TEXT_FILE_NOT_FOUND'] : f"Creating textfile `{_PATH_LATEST_VERSION_FILENAME_}`.\nRelease version: {release.version}\nDev version: {dev.version}",
    }
    
    #sendToDiscord(release.url, _DISCORD_WEBHOOK_URL_PUBLIC_)    
    # Print it on discord if result is NEW_TEST_VERSION, NEW_RELEASE_VERSION, or TEXT_FILE_NOT_FOUND
    if result > EXIT_CODE['ALL_OK']: 
        # Print it on discord and save it inot file
        try:
            sendToDiscord(MSG[result])
            if result == EXIT_CODE['NEW_RELEASE_VERSION']:
                for server_url in _DISCORD_WEBHOOK_URLS_PUBLIC_:
                    sendToDiscord(release.url, server_url)
            saveVersion(release.version, dev.version)
        except (FileNotFoundError, FileExistsError, IOError):
            # couldnt save into file
            result = EXIT_CODE['FILE_NOT_UPDATED']
            sendToDiscord(MSG[result])
        except:
            # couldnt connect on discord 
            result = EXIT_CODE['DISCORD_UNAVAILABLE']


    # Log everything into the stdout
    if result != EXIT_CODE['ALL_OK']:
        timestamp = datetimeWithoutMS();
        print(timestamp, MSG[result])
    exit(result)

if __name__ == '__main__':
    main()
