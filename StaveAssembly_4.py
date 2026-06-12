import re
import itkdb
import json
from pathlib import Path
from itkdb.core import User
from getpass import getpass

# Written by Xavier Chen and Ella Richards May 2026.
# Finds IV scan results on local computer, pulls out module serial numbers to be matched with fuse ID from Autoconfig, then assembles modules onto stave.

folder = Path("/home/stavetesting/Desktop/itsdaq-sw/DAT/results")  # Direct to the folder with the test results ("/home/stavetesting/Desktop/itsdaq-sw/DAT/results")
output = dict() # The dictionary that stores all component information and assembly results.
output["Success"] = []
output["Failure"] = []
output["errors"] = []
output["children"] = {}
successSlot = []
MLSN = [None] * 28

def extractJson(runNum, folder):
    tst = []
    for file in folder.glob("*.json"):
        if runNum + "_MODULE_IV_AMAC" in file.name:  # Criteria that locates the specific test files in folder.
            with open(file, "r") as f:
                tst.append(json.load(f))  # Loading the json files in the list "tst" (which is not properly ordered yet).
    return tst

def MLlocator(folder):
    while True:
        try:
            RN = input("Stave IV Scan Test Run Number (5-digit, e.g. 1234_5): ")  # Need to enter in the format "12345", "1234-5" or "1234_5".
            if len(RN) == 6:
                runNum = RN[:4] + "_" + RN[5]
                print("Run #", runNum)
                test = extractJson(runNum, folder)
                if len(test) == 28: # Check if there are exactly 28 IV Scan Files.
                    break
                elif len(test) == 0:
                    print("Error: No IV scan files with such run number. Check run number and folder path.")
                else:
                    print("Error: Expected exactly 28 files.")
            elif len(RN) == 5:
                runNum = RN[:4] + "_" + RN[4]
                print("Run #", runNum)
                test = extractJson(runNum, folder)
                if len(test) == 28:  # Check if there are exactly 28 IV Scan Files.
                    break
                elif len(test) == 0:
                    print("Error: No IV scan files with such run number.")
                else:
                    print("Error: Expected exactly 28 files.")
            else:
                print("Error: Invalid run number.")
        except :
            print("Error: Invalid run number.")

    # Extracting position/sequence of modules installed through AMAC FuseIDs provided in AutoConfig
    # probably not the best way, but there has to be some kind of manual input that informs position/sequence of modules
    # the HCC Fuse IDs can also be used, but not with this code
    while True:
        print("Paste AMAC FuseIDs (then press enter twice):")
        amacid = []
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        for line in lines:
            match = re.search(r'([0-9a-z]{6})', line)
            if match:
                amacid.append(match.group(1))
            else:
                print("Error: "+f"Could not extract Fuse ID from line:\n{line}")
        if len(amacid) == 28:
            break
        else:
            print("Error: Failed to read 28 AMAC FuseIDs.")

    # Match ordered AMAC FuseID with the Module SN
    for i in range(28):
        for j in range(28):
            if str(amacid[i]) == str(test[j]["properties"]["det_info"]["AMAC_FuseID"]):
                MLSN[i] = test[j]["component"]

    for i in range(28):
        output["children"]["Module #" + str(i)] = {"childSN": MLSN[i], "slot": str(i)}
    return output

def assembleComponent(parent, core, output, client):
    # Assemble Core
    try:
        print("Assembling CORE Stave" + core + "...")
        assembleCore = client.post("assembleComponent", json={
            "parent": parent,
            "child": core,
            "properties": None
        })
        output["errors"].append(assembleCore)
    except Exception as e:
        output['errors'].append(str(e))

    # Assemble modules
    if output["children"] == None:
        output['errors'].append('Could not find modules to assemble')
        return output
    for child in output["children"]:
        try:
            print("Assembling Module " + output["children"][child]["childSN"] + " in slot " + output["children"][child][
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

    # Verify through database if core and modules are assembled in the correct positions, then print results
    getStave = client.get("getComponent", json={"component": parent, "alternativeIdentifier": False, "state": "ready",
                                                    "outputType": "full", "noTests": False, "noEosToken": True})
    output["staveCode"] = getStave["code"]
    for children in getStave["children"]:
        if children["componentType"]["code"] == "CORE_STAVE":
            if children["component"]["serialNumber"] == core:
                output["Success"].append("Successfully assembled CORE Stave " + core)
            else:
                output["Failure"].append("Failed to assemble CORE Stave" + core)
    for j in output["children"]:
        for i in range(len(getStave["children"])):
            if int(output["children"][j]["slot"]) < 14:
                if getStave["children"][i]["component"] == None:
                    pass
                elif getStave["children"][i]["component"]["serialNumber"] == output["children"][j]["childSN"]:
                    if getStave["children"][i]["properties"][1]["value"] == output["children"][j]["slot"] and \
                            getStave["children"][i]["properties"][0]["value"] == "Main":
                        output["Success"].append("Successfully assembled Module " + output["children"][j]["childSN"]
                            + " in slot " + output["children"][j]["slot"])
            else:
                if getStave["children"][i]["component"] == None:
                    pass
                elif getStave["children"][i]["component"]["serialNumber"] == output["children"][j]["childSN"]:
                    if getStave["children"][i]["properties"][1]["value"] == str(int(output["children"][j]["slot"]) - 14)\
                            and getStave["children"][i]["properties"][0]["value"] == "Secondary":
                        output["Success"].append("Successfully assembled Module " + output["children"][j]["childSN"]
                            + " in slot " + output["children"][j]["slot"])

    # Find modules failed to assemble
    for success in output["Success"]:
        try:
            successSlot.append(int(success.split()[-1]))
        except:
            pass
    failSlot = set(range(28)) - set(successSlot)
    if failSlot:
        for i in sorted(failSlot):
            output["Failure"].append(
                "Failed to assemble Module " + output["children"]["Module #" + str(i)]["childSN"] + " in slot " +
                output["children"]["Module #" + str(i)]["slot"])
    return output

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

# Verify stave and core serial numbers before assembly.
def askStave(client):
    stave = None
    while True:
        try:
            parent = input("Enter stave SN: ")
            stave = client.get("getComponent", json={"component": parent})
            if stave["componentType"]["code"] == "STAVE":
                if stave["currentLocation"]["code"] == "BNL":
                    break
                else:
                    print("Error: Stave not at BNL")
            else:
                print("Error: Entered SN is not a stave")
        except Exception as e:
            if stave and "uuAppErrorMap" in stave:
                print(stave["uuAppErrorMap"]["message"])
            else:
                print("Error:" + str(e))
    coreSN = parent[:5]+"BC"+parent[7:]
    print("Is " + coreSN + " the correct CORE Stave Serial Number? (y/N)")
    if input() == "y" or input() == "yes":
        core = coreSN
    else:
        core = input("Enter CORE Stave Serial Number:")
    return parent, core

# Run
client = getToken()
StaveCoreSN = askStave(client)
assemblyOutput = assembleComponent(StaveCoreSN[0], StaveCoreSN[1], MLlocator(folder), client)

# Print results
for line in assemblyOutput["Success"]:
    print(line + ".")
if len(assemblyOutput["Failure"]) != 0:
    for line in assemblyOutput["Failure"]:
        print(line + ".")
print("Link to stave on database:")
print("https://itkpd.unicornuniversity.net/componentView?code="+assemblyOutput["staveCode"])
if len(assemblyOutput["errors"]) != 0:
    print("Errors: " + str(assemblyOutput["errors"]))
