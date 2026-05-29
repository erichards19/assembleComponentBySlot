import re

import itkdb
import json
from pathlib import Path

# Written by Xavier Chen and Ella Richards May 2026. 
# Finds IV scan results on local computer, pulls out module serial number to be matched with fuse ID from Autoconfig. Assembles modules by slot. 

folder = Path("/Users/ellarichards/BNL work") #Direct to the folder with the test results ("/home/stavetesting/Desktop/itsdaq-sw/DAT/results")

output = dict()
output["Successfully Assembled"] = []
output["Failed to Assemble"] = []
output["errors"] = []
output["children"] = {}

client = itkdb.Client()
client.user.authenticate()  
user = client.get("getUser", json={"userIdentity": client.user.identity})

def MLlocator(folder):
    children={}
    RN = input("Stave Test Run Number: ") #Need to enter in the format "1234-5" or "1234_5".
    if len(RN) == 6:
        runNum = RN[:4]+"_"+RN[5]
    elif len(RN) == 5:
        runNum = RN[:4]+"_"+RN[4]
    else:  
        output['errors'].append("Invalid run number format.")
        return output
    print("Run #", runNum)
    data = [] #The list for test result json files.
    MLSN = [None] * 28 #Module Serial Number list to be filled.

    for file in folder.glob("*.json"):
        if "ML" in file.name and runNum in file.name: #The criteria should be updated. Right now checks for "ML" (module) and "runNum" (run number).
            with open(file, "r") as f:
                data.append(json.load(f)) #Loading the json files in the list "data" (which is not properly ordered yet).

    if len(data) == 0:
        output['errors'].append("No IV scan files with such run number.")
        return output
    elif len(data) != 28: #Check if there're 28 IV Scan Files
        output['errors'].append("Expected exactly 28 files.")
        return output
   
    lines = []
    print("Paste AMAC FuseIDs:")

    # Extracting position/sequence of modules installed through AMAC FuseIDs provided in AutoConfig'''
    # probably not the best way, but there has to be some kind of manual input that informs position/sequence of modules'''
    # the HCC Fuse IDs can also be used, but not with this code'''

    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    amacid = []
    for line in lines:
        match = re.search(r'([0-9a-z]{6})', line)
        if match:
            amacid.append(match.group(1))
        else:
            raise ValueError(f"Could not extract Fuse ID from line:\n{line}")

    if len(amacid) != 28: #Check if there're 28 AMAC FuseIDs from what is pasted.
        raise ValueError("Expected exactly 28 AMAC FuseIDs")

    #Match ordered AMAC FuseID with the Module SN
    for i in range(28):
        for j in range(28):
            if str(amacid[i]) == str(data[j]["properties"]["det_info"]["AMAC_FuseID"]):
                MLSN[i] = data[j]["component"]

    for i in range(28):
        output["children"]["Module #" + str(i)] = {"childSN": MLSN[i], "slot": str(i)}
    return output


parent = input("Enter stave SN: ")

def assembleComponentBySlot(parent, output):

    # Check that parent exists, is a stave, and is in correct location 
    comp = client.get("getComponent", json={"component": parent})  
    if comp == None: 
        output['errors'].append('Component does not exist')
        return output
    if comp["componentType"]["code"] != "STAVE":
        output['errors'].append('Component is not a stave')
        return output
    if comp["institution"]["code"] != "BNL":
        output['errors'].append('Component is not at BNL')
        return output

    # Assemble modules 
    if output["children"] == None:
        output['errors'].append('Could not find modules to assemble')
        return output
    try:   
        for child in output["children"]:
            print("Assembling " + output["children"][child]["childSN"] + " in slot " + output["children"][child]["slot"])
            assembleChild = client.post("assembleComponentBySlot", json={
                "parent": parent,
                "child": output["children"][child]["childSN"],
                "slot": output["children"][child]["slot"],
            })
            if assembleChild.get("success"):
                output["Successfully Assembled" + output["children"][child]["childSN"] + " in slot " + output["children"][child]["slot"]].append(assembleChild)
            else:
                output["Failed to Assemble" + output["children"][child]["childSN"] + " in slot " + output["children"][child]["slot"]].append(assembleChild)
        return output
    except Exception as e:
        output['errors'].append(str(e))
        return output

assemblyOutput = assembleComponentBySlot(parent, MLlocator(folder))
print("Successfully Assembled: " + str(assemblyOutput["Successfully Assembled"]))
print("Failed to Assemble: " + str(assemblyOutput["Failed to Assemble"]))
print("Errors: " + str(assemblyOutput["errors"]))
