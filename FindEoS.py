import json
import os
import itkdb
from itkdb.core import User
from pathlib import Path
from getpass import getpass

runNumFolder = Path("/home/stavetesting/Desktop/itsdaq-sw/DAT/etc")
logpath = Path("/home/stavetesting/Desktop/itsdaq-sw/DAT/logs")

def getToken():
    while True:
        access_code1 = getpass("Access Code 1: ")
        access_code2 = getpass("Access Code 2: ")
        client = itkdb.Client()
        client.user = User(access_code1=access_code1,access_code2=access_code2)
        try:
            client.user.authenticate()
            print("Authentication successful.")
            break
        except:
            print("Authentication failed.")
    return client

def findLastFile(logpath, name_pattern):
    latest_file = None
    latest_mtime = 0

    print("Scanning logs...")

    # os.scandir loops through files efficiently without loading the whole list into memory
    with os.scandir(logpath) as logs:
        for files in logs:
            # Check if it's a file and contains your specific number/format string
            if files.is_file() and name_pattern in files.name:
                # entry.stat() retrieves the modification time instantly
                mtime = files.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_file = files.path

    if not latest_file:
        print(f"No files found matching the pattern: '{name_pattern}'")
        return

    print(f"Success! Found latest file: {latest_file}")
    print(f"Extracting data starting from keyword: '{keyword}'\n")

    return latest_file

client = getToken()

with open(findLastFile(logpath, "lpgbt_report"), "r") as f:
    lpgbtReport = json.load(f)

eosSN=[None]*2
for i in range(2):
    eosSN[i] = (client.get("getComponent", json={
    "component": lpgbtReport["port_"+str(i*2)]["eos_id"],
    "alternativeIdentifier": True,})["serialNumber"])

print("MAIM side EoS SN: "+ str(eosSN[0]))
print("SECONDARY side EoS SN: "+ str(eosSN[1]))






