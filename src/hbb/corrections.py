"""
Collection of utilities for corrections and systematics in processors.

Most corrections retrieved from the cms-nanoAOD repo:
See https://cms-nanoaod-integration.web.cern.ch/commonJSONSFs/
"""

from __future__ import annotations

import pathlib
from pathlib import Path

import awkward as ak
from coffea.nanoevents.methods import vector

ak.behavior.update(vector.behavior)
package_path = str(pathlib.Path(__file__).parent.parent.resolve())

# Important Run3 start of Run
FirstRun_2022C = 355794
FirstRun_2022D = 357487
LastRun_2022D = 359021
FirstRun_2022E = 359022
LastRun_2022F = 362180

"""
CorrectionLib files are available from: /cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration - synced daily
"""
pog_correction_path = "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/"
pog_jsons = {
    "muon": ["MUO", "muon_Z.json.gz"],
    "electron": ["EGM", "electron.json.gz"],
    "pileup": ["LUM", "puWeights.json.gz"],
    "fatjet_jec": ["JME", "fatJet_jerc.json.gz"],
    "jet_jec": ["JME", "jet_jerc.json.gz"],
    "jetveto": ["JME", "jetvetomaps.json.gz"],
    "btagging": ["BTV", "btagging.json.gz"],
}

years = {
    "2022": "2022_Summer22",
    "2022EE": "2022_Summer22EE",
    "2023": "2023_Summer23",
    "2023BPix": "2023_Summer23BPix",
}


def get_pog_json(obj: str, year: str) -> str:
    try:
        pog_json = pog_jsons[obj]
    except:
        print(f"No json for {obj}")

    year = years[year]

    return f"{pog_correction_path}/POG/{pog_json[0]}/{year}/{pog_json[1]}"


def build_lumimask(filename):
    from coffea.lumi_tools import LumiMask

    path = Path(f"{package_path}/hbb/data/{filename}")
    return LumiMask(path)


lumiMasks = {
    "2022": build_lumimask("Cert_Collisions2022_355100_362760_Golden.json"),
    "2022EE": build_lumimask("Cert_Collisions2022_355100_362760_Golden.json"),
    "2023": build_lumimask("Cert_Collisions2023_366442_370790_Golden.json"),
    "2023BPix": build_lumimask("Cert_Collisions2023_366442_370790_Golden.json"),
}
