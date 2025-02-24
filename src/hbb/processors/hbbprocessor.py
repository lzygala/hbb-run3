"""
Skimmer for simple analysis with FatJets.
"""

from __future__ import annotations
import logging
import time
from collections import OrderedDict

import awkward as ak
import numpy as np
from coffea import processor
from coffea.analysis_tools import PackedSelection, Weights

from .. import utils
from hbb import common_vars
from .GenSelection import gen_selection_V, gen_selection_HHbbbb, gen_selection_Hbb
from .objects import (
    get_ak8jets,
    good_ak8jets,
    veto_muons,
    veto_electrons,
)
from .SkimmerABC import SkimmerABC
from ..utils import P4, add_selection, pad_val


# mapping samples to the appropriate function for doing gen-level selections
gen_selection_dict = {
    "Zto2Q": gen_selection_V,
    "Zto2Nu": gen_selection_V,
    "Wto2Q": gen_selection_V,
    "WtoLNu": gen_selection_V,
    "HHto4B": gen_selection_HHbbbb,
    "Hto2B": gen_selection_Hbb,
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class HbbProcessor(SkimmerABC):
    """
    Skims nanoaod files, saving selected branches and events passing preselection cuts
    (and triggers for data).
    """

    # key is name in nano files, value will be the name in the skimmed output
    skim_vars = {  # noqa: RUF012
        "FatJet": {
            **P4,
            "Txbb": "PNetTXbb",
            "Txjj": "PNetTXjj",
            "Tqcd": "PNetQCD",
            "Txgg": "PNetTXgg",       # added
            "Txcc": "PNetTXcc",       # added
            "TXqq_legacy": "PNetTXqq", # added
            #"WvsQCD": "PNetWVsQCD",
            "PQCDb": "PNetQCD1HF",
            "PQCDbb": "PNetQCD2HF",
            "PQCDothers": "PNetQCD0HF",
            "particleNet_mass": "PNetMass",
            "particleNet_massraw": "PNetMassRaw",
            "t21": "Tau2OverTau1",
            "t32": "Tau3OverTau2",
            "rawFactor": "rawFactor",
            "msoftdrop": "msoftdrop",
            "ParTPQCD1HF": "ParTPQCD1HF",
            "ParTPQCD2HF": "ParTPQCD2HF",
            "ParTPQCD0HF": "ParTPQCD0HF",
            "ParTPXbb": "ParTPXbb",
            "ParTPXcc": "ParTPXcc",
            "ParTPXcs": "ParTPXcs",
            "ParTPXgg": "ParTPXgg",
            "ParTPXqq": "ParTPXqq",
            "particleNet_mass_legacy": "Mass_legacy",
            "ParTmassRes": "ParTmassRes",
            "ParTmassVis": "ParTmassVis",
        },
    }

    def __init__(
        self,
        xsecs=None,
    ):
        super().__init__()

        self.XSECS = xsecs if xsecs is not None else {}  # in pb

        self.HLTs = {
            "2023": [
                # Add triggers here for the year 2023
                
                # offline triggers
                "QuadPFJet70_50_40_35_PFBTagParticleNet_2BTagSum0p65",
                "PFHT1050",
                "AK8PFJet230_SoftDropMass40_PFAK8ParticleNetBB0p35",
                "AK8PFJet250_SoftDropMass40_PFAK8ParticleNetBB0p35",
                "AK8PFJet275_SoftDropMass40_PFAK8ParticleNetBB0p35",
                "AK8PFJet230_SoftDropMass40",
                "AK8PFJet425_SoftDropMass40",
                "AK8PFJet400_SoftDropMass40",
                "AK8DiPFJet250_250_MassSD50",
                "AK8DiPFJet260_260_MassSD30",
                "AK8PFJet420_MassSD30",
                "AK8PFJet230_SoftDropMass40_PNetBB0p06",
                "AK8PFJet230_SoftDropMass40_PNetBB0p10",
                "AK8PFJet250_SoftDropMass40_PNetBB0p06",
                # parking triggers
                # HHparking
                #"PFHT280_QuadPFJet30_PNet2BTagMean0p55",
                # VBFparking
                # https://its.cern.ch/jira/browse/CMSHLT-3058
                #"DiJet110_35_Mjj650_PFMET110",
                #"TripleJet110_35_35_Mjj650_PFMET110",
                #"VBF_DiPFJet80_45_Mjj650_PFMETNoMu85",
                #"VBF_DiPFJet110_35_Mjj650",
                #"VBF_DiPFJet110_35_Mjj650_TriplePFJet",
                #"VBF_DiPFJet110_40_Mjj1000_Detajj3p5",
                #"VBF_DiPFJet110_40_Mjj1000_Detajj3p5_TriplePFJet",
                #"VBF_DiJet_60_30_Mass500_DiJet50",
                #"VBF_DiJet_110_35_Mass620",
                # SingleMuonparking
                #"Mu12_IP6",
            ],
        }

        # https://twiki.cern.ch/twiki/bin/viewauth/CMS/MissingETOptionalFiltersRun2#Run_3_recommendations
        self.met_filters = [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "eeBadScFilter",
            "hfNoisyHitsFilt",
        ]



        self._accumulator = processor.dict_accumulator({})

    @property
    def accumulator(self):
        return self._accumulator

    def process(self, events: ak.Array):
        """Runs event processor for different types of jets"""

        start = time.time()
        print("Starting")
        print("# events", len(events))

        year = events.metadata["dataset"].split("_")[0]
        dataset = "_".join(events.metadata["dataset"].split("_")[1:])

        isData = not hasattr(events, "genWeight")

        gen_weights = events["genWeight"].to_numpy() if not isData else None

        n_events = len(events) if isData else np.sum(gen_weights)

        cutflow = OrderedDict()
        cutflow["all"] = n_events
        selection = PackedSelection()
        selection_args = (selection, cutflow, isData, gen_weights)

        #########################
        # Object definitions
        #########################
        print("Starting object definition", f"{time.time() - start:.2f}")

        num_fatjets = 2  # number to save


        fatjets = get_ak8jets(events.FatJet)


        fatjets = good_ak8jets(fatjets, 300, 2.5, 40, 40)
        #fatjets["WVsQCD"] = events.FatJet.particleNet_WVsQCD
        #fatjets["Txbb"] = fatjets.particleNet_XbbVsQCD
        

        ak4_jets = events.Jet

        veto_muon_sel = veto_muons(events.Muon)
        veto_electron_sel = veto_electrons(events.Electron)
        
        print("Object definition", f"{time.time() - start:.2f}")

        #########################
        # Derive variables
        #########################

        # Gen variables - saving HH and bbbb 4-vector info
        genVars = {}
        for d in gen_selection_dict:
            if d in dataset:
                vars_dict = gen_selection_dict[d](events, ak4_jets, fatjets, selection_args, P4)
                genVars = {**genVars, **vars_dict}


        # Add LHE_HT and LHE_Vpt to genVars
        #genVars["LHE_HT"] = events.LHE.HT.to_numpy()
        #genVars["LHE_Vpt"] = events.LHE.Vpt.to_numpy()

        # used for normalization to cross section below
        gen_selected = (
            selection.all(*selection.names)
            if len(selection.names)
            else np.ones(len(events)).astype(bool)
        )

        # FatJet variables
        fatjet_skimvars = self.skim_vars["FatJet"]
        ak8FatJetVars = {
            f"ak8FatJet{key}": pad_val(fatjets[var], num_fatjets, axis=1)
            for (var, key) in fatjet_skimvars.items()
        }

        print("FatJet vars", f"{time.time() - start:.2f}")


        HLTs = [
            # offline triggers
            "QuadPFJet70_50_40_35_PFBTagParticleNet_2BTagSum0p65",
            "PFHT1050",
            "AK8PFJet230_SoftDropMass40_PFAK8ParticleNetBB0p35",
            "AK8PFJet250_SoftDropMass40_PFAK8ParticleNetBB0p35",
            "AK8PFJet275_SoftDropMass40_PFAK8ParticleNetBB0p35",
            "AK8PFJet230_SoftDropMass40",
            "AK8PFJet425_SoftDropMass40",
            "AK8PFJet400_SoftDropMass40",
            "AK8DiPFJet250_250_MassSD50",
            "AK8DiPFJet260_260_MassSD30",
            "AK8PFJet420_MassSD30",
            "AK8PFJet230_SoftDropMass40_PNetBB0p06",
            "AK8PFJet230_SoftDropMass40_PNetBB0p10",
            "AK8PFJet250_SoftDropMass40_PNetBB0p06",
            # parking triggers
            # HHparking
            #"PFHT280_QuadPFJet30_PNet2BTagMean0p55",
            # VBFparking
            # https://its.cern.ch/jira/browse/CMSHLT-3058
            #"DiJet110_35_Mjj650_PFMET110",
            #"TripleJet110_35_35_Mjj650_PFMET110",
            #"VBF_DiPFJet80_45_Mjj650_PFMETNoMu85",
            #"VBF_DiPFJet110_35_Mjj650",
            #"VBF_DiPFJet110_35_Mjj650_TriplePFJet",
            #"VBF_DiPFJet110_40_Mjj1000_Detajj3p5",
            #"VBF_DiPFJet110_40_Mjj1000_Detajj3p5_TriplePFJet",
            #"VBF_DiJet_60_30_Mass500_DiJet50",
            #"VBF_DiJet_110_35_Mass620",
            # SingleMuonparking
            #"Mu12_IP6",
        ]
        zeros = np.zeros(len(events), dtype="bool")
        HLTVars = {
            trigger: (
                events.HLT[trigger].to_numpy().astype(int)
                if trigger in events.HLT.fields
                else zeros
            )
            for trigger in HLTs
        }
        
        skimmed_events = {
            **genVars,
            **ak8FatJetVars,
            **HLTVars,
        }

        print("Vars", f"{time.time() - start:.2f}")

        #########################
        # Selection Starts
        #########################

        print("Selection", f"{time.time() - start:.2f}")

        # OR-ing HLT triggers
        for trigger in self.HLTs[year]:
            if trigger not in events.HLT.fields:
                logger.warning(f"Missing HLT {trigger}!")

        HLT_triggered = np.any(
            np.array(
                [events.HLT[trigger] for trigger in self.HLTs[year] if trigger in events.HLT.fields]
            ),
            axis=0,
        )


        #in HH4b code there is an if region == signal here

        # >=2 AK8 jets passing selections
        add_selection("ak8_numjets", (ak.num(fatjets) >= 1), *selection_args)

        #add_selection("ak8bb_txbb0", cut_txbb, *selection_args)

        # 0 veto leptons
        add_selection(
            "0lep",
            (ak.sum(veto_muon_sel, axis=1) == 0) & (ak.sum(veto_electron_sel, axis=1) == 0),
            *selection_args,
        )

        ######################
        # Weights
        ######################

        # used for normalization to cross section below
        gen_selected = (
            selection.all(*selection.names)
            if len(selection.names)
            else np.ones(len(events)).astype(bool)
        )

        totals_dict = {"nevents": n_events}

        if isData:
            skimmed_events["weight"] = np.ones(n_events)
        else:
            weights_dict, totals_temp = self.add_weights(
                events,
                year,
                dataset,
                gen_weights,
                gen_selected,
            )
            skimmed_events = {**skimmed_events, **weights_dict}
            totals_dict = {**totals_dict, **totals_temp}

        ##############################
        # Reshape and apply selections
        ##############################

        sel_all = selection.all(*selection.names) if len(selection.names) else np.ones(len(events)).astype(bool)

        #HERE
        

        
        skimmed_events = {
            key: value.reshape(len(skimmed_events["weight"]), -1)[sel_all]
            for (key, value) in skimmed_events.items()
        }

        dataframe = self.to_pandas(skimmed_events)
        fname = events.behavior["__events_factory__"]._partition_key.replace("/", "_") + ".parquet"
        self.dump_table(dataframe, fname)

        print("Return ", f"{time.time() - start:.2f}")
        return {year: {dataset: {"nevents": n_events, "cutflow": cutflow}}}

    def postprocess(self, accumulator):
        return accumulator

    def add_weights(
        self,
        events,
        year,
        dataset,
        gen_weights,
        gen_selected,
    ) -> tuple[dict, dict]:
        """Adds weights and variations, saves totals for all norm preserving weights and variations"""
        weights = Weights(len(events), storeIndividual=True)
        weights.add("genweight", gen_weights)

        logger.debug("weights", extra=weights._weights.keys())

        ###################### Save all the weights and variations ######################

        # these weights should not change the overall normalization, so are saved separately
        norm_preserving_weights = common_vars.norm_preserving_weights

        # dictionary of all weights and variations
        weights_dict = {}
        # dictionary of total # events for norm preserving variations for normalization in postprocessing
        totals_dict = {}

        # nominal
        weights_dict["weight"] = weights.weight()

        # norm preserving weights, used to do normalization in post-processing
        weight_np = weights.partial_weight(include=norm_preserving_weights)
        totals_dict["np_nominal"] = np.sum(weight_np[gen_selected])

        ###################### Normalization (Step 1) ######################

        weight_norm = self.get_dataset_norm(year, dataset)
        # normalize all the weights to xsec, needs to be divided by totals in Step 2 in post-processing
        for key, val in weights_dict.items():
            weights_dict[key] = val * weight_norm

        # save the unnormalized weight, to confirm that it's been normalized in post-processing
        weights_dict["weight_noxsec"] = weights.weight()

        return weights_dict, totals_dict
