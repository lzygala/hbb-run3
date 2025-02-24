"""
Gen selection functions for skimmer.

Author(s): Raghav Kansal, Cristina Mantilla Suarez
"""

from __future__ import annotations

import awkward as ak
import numpy as np
from coffea.nanoevents.methods.base import NanoEventsArray
from coffea.nanoevents.methods.nanoaod import FatJetArray, JetArray

from ..utils import add_selection, pad_val

d_PDGID = 1
u_PDGID = 2
s_PDGID = 3
c_PDGID = 4
b_PDGID = 5
g_PDGID = 21
TOP_PDGID = 6

ELE_PDGID = 11
vELE_PDGID = 12
MU_PDGID = 13
vMU_PDGID = 14
TAU_PDGID = 15
vTAU_PDGID = 16

G_PDGID = 22
Z_PDGID = 23
W_PDGID = 24
HIGGS_PDGID = 25

b_PDGIDS = [511, 521, 523]

GEN_FLAGS = ["fromHardProcess", "isLastCopy"]


def gen_selection_HHbbbb(
    events: NanoEventsArray,
    jets: JetArray,
    fatjets: FatJetArray,
    selection_args: list,
    skim_vars: dict,
):
    """Gets HH, bb 4-vectors"""
    # finding the two gen higgs
    higgs = events.GenPart[
        (abs(events.GenPart.pdgId) == HIGGS_PDGID) * events.GenPart.hasFlags(GEN_FLAGS)
    ]

    # saving 4-vector info
    GenHiggsVars = {f"GenHiggs{key}": higgs[var].to_numpy() for (var, key) in skim_vars.items()}

    higgs_children = higgs.children
    is_bb = abs(higgs_children.pdgId) == b_PDGID

    # checking that is a 4b decay
    has_4b = ak.sum(ak.flatten(is_bb, axis=2), axis=1) == 4

    # only select events with 4 b's
    add_selection("has_bbbb", has_4b, *selection_args)

    # children 4-vector
    bs = ak.flatten(higgs_children[is_bb], axis=2)
    GenbVars = {f"Genb{key}": pad_val(bs[var], 4, axis=1) for (var, key) in skim_vars.items()}

    bs_unflat = higgs_children[is_bb]
    b_h1 = higgs_children[is_bb][:, 0]
    b_h2 = higgs_children[is_bb][:, 1]

    # match jets to each b-quark
    matched_to_bs = jets.metric_table(bs_unflat) < 0.4
    num_b_matched = ak.sum(matched_to_bs, axis=2)
    matched_to_higgs = jets.metric_table(higgs) < 0.5

    # require 1 b matched to the jet (but not necessarily matched to the Higgs)
    is_matched = num_b_matched == 1
    is_jet_matched = ak.any(is_matched, axis=2)
    jets["HiggsMatch"] = is_jet_matched

    # index of the higgs to which the jet is closest to
    # This line in particular is taking ak.argmin (index of the b quark that is closest to the jet)
    # we take np.floor of the number divided by 2 to get the index of the higgs
    #  e.g. if it is matched to b quarks 0 or 1 => HiggsMatchIndex = 0
    #  e.g. if it is matched to b quarks 2 or 3 => HiggsMatchIndex = 1
    jets["HiggsMatchIndex"] = ak.mask(
        np.floor(ak.argmin(jets.metric_table(bs), axis=2) / 2), jets["HiggsMatch"] == 1
    )

    num_jets = 6
    ak4JetVars = {
        f"ak4Jet{var}": pad_val(jets[var], num_jets, axis=1)
        for var in ["HiggsMatch", "HiggsMatchIndex", "hadronFlavour"]
    }

    # match fatjets to bb
    num_b_matched = ak.sum(fatjets.metric_table(bs_unflat) < 0.8, axis=2)
    matched_to_higgs = fatjets.metric_table(higgs) < 0.8

    # require 2 bs matched to the jet
    is_matched = matched_to_higgs
    is_fatjet_matched = ak.any(is_matched, axis=2)

    fatjets["HiggsMatch"] = is_fatjet_matched
    fatjets["HiggsMatchIndex"] = ak.mask(
        ak.argmin(fatjets.metric_table(higgs), axis=2), fatjets["HiggsMatch"] == 1
    )
    fatjets["NumBMatchedH1"] = ak.sum(fatjets.metric_table(b_h1) < 0.8, axis=2)
    fatjets["NumBMatchedH2"] = ak.sum(fatjets.metric_table(b_h2) < 0.8, axis=2)
    fatjets["MaxdRH1"] = ak.max(fatjets.metric_table(b_h1), axis=2)
    fatjets["MaxdRH2"] = ak.max(fatjets.metric_table(b_h2), axis=2)

    num_fatjets = 2
    bbFatJetVars = {
        f"bbFatJet{var}": pad_val(fatjets[var], num_fatjets, axis=1)
        for var in [
            "HiggsMatch",
            "HiggsMatchIndex",
            "NumBMatchedH1",
            "NumBMatchedH2",
            "MaxdRH1",
            "MaxdRH2",
        ]
    }

    return {**GenHiggsVars, **GenbVars, **ak4JetVars, **bbFatJetVars}


def gen_selection_Hbb(
    events: NanoEventsArray,
    jets: JetArray,  # noqa: ARG001
    fatjets: FatJetArray,
    selection_args: list,  # noqa: ARG001
    skim_vars: dict,
):
    """Gets H, bb, 4-vectors + Higgs children information"""

    # finding the two gen higgs
    higgs = events.GenPart[
        (abs(events.GenPart.pdgId) == HIGGS_PDGID) * events.GenPart.hasFlags(GEN_FLAGS)
    ]
    higgs_children = higgs.children

    GenHiggsVars = {f"GenHiggs{key}": higgs[var].to_numpy() for (var, key) in skim_vars.items()}
    GenHiggsVars["GenHiggsChildren"] = abs(higgs_children.pdgId[:, :, 0]).to_numpy()

    is_bb = abs(higgs_children.pdgId) == b_PDGID
    bs = ak.flatten(higgs_children[is_bb], axis=2)
    GenbVars = {f"Genb{key}": pad_val(bs[var], 4, axis=1) for (var, key) in skim_vars.items()}

    # match fatjets to bb
    # bs_unflat = higgs_children[is_bb]
    # num_b_matched = ak.sum(fatjets.metric_table(bs_unflat) < 0.8, axis=2)
    #[:, n] selects the  n -th element along the second axis (the Higgs boson index)
    b_h1 = ak.firsts(higgs_children[is_bb][:, 0:1])   # first b quark
    b_h2 = ak.firsts(higgs_children[is_bb][:, 1:2]) # second b quark
    matched_to_higgs = fatjets.metric_table(higgs) < 0.8    # metric_table returns the deltaR between the fatjet and the higgs
    is_fatjet_matched = ak.any(matched_to_higgs, axis=2)

    fatjets["HiggsMatch"] = is_fatjet_matched
    fatjets["HiggsMatchIndex"] = ak.mask(
        ak.argmin(fatjets.metric_table(higgs), axis=2), fatjets["HiggsMatch"] == 1
    )
    fatjets["NumBMatchedH1"] = ak.sum(fatjets.metric_table(b_h1) < 0.8, axis=2)
    fatjets["NumBMatchedH2"] = ak.sum(fatjets.metric_table(b_h2) < 0.8, axis=2)

    print(ak.num(fatjets[var], axis=1))

    num_fatjets = 2
    bbFatJetVars = {
        f"bbFatJet{var}": pad_val(fatjets[var], num_fatjets, axis=1)
        for var in [
            "HiggsMatch",
            "HiggsMatchIndex",
            "NumBMatchedH1",
            "NumBMatchedH2",
        ]
    }

    return {**GenHiggsVars, **GenbVars, **bbFatJetVars}


def gen_selection_V(
    events: NanoEventsArray,
    jets: JetArray,  # noqa: ARG001
    fatjets: FatJetArray,
    selection_args: list,  # noqa: ARG001
    skim_vars: dict,
):
    """Get W/Z and children information"""
    vs = events.GenPart[
        ((abs(events.GenPart.pdgId) == W_PDGID) | (abs(events.GenPart.pdgId) == Z_PDGID))
        * events.GenPart.hasFlags(GEN_FLAGS)
    ]
    vs_flat = ak.firsts(vs)
    vs_children = vs.children
    vs_pdgId = abs(vs_children.pdgId)

    GenVVars = {f"GenV{key}": vs_flat[var].to_numpy() for (var, key) in skim_vars.items()}
    GenVVars["GenVChildren"] = vs_pdgId.to_numpy()


    #events.GenPart.fields()  # Print fields of GenPart
    # vs should have something like higgs_children = vs.children
    # the .children will still be a genpart object
    # children.pdgId will be the pdgId of the children

    #print("vs: ", vs)
    #print("vs type:", type(vs))  # Print type of `vs`
    #print(type(vs[0, :]))        # Print type of the element of vs
    #print(ak.firsts(vs))

    #print("vs_pdgId: ", vs_pdgId)

    vs_flat["is_bb"] = ((vs_pdgId[:,:,0] == b_PDGID) & (vs_pdgId[:,:,1] == b_PDGID))
    vs_flat["is_cc"] = ((vs_pdgId[:,:,0] == c_PDGID) & (vs_pdgId[:,:,1] == c_PDGID)) 
    vs_flat["is_cs"] = ((vs_pdgId[:,:,0] == c_PDGID) & (vs_pdgId[:,:,1] == s_PDGID)) | ((vs_pdgId[:,:,0] == s_PDGID) & (vs_pdgId[:,:,1] == c_PDGID))

    GenVVars["GenVis_bb"] = vs_flat["is_bb"].to_numpy()
    GenVVars["GenVis_cc"] = vs_flat["is_cc"].to_numpy()
    GenVVars["GenVis_cs"] = vs_flat["is_cs"].to_numpy()
 
    #quarks of the first jet: W/Z -> qq
    #q_v1 = ak.firsts(vs_children[:, 0:1])
    q_v1 = vs_children[:, 0]
    delta_r = fatjets.metric_table(q_v1)
    matched_mask = delta_r < 0.8
    fatjets["NumQMatchedV1"] = ak.sum(matched_mask, axis=2)

    matched_to_v = fatjets.metric_table(vs) < 0.8  # metric_table returns the deltaR between the fatjet and the W/Z
    is_fatjet_matched = ak.any(matched_to_v, axis=2) # checks if any of the fatjets is matched to the W/Z

    #print("GenVVars: ", GenVVars["GenVChildren"])

    fatjets["VMatch"] = is_fatjet_matched # fatjets["VMatch"] is a boolean array that checks if the fatjet is matched to the W/Z
    #fatjets["NumQMatchedV1"] = ak.sum(fatjets.metric_table(q_v1) < 0.8, axis=2) # fatjets["NumQMatchedV1"] is the number of quarks matched to the first jet


    num_fatjets = 2
    bbFatJetVars = {
        f"bbFatJet{var}": pad_val(fatjets[var], num_fatjets, axis=1)
        for var in [
            "VMatch",
            "NumQMatchedV1",
        ]
    }

    return {**GenVVars, **bbFatJetVars}
