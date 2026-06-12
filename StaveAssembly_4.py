import re
import itkdb
import json
import datetime
from pathlib import Path
from itkdb.core import User
from getpass import getpass

# Written by Xavier Chen and Ella Richards May 2026.
# Finds IV scan results on local computer, pulls out module serial numbers to be matched with fuse ID from Autoconfig, then assembles modules onto stave.

folder = Path(
    "/home/stavetesting/Desktop/itsdaq-sw/DAT/results")  # Direct to the folder with the test results ("/home/stavetesting/Desktop/itsdaq-sw/DAT/results")
logpath = Path(r"C:\Users\xavie\Desktop")  # /home/stavetesting/Desktop/itsdaq-sw/DAT/logs
date = datetime.datetime.now().strftime("%Y%m%d")
output = dict()  # The dictionary that stores all component information and assembly results.
output["Success"] = []
output["Failure"] = []
output["errors"] = []
output["children"] = {}
successSlot = []
MLSN = [None] * 28


def finditsdaqLog(path):
    max_time = 0
    latest_file = None
    for itsdaqLog in path.glob("*.txt"):
        if date in itsdaqLog.name:
            time = re.search(rf"{date}(\d*)", itsdaqLog.name)
            if time:
                if int(time.group()) > max_time:
                    max_time = int(time.group())
                    latest_file = itsdaqLog
    return latest_file

def findAMACIDs(file):
    amacID_pattern = re.compile(r"^AMAC\(\d+\) fuse_id [a-z0-9]+:$")
    amacid = []
    IDblocks = []
    current_line = []
    print("Finding AMAC Fuse IDs ...")
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            clean_line = line.strip()
            if amacID_pattern.match(clean_line):
                current_line.append(clean_line)
            else:
                if current_line:
                    IDblocks.append(current_line)
                    current_line = []
    if current_line:
        IDblocks.append(current_line)
    for block in IDblocks[-1]:
        amacid.append(block[-7:-1])
    print("Found all 28 AMAC Fuse IDs.")
    return amacid

def extractJson(runNum, folder):
    tst = []
    for file in folder.glob("*.json"):
        if runNum + "_MODULE_IV_AMAC" in file.name:  # Criteria that locates the specific test files in folder.
            with open(file, "r") as f:
                tst.append(
                    json.load(f))  # Loading the json files in the list "tst" (which is not properly ordered yet).
    return tst

def MLlocator(folder, amacid):
    while True:
        try:
            RN = input(
                "Stave IV Scan Test Run Number (5-digit, e.g. 1234_5): ")  # Need to enter in the format "12345", "1234-5" or "1234_5".
            if len(RN) == 6:
                runNum = RN[:4] + "_" + RN[5]
                print("Run #", runNum)
                test = extractJson(runNum, folder)
                if len(test) == 28:  # Check if there are exactly 28 IV Scan Files.
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
        except:
            print("Error: Invalid run number.")
    output["runNum"] = runNum

    # Extracting position/sequence of modules installed through AMAC FuseIDs provided in AutoConfig from log
    # Match ordered AMAC FuseID with the Module SN
    for i in range(28):
        for j in range(28):
            if str(amacid[i]) == str(test[j]["properties"]["det_info"]["AMAC_FuseID"]):
                MLSN[i] = test[j]["component"]

    for i in range(28):
        output["children"]["Module #" + str(i)] = {"childSN": MLSN[i], "slot": str(i)}
    print("Successfully matched all modules.")
    return output

def assembleComponent(parent, core, output, client):
    # Assemble Core
    try:
        print("Assembling CORE Stave" + core + "...")
        assembleCore = client.post("assembleComponent", json={
            "parent": parent,
            "child": core,
            "properties": None})
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

    # Assembly EoS cards
    try:
        print("Assembling first EoS card ...")
        eosSN = lpgbtReport(output["runNum"][:4], logpath)
        assembleEoS1 = client.post("assembleComponent", json={
            "parent": parent,
            "child": eosSN[0],
            "properties": {"SIDE": "Main"}})
        output["errors"].append(assembleEoS1)
    except Exception as e:
        output['errors'].append(str(e))
    try:
        print("Assembling second EoS card ...")
        assembleEoS2 = client.post("assembleComponent", json={
            "parent": parent,
            "child": eosSN[1],
            "properties": {"SIDE": "Secondary"}})
        output["errors"].append(assembleEoS2)
    except Exception as e:
        output['errors'].append(str(e))

    # Verify through database if core, modules, and EoS cards are assembled in the correct positions, then print results
    getStave = client.get("getComponent", json={"component": parent, "alternativeIdentifier": False, "state": "ready",
                                                "outputType": "full", "noTests": False, "noEosToken": True})
    output["staveCode"] = getStave["code"]
    for children in getStave["children"]:
        if children["componentType"]["code"] == "CORE_STAVE":
            if children["component"]["serialNumber"] == core:
                output["Success"].append("Successfully assembled CORE Stave " + core)
            else:
                output["Failure"].append("Failed to assemble CORE Stave" + core)
        if children["componentType"]["code"] == "EOS_CARD":

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
                    if getStave["children"][i]["properties"][1]["value"] == str(int(output["children"][j]["slot"]) - 14) \
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
        client.user = User(access_code1=access_code1, access_code2=access_code2)
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
    coreSN = parent[:5] + "BC" + parent[7:]
    print("Is " + coreSN + " the correct CORE Stave Serial Number? (y/N)")
    if input() == "y" or input() == "yes":
        core = coreSN
    else:
        core = input("Enter CORE Stave Serial Number:")
    return parent, core

def lpgbtReport(runNum, folder):
    for file in folder.glob("*.json"):
        if "lpgbt_report_" + str(runNum) in file.name:
            with open(file, "r") as f:
                EoS = json.load(f)
    SN = [None] * 2
    for i in range(2):
        SN[i] = client.get("getComponent", json={
            "component": EoS["port_" + str(i * 2)]["eos_id"],
            "alternativeIdentifier": True, })["serialNumber"]
    return SN


# Run
client = getToken()
StaveCoreSN = askStave(client)
assemblyOutput = assembleComponent(StaveCoreSN[0], StaveCoreSN[1],
                                   MLlocator(folder, findAMACIDs(finditsdaqLog(logpath))), client)

# Print results
for line in assemblyOutput["Success"]:
    print(line + ".")
if len(assemblyOutput["Failure"]) != 0:
    for line in assemblyOutput["Failure"]:
        print(line + ".")
print("Link to stave on database:")
print("https://itkpd.unicornuniversity.net/componentView?code=" + assemblyOutput["staveCode"])
if len(assemblyOutput["errors"]) != 0:
    print("Errors: " + str(assemblyOutput["errors"]))
