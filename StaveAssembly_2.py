import re
import itkdb
import json
from pathlib import Path
from itkdb.core import User
from getpass import getpass

# Written by Xavier Chen and Ella Richards May 2026.
# Finds IV scan results on local computer, pulls out module serial numbers to be matched with fuse ID from Autoconfig, then assembles modules onto stave.

folder = Path("/home/stavetesting/Desktop/itsdaq-sw/DAT/results/")  # Direct to the folder with the test results ("/home/stavetesting/Desktop/itsdaq-sw/DAT/results")
output = dict()
output["Successfully Assembled"] = []
output["Failed to Assemble"] = []
output["errors"] = []
output["children"] = {}

def MLlocator(folder):
    RN = input("Stave IV Scan Test Run Number (5-digit): ")  # Need to enter in the format "12345", "1234-5" or "1234_5".
    if len(RN) == 6:
        runNum = RN[:4] + "_" + RN[5]
    elif len(RN) == 5:
        runNum = RN[:4] + "_" + RN[4]
    else:
        output['errors'].append("Invalid run number format.")
        return output
    print("Run #", runNum)
    test = []  # The list for test result json files.
    MLSN = [None] * 28  # Module Serial Number list to be filled.

    for file in folder.glob("*.json"):
        if runNum + "_MODULE_IV_AMAC" in file.name:  # The criteria should be updated. Right now checks for "ML" (module) and "runNum" (run number).
            with open(file, "r") as f:
                test.append(json.load(f))  # Loading the json files in the list "test" (which is not properly ordered yet).

    if len(test) == 0:
        output['errors'].append("No IV scan files with such run number.")
        return output
    elif len(test) != 28:  # Check if there're 28 IV Scan Files
        output['errors'].append("Expected exactly 28 files.")
        return output

    lines = []
    print("Paste AMAC FuseIDs (then press enter twice):")

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
            output['errors'].append(f"Could not extract Fuse ID from line:\n{line}")
            return output

    if len(amacid) != 28:  # Check if there're 28 AMAC FuseIDs from what is pasted.
        output['errors'].append("Expected exactly 28 AMAC FuseIDs")
        return output

    # Match ordered AMAC FuseID with the Module SN
    for i in range(28):
        for j in range(28):
            if str(amacid[i]) == str(test[j]["properties"]["det_info"]["AMAC_FuseID"]):
                MLSN[i] = test[j]["component"]

    for i in range(28):
        output["children"]["Module #" + str(i)] = {"childSN": MLSN[i], "slot": str(i)}
    return output

def assembleComponent(parent, output):
    # Check that parent exists, is a stave, and is in correct location
    comp = client.get("getComponent", json={"component": parent})
    if comp == None:
        output['errors'].append('Stave does not exist')
        return output
    if comp["componentType"]["code"] != "STAVE":
        output['errors'].append('Entered SN is not a stave')
        return output
    if comp["institution"]["code"] != "BNL":
        output['errors'].append('Stave is not at BNL')
        return output

    # Assemble modules
    if output["children"] == None:
        output['errors'].append('Could not find modules to assemble')
        return output
    for child in output["children"]:
        try:
            print("Assembling " + output["children"][child]["childSN"] + " in slot " + output["children"][child][
                "slot"] + "...")
            if int(output["children"][child]["slot"]) < 14:
                assembleChild = client.post("assembleComponent", json={
                    "parent": parent,
                    "child": output["children"][child]["childSN"],
                    "properties": {"SIDE": "Main", "POSITION": output["children"][child]["slot"], "ASSEMBLER": None,
                                   "CALIBRATION": None, "GLUE-TIME": None, "GLUE-ID": None, "GLUE": None}})
            else:
                assembleChild = client.post("assembleComponent", json={
                    "parent": parent,
                    "child": output["children"][child]["childSN"],
                    "properties": {"SIDE": "Secondary", "POSITION": str(int(output["children"][child]["slot"]) - 14),
                                   "ASSEMBLER": None, "CALIBRATION": None, "GLUE-TIME": None, "GLUE-ID": None,
                                   "GLUE": None}})
            output["errors"].append(assembleChild)
        except Exception as e:
            output['errors'].append(str(e))

    # Verify through database if modules are assembled in the correct positions, then print results
    getStave = client.get("getComponent", json={"component": parent, "alternativeIdentifier": False, "state": "ready",
                                                    "outputType": "full", "noTests": False, "noEosToken": True, })
    for j in output["children"]:
        for i in range(len(getStave["children"])):
            if int(output["children"][j]["slot"]) < 14:
                if getStave["children"][i]["component"] == None:
                    pass
                elif getStave["children"][i]["component"]["serialNumber"] == output["children"][j]["childSN"]:
                    if getStave["children"][i]["properties"][1]["value"] == output["children"][j]["slot"] and \
                            getStave["children"][i]["properties"][0]["value"] == "Main":
                        output["Successfully Assembled"].append("Successfully assembled " + output["children"][j]["childSN"]
                            + " in slot " + output["children"][j]["slot"])
            else:
                if getStave["children"][i]["component"] == None:
                    pass
                elif getStave["children"][i]["component"]["serialNumber"] == output["children"][j]["childSN"]:
                    if getStave["children"][i]["properties"][1]["value"] == str(int(output["children"][j]["slot"]) - 14) and \
                            getStave["children"][i]["properties"][0]["value"] == "Secondary":
                        output["Successfully Assembled"].append("Successfully assembled " + output["children"][j]["childSN"]
                            + " in slot " + output["children"][j]["slot"])

    for i in range(28):
        if all(int(success.split()[-1]) != i for success in output["Successfully Assembled"]):
            output["Failed to Assemble"].append(
                "Failed to assemble " + output["children"]["Module #" + str(i)]["childSN"] + " in slot " +
                output["children"]["Module #" + str(i)]["slot"])
    return output

# Get token
access_code1 = getpass("Access Code 1: ")
access_code2 = getpass("Access Code 2: ")
client = itkdb.Client()
client.user = User(access_code1=access_code1,access_code2=access_code2)

try:
    client.user.authenticate()
    print("Authentication successful.")
except Exception as e:
    print("Authentication failed.")
    print(e)

# Run program
parent = input("Enter stave SN: ")
assemblyOutput = assembleComponent(parent, MLlocator(folder))
print(str(assemblyOutput["Successfully Assembled"]))
if len(assemblyOutput["Failed to Assemble"]) != 0:
    print(str(assemblyOutput["Failed to Assemble"]))
if len(assemblyOutput["errors"]) != 0:
    print("Errors: " + str(assemblyOutput["errors"]))
