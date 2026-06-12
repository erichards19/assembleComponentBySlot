import json
import os
import itkdb
from itkdb.core import User
from pathlib import Path
from getpass import getpass

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

def lpgbtReport(runNum, folder):
    for file in folder.glob("*.json"):
        if "lpgbt_report_" + str(runNum) in file.name:
            with open(file, "r") as f:
                return json.load(f)


client = getToken()
runNum = input("Enter Test Run Number: (Press RETURN if using current test)")
eosSN=[None]*2
EoS = lpgbtReport(runNum, logpath)
for i in range(2):
    eosSN[i] = client.get("getComponent", json={
            "component": EoS["port_"+str(i*2)]["eos_id"],
            "alternativeIdentifier": True,})["serialNumber"]
    assembleEoS = client.post("assembleComponent", json={
        "parent": parent,
        "child": eosSN[i],
        "properties": 







