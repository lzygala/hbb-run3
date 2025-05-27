from __future__ import annotations

import numpy as np
from coffea.nanoevents.methods.nanoaod import (
    ElectronArray,
    FatJetArray,
    JetArray,
    MuonArray,
)


def good_muons(muons: MuonArray):
    sel = (
        (muons.pt > 10)
        & (np.abs(muons.eta) < 2.4)
        & (muons.looseId)
        & (muons.pfRelIso04_all < 0.15)
        & (
            ((abs(muons.eta) < 1.479) & (abs(muons.dz) < 0.1) & (abs(muons.dxy) < 0.05))
            | ((abs(muons.eta) >= 1.479) & (abs(muons.dz) < 0.2) & (abs(muons.dxy) < 0.1))
        )
    )
    return muons[sel]


def good_electrons(electrons: ElectronArray):
    sel = (
        (electrons.pt > 10)
        & (abs(electrons.eta) < 2.5)
        & (electrons.pfRelIso03_all < 0.15)
        & (electrons.mvaNoIso_WP90)
        & (
            ((abs(electrons.eta) < 1.479) & (abs(electrons.dz) < 0.1) & (abs(electrons.dxy) < 0.05))
            | (
                (abs(electrons.eta) >= 1.479)
                & (abs(electrons.dz) < 0.2)
                & (abs(electrons.dxy) < 0.1)
            )
        )
    )
    return electrons[sel]


def set_ak4jets(jets: JetArray):
    """
    Jet ID fix for NanoAOD v12 copying
    # https://gitlab.cern.ch/cms-jetmet/coordination/coordination/-/issues/117#note_8880716
    """

    jetidtightbit = (jets.jetId & 2) == 2
    jetidtight = (
        ((np.abs(jets.eta) <= 2.7) & jetidtightbit)
        | (
            ((np.abs(jets.eta) > 2.7) & (np.abs(jets.eta) <= 3.0))
            & jetidtightbit
            & (jets.neHEF >= 0.99)
        )
        | ((np.abs(jets.eta) > 3.0) & jetidtightbit & (jets.neEmEF < 0.4))
    )

    jetidtightlepveto = (
        (np.abs(jets.eta) <= 2.7) & jetidtight & (jets.muEF < 0.8) & (jets.chEmEF < 0.8)
    ) | ((np.abs(jets.eta) > 2.7) & jetidtight)

    jets["jetidtight"] = jetidtight
    jets["jetidtightlepveto"] = jetidtightlepveto

    return jets


# ak4 jet definition
def good_ak4jets(jets: JetArray):
    # Since the main AK4 collection for Run3 is the AK4 Puppi collection, jets originating from pileup are already suppressed at the jet clustering level
    # PuID might only be needed for forward region (WIP)

    # JETID: https://twiki.cern.ch/twiki/bin/viewauth/CMS/JetID13p6TeV
    # 2 working points: tight and tightLepVeto
    sel = (jets.pt > 30) & (jets.isTight) & (abs(jets.eta) < 5.0)

    return jets[sel]


def set_ak8jets(fatjets: FatJetArray):
    # Left as temporary alternative to get_ak8jets below
    # Lara needs to learn about the particle transformer taggers
    fatjets["msdcorr"] = fatjets.msoftdrop  # TODO Correction study
    fatjets["qcdrho"] = 2 * np.log(fatjets.msdcorr / fatjets.pt)

    if "globalParT_Xcs" in fatjets.fields:
        fatjets["ParTPQCD1HF"] = fatjets.globalParT_QCD1HF
        fatjets["ParTPQCD2HF"] = fatjets.globalParT_QCD2HF
        fatjets["ParTPQCD0HF"] = fatjets.globalParT_QCD0HF
        fatjets["ParTPXbb"] = fatjets.globalParT_Xbb
        fatjets["ParTPXcc"] = fatjets.globalParT_Xcc
        fatjets["ParTPXcs"] = fatjets.globalParT_Xcs
        fatjets["ParTPXgg"] = fatjets.globalParT_Xgg
        fatjets["ParTPXqq"] = fatjets.globalParT_Xqq
        # ParT masses were trained with the masses WITHOUT the jet mass correction, so we have to undo the correction here
        fatjets["ParTmassRes"] = fatjets.globalParT_massRes * (1 - fatjets.rawFactor) * fatjets.mass
        fatjets["ParTmassVis"] = fatjets.globalParT_massVis * (1 - fatjets.rawFactor) * fatjets.mass

    return fatjets


# ak8 jet definition
def good_ak8jets(fatjets: FatJetArray):
    sel = fatjets.isTight & (fatjets.pt > 200) & (abs(fatjets.eta) < 2.5)
    return fatjets[sel]
