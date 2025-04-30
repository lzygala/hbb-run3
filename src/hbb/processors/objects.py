from __future__ import annotations

import awkward as ak
import numpy as np
from coffea.nanoevents.methods.nanoaod import (
    ElectronArray,
    FatJetArray,
    JetArray,
    MuonArray,
    TauArray,
)

# https://twiki.cern.ch/twiki/bin/view/CMS/MuonRun32022


def veto_muons_run2(muons: MuonArray):
    return (
        (muons.pt >= 30)
        & (abs(muons.eta) <= 2.4)
        & (muons.tightId)
        & (muons.miniPFRelIso_all <= 0.2)
    )


def veto_electrons_run2(electrons: ElectronArray):
    return (
        (electrons.pt >= 35)
        & (abs(electrons.eta) <= 2.5)
        & (electrons.cutBased > 3)
        & (electrons.miniPFRelIso_all <= 0.2)
    )


def veto_muons(muons: MuonArray):
    """
    Definition used in Run 2 boosted VBF Hbb
    https://github.com/rkansal47/HHbbVV/blob/bdcc8c672a0fa0aa2182a9d4d677e07fc3c9a281/src/HHbbVV/processors/bbVVSkimmer.py#L551-L553
    """
    return (
        (muons.pt >= 10) & (abs(muons.eta) <= 2.4) & (muons.looseId) & (muons.pfRelIso04_all < 0.25)
    )


def veto_electrons(electrons: ElectronArray):
    """
    Definition used in Run 2 boosted VBF Hbb
    https://github.com/rkansal47/HHbbVV/blob/bdcc8c672a0fa0aa2182a9d4d677e07fc3c9a281/src/HHbbVV/processors/bbVVSkimmer.py#L542-L547
    """
    return (
        (electrons.pt >= 20)
        & (abs(electrons.eta) <= 2.5)
        & (electrons.miniPFRelIso_all < 0.4)
        & (electrons.cutBased >= electrons.LOOSE)
    )


def veto_taus(taus: TauArray):
    # https://github.com/jeffkrupa/zprime-bamboo/blob/main/zprlegacy.py#L371
    return (
        (taus.pt > 20)
        & (taus.decayMode >= 0)
        & (taus.decayMode != 5)
        & (taus.decayMode != 6)
        & (taus.decayMode != 7)
        & (abs(taus.eta) < 2.3)
        & (abs(taus.dz) < 0.2)
        & (taus.idDeepTau2017v2p1VSe >= 2)
        & (taus.idDeepTau2017v2p1VSmu >= 8)
        & (taus.idDeepTau2017v2p1VSjet >= 16)
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
            | ((abs(electrons.eta) >= 1.479) & (abs(electrons.dz) < 0.2) & (abs(electrons.dxy) < 0.1)) 
            )
    )
    return electrons[sel]


def loose_taus(taus: TauArray):
    sel = (
        (taus.pt > 20)
        & (abs(taus.eta) <= 2.5)
        & (taus.idDeepTau2017v2p1VSe >= 2)
        & (taus.idDeepTau2017v2p1VSmu >= 2)
        & (taus.idDeepTau2017v2p1VSjet >= 8)
    )
    return sel


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


# apply ak4 b-jet regression
def bregcorr(jets: JetArray):
    # pt correction for b-jet energy regression
    return ak.zip(
        {
            "pt": jets.pt * jets.bRegCorr,
            "eta": jets.eta,
            "phi": jets.phi,
            "energy": jets.energy * jets.bRegCorr,
        },
        with_name="PtEtaPhiELorentzVector",
    )


def set_ak8jets(fatjets: FatJetArray):
    #Left as temporary alternative to get_ak8jets below
    #Lara needs to learn about the particle transformer taggers
    fatjets['msdcorr'] = fatjets.msoftdrop #TODO Correction study
    fatjets['qcdrho'] = 2 * np.log(fatjets.msdcorr / fatjets.pt)

    return fatjets

# add extra variables to FatJet collection
def get_ak8jets(fatjets: FatJetArray):
    fatjets["t32"] = ak.nan_to_num(fatjets.tau3 / fatjets.tau2, nan=-1.0)
    fatjets["t21"] = ak.nan_to_num(fatjets.tau2 / fatjets.tau1, nan=-1.0)

    fatjets_fields = fatjets.fields
    print(fatjets_fields)

    if "globalParT_Xcs" in fatjets_fields:
        print("Using globalParT_Xcs!!!!!!!!")
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


    if "particleNetMD_Xbb" in fatjets_fields:
        fatjets["Txbb"] = ak.nan_to_num(
            fatjets.particleNetMD_Xbb / (fatjets.particleNetMD_QCD + fatjets.particleNetMD_Xbb),
            nan=-1.0,
        )
        fatjets["Txjj"] = ak.nan_to_num(
            (fatjets.particleNetMD_Xbb + fatjets.particleNetMD_Xcc + fatjets.particleNetMD_Xqq)
            / (
                fatjets.particleNetMD_Xbb
                + fatjets.particleNetMD_Xcc
                + fatjets.particleNetMD_Xqq
                + fatjets.particleNetMD_QCD
            ),
            nan=-1.0,
        )
        fatjets["Tqcd"] = fatjets.particleNetMD_QCD
    elif "ParticleNetMD_probXbb" in fatjets_fields:
        fatjets["Tqcd"] = (
            fatjets.ParticleNetMD_probQCDb
            + fatjets.ParticleNetMD_probQCDbb
            + fatjets.ParticleNetMD_probQCDc
            + fatjets.ParticleNetMD_probQCDcc
            + fatjets.ParticleNetMD_probQCDothers
        )
        fatjets["Txbb"] = fatjets.ParticleNetMD_probXbb / (
            fatjets.ParticleNetMD_probXbb + fatjets["Tqcd"]
        )
        fatjets["Pxjj"] = (
            fatjets.ParticleNetMD_probXbb
            + fatjets.ParticleNetMD_probXcc
            + fatjets.ParticleNetMD_probXqq
        )
        fatjets["Txjj"] = fatjets["Pxjj"] / (fatjets["Pxjj"] + fatjets["Tqcd"])
    else:
        fatjets["Txbb"] = fatjets.particleNet_XbbVsQCD
        fatjets["Txjj"] = fatjets.particleNet_XqqVsQCD
        fatjets["Tqcd"] = fatjets.particleNet_QCD
        # adding Xcc and Xgg
        fatjets["Txcc"] = fatjets.particleNet_XccVsQCD
        fatjets["Txgg"] = fatjets.particleNet_XggVsQCD
        #fatjets["WvsQCD"] = fatjets.particleNetWithMass_WvsQCD

    if "particleNet_mass" not in fatjets_fields:
        fatjets["particleNet_mass"] = fatjets.mass

    if "particleNet_massCorr" in fatjets_fields:
        fatjets["particleNet_mass"] = fatjets.mass * fatjets.particleNet_massCorr
        fatjets["particleNet_massraw"] = (
            (1 - fatjets.rawFactor) * fatjets.mass * fatjets.particleNet_massCorr
        )
    else:
        if "particleNet_mass" not in fatjets_fields:
            fatjets["particleNet_mass"] = fatjets.mass
            fatjets["particleNet_massraw"] = fatjets.mass
        else:
            fatjets["particleNet_massraw"] = fatjets.particleNet_mass

    if "ParticleNetMD_probQCDb" in fatjets_fields:
        fatjets["PQCDb"] = fatjets.ParticleNetMD_probQCDb
        fatjets["PQCDbb"] = fatjets.ParticleNetMD_probQCDbb
        fatjets["PQCDothers"] = fatjets.ParticleNetMD_probQCDothers
    elif "particleNet_QCD1HF" in fatjets_fields:
        fatjets["PQCDb"] = fatjets.particleNet_QCD1HF
        fatjets["PQCDbb"] = fatjets.particleNet_QCD2HF
        fatjets["PQCDothers"] = fatjets.particleNet_QCD0HF
    else:
        # dummy
        fatjets["PQCDb"] = fatjets.particleNetMD_QCD
        fatjets["PQCDbb"] = fatjets.particleNetMD_QCD
        fatjets["PQCDothers"] = fatjets.particleNetMD_QCD

    if "particleNetLegacy_Xbb" in fatjets_fields:
        print("Using particleNetLegacy_Xbb!!!!!!!!")
        fatjets["TXbb_legacy"] = fatjets.particleNetLegacy_Xbb / (
            fatjets.particleNetLegacy_Xbb + fatjets.particleNetLegacy_QCD
        )
        fatjets["TXqq_legacy"] = fatjets.particleNetLegacy_Xqq / (
            fatjets.particleNetLegacy_Xqq + fatjets.particleNetLegacy_QCD
        )
        fatjets["PXbb_legacy"] = fatjets.particleNetLegacy_Xbb
        fatjets["PQCD_legacy"] = fatjets.particleNetLegacy_QCD
        fatjets["PQCDb_legacy"] = fatjets.particleNetLegacy_QCDb
        fatjets["PQCDbb_legacy"] = fatjets.particleNetLegacy_QCDbb
        fatjets["PQCDothers_legacy"] = fatjets.particleNetLegacy_QCDothers
    else:
        fatjets["TXbb_legacy"] = fatjets["Txbb"]

    if "particleNetLegacy_mass" in fatjets_fields:
        fatjets["particleNet_mass_legacy"] = fatjets.particleNetLegacy_mass
    else:
        fatjets["particleNet_mass_legacy"] = fatjets["particleNet_mass"]

    if "particleNetWithMass_TvsQCD" in fatjets_fields:
        fatjets["particleNetWithMass_TvsQCD"] = fatjets.particleNetWithMass_TvsQCD


    fatjets["pt_raw"] = (1 - fatjets.rawFactor) * fatjets.pt

    return fatjets


# ak8 jet definition
def good_ak8jets(fatjets: FatJetArray):
    sel = (
        fatjets.isTight
        & (fatjets.pt > 200)
        & (abs(fatjets.eta) < 2.5)
    )
    return fatjets[sel]


def vbf_jets(
    jets: JetArray,
    fatjets: FatJetArray,
    events,
    pt: float,
    id: str,  # noqa: ARG001
    eta_max: float,
    dr_fatjets: float,
    dr_leptons: float,
    electron_pt: float,
    muon_pt: float,
):
    """Top 2 jets in pT passing the VBF selections"""
    electrons = electrons
    electrons = electrons[electrons.pt > electron_pt]

    muons = muons
    muons = muons[muons.pt > muon_pt]

    ak4_sel = (
        jets.isTight
        & (jets.pt >= pt)
        & (np.abs(jets.eta) <= eta_max)
        & (ak.all(jets.metric_table(fatjets) > dr_fatjets, axis=2))
        & ak.all(jets.metric_table(electrons) > dr_leptons, axis=2)
        & ak.all(jets.metric_table(muons) > dr_leptons, axis=2)
    )

    return jets[ak4_sel][:, :2]


def ak4_jets_awayfromak8(
    jets: JetArray,
    fatjets: FatJetArray,
    events,
    pt: float,
    id: str,  # noqa: ARG001
    eta_max: float,
    dr_fatjets: float,
    dr_leptons: float,
    electron_pt: float,
    muon_pt: float,
    sort_by: str = "btag",
):
    """AK4 jets nonoverlapping with AK8 fatjets"""
    electrons = electrons
    electrons = electrons[electrons.pt > electron_pt]

    muons = muons
    muons = muons[muons.pt > muon_pt]

    ak4_sel = (
        jets.isTight
        & (jets.pt >= pt)
        & (np.abs(jets.eta) <= eta_max)
        & (ak.all(jets.metric_table(fatjets) > dr_fatjets, axis=2))
        & ak.all(jets.metric_table(electrons) > dr_leptons, axis=2)
        & ak.all(jets.metric_table(muons) > dr_leptons, axis=2)
    )

    # return top 2 jets sorted by btagPNetB
    if sort_by == "btag":
        jets_pnetb = jets[ak.argsort(jets.btagPNetB, ascending=False)]
        return jets_pnetb[ak4_sel][:, :2]
    # return 2 jets closet to fatjet0 and fatjet1, respectively
    elif sort_by == "nearest":
        jets_away = jets[ak4_sel]
        FirstFatjet = ak.firsts(fatjets[:, 0:1])
        SecondFatjet = ak.firsts(fatjets[:, 1:2])
        jet_near_fatjet0 = jets_away[ak.argsort(jets_away.delta_r(FirstFatjet), ascending=True)][
            :, 0:1
        ]
        jet_near_fatjet1 = jets_away[ak.argsort(jets_away.delta_r(SecondFatjet), ascending=True)][
            :, 0:1
        ]
        return [jet_near_fatjet0, jet_near_fatjet1]
    # return all nonoverlapping jets, no sorting
    else:
        return jets[ak4_sel]


