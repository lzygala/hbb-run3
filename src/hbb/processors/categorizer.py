from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import awkward as ak
import dask_awkward as dak
import numpy as np
from coffea.analysis_tools import PackedSelection, Weights
from hist.dask import Hist

from hbb.corrections import (
    add_btag_weights,
    add_muon_weights,
    add_pdf_weight,
    add_photon_weights,
    add_pileup_weight,
    add_ps_weight,
    add_scalevar_3pt,
    add_scalevar_7pt,
    apply_jerc,
    correct_met,
    correct_muons,
    get_jetveto_event,
    lumiMasks,
    mupt_variations,
)
from hbb.jerc_eras import jerc_variations, run_map
from hbb.processors.SkimmerABC import SkimmerABC
from hbb.taggers import b_taggers

from .GenSelection import (
    bosonFlavor,
    gen_selection_Hbb,
    gen_selection_V,
    gen_selection_Vg,
    getBosons,
)
from .objects import (
    good_ak4jets,
    good_ak8jets,
    good_electrons,
    good_muons,
    good_photons,
    set_ak4jets,
    set_ak8jets,
    tight_photons,
)

logger = logging.getLogger(__name__)


def update(events, collections):
    """Return a shallow copy of events array with some collections swapped out"""
    out = events
    for name, value in collections.items():
        out = ak.with_field(out, value, name)
    return out


# mapping samples to the appropriate function for doing gen-level selections
gen_selection_dict = {
    "Hto2B": gen_selection_Hbb,
    "Wto2Q-": gen_selection_V,
    "Zto2Q-": gen_selection_V,
    "ZGto2QG-": gen_selection_Vg,
}


class categorizer(SkimmerABC):
    def __init__(
        self,
        year="2022",
        nano_version="v12",
        xsecs: dict = None,
        systematics=False,
        save_skim=False,
        skim_outpath="",
        btag_eff=False,
        save_skim_nosysts=False,
    ):
        super().__init__()

        self.XSECS = xsecs if xsecs is not None else {}  # in pb

        self._year = year
        self._nano_version = nano_version
        self._systematics = systematics
        self._skip_syst = save_skim_nosysts
        self._save_skim = save_skim
        if self._skip_syst:
            self._save_skim = True
        self._skim_outpath = skim_outpath
        self._btag_eff = btag_eff
        self._btagger, self._btag_wp = "btagPNetB", "M"
        if year == "2024":
            self._btagger = "btagUParTAK4B"
        self._btag_cut = b_taggers[self._year]["AK4"][self._btagger][self._btag_wp]
        self._mupt_type = "ptcorr"

        with Path("src/hbb/dilep_triggers.json").open() as f:
            self._triggers = json.load(f)

        # https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFiltersRun2
        with Path("src/hbb/metfilters.json").open() as f:
            self._met_filters = json.load(f)

        self.make_output = lambda: {
            "sumw": {},
            "cutflow": Hist.new.StrCat([], growth=True, name="region", label="Region")
            .StrCat([], growth=True, name="dataset", label="Dataset")
            .Reg(15, 0, 15, name="cut", label="Cut index")
            .Variable([0, 1, 2, 3, 4], name="genflavor", label="Gen. jet flavor")
            .Weight(),
            "btagWeight": Hist.new.Reg(50, 0, 3, name="val", label="BTag correction").Weight(),
            "skim": {},
        }

        # btag efficiency plots - binning according to:
        # https://btv-wiki.docs.cern.ch/PerformanceCalibration/fixedWPSFRecommendations/#b-tagging-efficiencies-in-simulation
        self.make_btag_output = lambda: (
            Hist.new.StrCat([], growth=True, name="tagger", label="Tagger")
            .Reg(2, 0, 2, name="passWP", label="passWP")
            .Variable([0, 4, 5], name="flavor", label="Jet hadronFlavour")
            .Variable([20, 30, 50, 70, 100, 140, 200, 300, 600, 1000], name="pt", label="Jet pt")
            .Reg(4, 0, 2.5, name="abseta", label="Jet abseta")
            .Weight()
        )

    def process(self, events):

        # process only nominal case
        if self._skip_syst or not self._save_skim:
            return {"nominal": self.process_shift(events, "nominal")}

        """
        Add `Up and Down` to total list of energy variations
        Muon Energy: `MuonPTScale and MuonPTResolution` defined in mupt_variations
        Jet Energy: `JES, JER, UES` defined in jerc_variations
        """
        total_variations = (
            ["nominal"]
            + [f"{var}_{dir}" for var in jerc_variations for dir in ["Up", "Down"]]
            + [f"{var}_{dir}" for var in mupt_variations for dir in ["Up", "Down"]]
        )

        """
        run processor for each shift defined in total_variations
        return output as dict {variation: output}
        """
        return {var: self.process_shift(events, var) for var in total_variations}

    def add_weights(
        self, weights, events, dataset, btag_jets, muons=None, photons=None
    ) -> tuple[dict, dict]:
        """Adds weights and variations, saves totals for all norm preserving weights and variations"""
        weights.add("genweight", events.genWeight)

        btag_SF = ak.ones_like(events.run)
        if not self._skip_syst:
            add_pileup_weight(weights, self._year, events.Pileup.nPU)
            add_ps_weight(weights, events.PSWeight)
            if not self._btag_eff:
                btag_SF = add_btag_weights(
                    weights, btag_jets, self._btagger, self._btag_wp, self._year, dataset
                )

            # Easier to save nominal weights for rest of MC with all of the syst names for grabbing columns in post-processing
            flag_syst = ("Hto2B" in dataset) or ("Hto2C" in dataset) or ("VBFZto" in dataset)
            add_pdf_weight(weights, getattr(events, "LHEPdfWeight", None) if flag_syst else None)
            add_scalevar_7pt(
                weights, getattr(events, "LHEScaleWeight", None) if flag_syst else None
            )
            add_scalevar_3pt(
                weights, getattr(events, "LHEScaleWeight", None) if flag_syst else None
            )

            if muons is not None:
                add_muon_weights(weights, self._year, muons, self._mupt_type)
            if photons is not None:
                add_photon_weights(weights, self._year, photons)

        logger.debug("weights", extra=weights._weights.keys())
        # logger.debug(f"Weight statistics: {weights.weightStatistics!r}")

        # dictionary of all weights and variations
        weights_dict = {}
        # dictionary of total # events for norm preserving variations for normalization in postprocessing
        totals_dict = {}

        # nominal
        weights_dict["weight"] = weights.weight()

        # systematics
        for systematic in weights.variations:
            weights_dict[systematic] = weights.weight(modifier=systematic)

        ###################### Normalization (Step 1) ######################
        # strip the year from the dataset name
        dataset_no_year = dataset.replace(f"{self._year}_", "")
        weight_norm = self.get_dataset_norm(self._year, dataset_no_year)
        # normalize all the weights to xsec, needs to be divided by totals in Step 2 in post-processing
        for key, val in weights_dict.items():
            weights_dict[key] = val * weight_norm

        # save the unnormalized weight, to confirm that it's been normalized in post-processing
        weights_dict["weight_noxsec"] = weights.weight()

        return weights_dict, totals_dict, btag_SF

    def process_shift(self, events, shift_name):

        dataset = events.metadata["dataset"]
        isRealData = not hasattr(events, "genWeight")
        selection = PackedSelection()
        output = self.make_output() if not self._btag_eff else self.make_btag_output()
        weights = Weights(None, storeIndividual=True)
        if shift_name == "nominal" and not isRealData and not self._btag_eff:
            output["sumw"][dataset] = ak.sum(events.genWeight)

        trigger = ak.values_astype(ak.zeros_like(events.run), bool)
        for t in self._triggers[self._year]:
            if t in events.HLT.fields:
                trigger = trigger | events.HLT[t]
        selection.add("trigger", trigger)
        del trigger

        if isRealData:
            selection.add("lumimask", lumiMasks[self._year[:4]](events.run, events.luminosityBlock))
        else:
            selection.add("lumimask", ak.values_astype(ak.ones_like(events.run), bool))

        metfilter = ak.values_astype(ak.ones_like(events.run), bool)
        for flag in self._met_filters[self._year]["data" if isRealData else "mc"]:
            if flag in events.Flag.fields:
                metfilter = metfilter & events.Flag[flag]
        selection.add("metfilter", metfilter)
        del metfilter

        mc_run = "mc"
        if isRealData:
            for keys, value in run_map.items():
                if any(k in dataset for k in keys):
                    mc_run = value
                    break
        jec_key = f"{self._year}_{mc_run}"

        fatjets = set_ak8jets(
            events.FatJet, self._year, self._nano_version, ak.ones_like(events.run) #events.Rho.fixedGridRhoFastjetAll
        )
        jets = set_ak4jets(
            events.Jet, self._year, self._nano_version, ak.ones_like(events.run) #events.Rho.fixedGridRhoFastjetAll
        )

        if self._nano_version == "v14_private":
            # subjets in PFNano reprocessing break the fatjet jercs for whatever reason
            keep_fields = [
                f
                for f in fatjets.fields
                if (
                    ("nConstituents" not in f)
                    and ("IdxG" not in f)
                    and ("Idx1G" not in f)
                    and ("Idx2G" not in f)
                )
            ]

            fatjets = ak.zip(
                {f: fatjets[f] for f in keep_fields}, with_name="FatJet", behavior=fatjets.behavior
            )

        met = events.PuppiMET
        # Apply jerc corrections to jets, fatjets, and met collections
        if not self._skip_syst:
            jets = apply_jerc(jets, "AK4", self._year, jec_key)
            fatjets = apply_jerc(fatjets, "AK8", self._year, jec_key)
            met = correct_met(met, jets)  # PuppiMET Recommended for Run3

        # Select jets, fatjets, and met collections according to jerc variation shift
        if shift_name != "nominal" and "Muon" not in shift_name:
            var, direction = shift_name.split("_")
            attr = jerc_variations[var]
            if var in ("JES", "JER"):
                jets = getattr(getattr(jets, attr), direction.lower())
                fatjets = getattr(getattr(fatjets, attr), direction.lower())
                met = getattr(getattr(met, attr), direction.lower())
            elif var == "UES":
                met = getattr(getattr(met, attr), direction.lower())

        cut_jetveto = get_jetveto_event(jets, self._year)
        selection.add("ak4jetveto", cut_jetveto)

        
        # ----- LEPTONS -----
        muons = correct_muons(events.Muon, events, self._year, isRealData)
        if shift_name != "nominal" and "Muon" in shift_name:
            var, direction = shift_name.split("_")
            self._mupt_type = f"{mupt_variations[var]}_{direction.lower()}"

        goodmuons = good_muons(muons, self._mupt_type)
        nmuons = ak.num(goodmuons, axis=1)
        leadingmuon = ak.firsts(goodmuons)
        ttbarmuon = ak.firsts(goodmuons[getattr(goodmuons, self._mupt_type) > 55.0])
        # low pt muons break sf (lower bound 15GeV)

        goodelectrons = good_electrons(events.Electron)
        nelectrons = ak.num(goodelectrons, axis=1)

        goodmuons["flavor"] = ak.zeros_like(goodmuons.pt)
        goodelectrons["flavor"] = ak.ones_like(goodelectrons.pt)

        # 2L Leading Leptons
        all_leps = ak.concatenate([goodmuons, goodelectrons], axis=1)
        all_leps = ak.with_name(all_leps, "PtEtaPhiMLorentzVector")
        leps_ordered = ak.argsort(all_leps.pt, ascending=False)
        leadinglep = ak.firsts(all_leps[leps_ordered][:, 0:1])
        subleadinglep = ak.firsts(all_leps[leps_ordered][:, 1:2])
        lep_mass = (leadinglep + subleadinglep).mass

        selection.add("highmet", met.pt > 100.0)

        selection.add("noleptons", (nmuons == 0) & (nelectrons == 0))
        selection.add("twoleptons", (ak.num(all_leps) == 2))
        selection.add("oppsign", (leadinglep.charge * subleadinglep.charge) == -1)
        selection.add("lepdR", (leadinglep.delta_r(subleadinglep) > 0.5))
        selection.add("sameflavor", leadinglep.flavor == subleadinglep.flavor)

        selection.add("inZpeak", ((lep_mass) <= 96) & ((lep_mass) >= 86))
        selection.add("notZpeak", ((lep_mass) >= 96) | ((lep_mass) <= 86))

        selection.add("onemuon", (nmuons == 1) & (nelectrons == 0))
        selection.add(
            "muonkin", (getattr(leadingmuon, self._mupt_type) > 55.0) & (abs(leadingmuon.eta) < 2.1)
        )


        # ---- Higgs AK8 ----
        goodfatjets = good_ak8jets(fatjets)
        dR_leadlep = goodfatjets.delta_r(leadinglep)
        dR_subleadlep = goodfatjets.delta_r(subleadinglep)
        ak8_outside_leps = goodfatjets[(dR_leadlep > 0.8) & (dR_subleadlep > 0.8)]

        if "v12" in self._nano_version:
            xbbfatjets = ak8_outside_leps[ak.argsort(ak8_outside_leps.pnetXbbVsQCD, axis=1, ascending=False)]
        else:
            xbbfatjets = ak8_outside_leps[ak.argsort(ak8_outside_leps.ParTPXbbVsQCD, axis=1, ascending=False)]

        candidatejet = ak.firsts(xbbfatjets)

        selection.add(
            "minjetkin",
            (candidatejet.pt >= 250) & (candidatejet.msd >= 40.0)
            # & (candidatejet.msd < 201.0)
            & (abs(candidatejet.eta) < 2.5),
        )

        # ---- AK4 Jets ----
        goodjets = good_ak4jets(jets)
        dR = goodjets.delta_r(candidatejet)
        ak4_outside_ak8 = goodjets[dR > 0.8]

        #AK4 b-jet vetos
        selection.add(
            "antiak4btagMedium",
            ak.max(getattr(ak4_outside_ak8, self._btagger), axis=1, mask_identity=False)
            < self._btag_cut,
        )
        selection.add(
            "ak4btagMedium08",
            ak.max(getattr(ak4_outside_ak8, self._btagger), axis=1, mask_identity=False)
            > self._btag_cut,
        )

        # ---- VBF Jets ----
        dR_higgs = goodjets.delta_r(candidatejet)
        dR_leadlep = goodjets.delta_r(leadinglep)
        dR_subleadlep = goodjets.delta_r(subleadinglep)
        ak4_outside_objs = goodjets[((dR_higgs > 0.8) & (dR_leadlep > 0.4) & (dR_subleadlep > 0.4))]

        pairs = ak.combinations(ak4_outside_objs, 2, fields=["j1", "j2"])
        deta_pairs = abs(pairs.j1.eta - pairs.j2.eta)
        max_idx = ak.argmax(deta_pairs, axis=1, keepdims=True)

        # VBF specific variables
        jet1_away = ak.firsts(pairs.j1[max_idx])
        jet2_away = ak.firsts(pairs.j2[max_idx])

        vbf_deta = abs(jet1_away.eta - jet2_away.eta)
        vbf_mjj = (jet1_away + jet2_away).mass
        vbf_deta = ak.fill_none(vbf_deta, -1)
        vbf_mjj = ak.fill_none(vbf_mjj, -1)

        isvbf = (vbf_deta > 2.5) & (vbf_mjj > 750)
        isvbf = ak.fill_none(isvbf, False)
        isnotvbf = ak.fill_none(~isvbf, True)

        selection.add("isvbf", isvbf)

        gen_variables = {}
        btag_SF = ak.ones_like(events.run)
        if isRealData:
            genflavor = ak.zeros_like(candidatejet.pt)
            genBosonPt = ak.zeros_like(candidatejet.pt)
        else:
            # signal regions
            weights_dict, totals_temp, btag_SF = self.add_weights(
                weights, events, dataset, ak4_outside_ak8
            )

            for d, gen_func in gen_selection_dict.items():
                if d in dataset:
                    # match goodfatjets
                    gen_variables = gen_func(events, goodfatjets)

            bosons = getBosons(events.GenPart)
            matchedBoson = candidatejet.nearest(bosons, axis=None, threshold=0.8)
            match_mask = (abs(candidatejet.pt - matchedBoson.pt) / matchedBoson.pt < 0.5) & (
                abs(candidatejet.msd - matchedBoson.mass) / matchedBoson.mass < 0.3
            )
            selmatchedBoson = ak.mask(matchedBoson, match_mask)
            genflavor = bosonFlavor(selmatchedBoson)
            genBosonPt = ak.fill_none(ak.firsts(bosons.pt), 0)

        # softdrop mass, 0 for genflavor == 0
        msd_matched = candidatejet.msd * (genflavor > 0) + candidatejet.msd * (genflavor == 0)

        regions = {
            "signal-wwh": [
                "trigger",
                "lumimask",
                "metfilter",
                "ak4jetveto",
                "twoleptons",
                "highmet",
                "oppsign",
                "lepdR",
                "notZpeak",
                "minjetkin",
                "antiak4btagMedium",
                "isvbf",

            ],
            "signal-zzh": [
                "trigger",
                "lumimask",
                "metfilter",
                "ak4jetveto",
                "twoleptons",
                "highmet",
                "oppsign",
                "lepdR",
                "inZpeak",
                "minjetkin",
                "antiak4btagMedium",
                "isvbf",
            ],
        }

        btag_eff_cuts = [
            "trigger",
            "lumimask",
            "metfilter",
            "ak4jetveto",
            "minjetkin",
            "lowmet",
            "noleptons",
        ]

        tic = time.time()

        nominal_weight = ak.ones_like(events.run) if isRealData else weights_dict["weight"]
        gen_weight = ak.ones_like(events.run) if isRealData else events.genWeight

        if self._btag_eff:
            cut = selection.all(*btag_eff_cuts)
            flat_gj = ak.flatten(goodjets)

            output.fill(
                tagger=self._btagger,
                abseta=self.normalize(abs(flat_gj.eta), cut),
                pt=self.normalize(flat_gj.pt, cut),
                flavor=self.normalize(flat_gj.hadronFlavour, cut),
                passWP=self.normalize(getattr(flat_gj, self._btagger) > self._btag_cut, cut),
            )
            return output

        output_array = None
        if self._save_skim:

            output_array = {
                "GenBoson_pt": genBosonPt,
                "GenFlavor": genflavor,
                "nFatJet": ak.num(goodfatjets, axis=1),
                "nJet": ak.num(goodjets, axis=1),
                "FatJet0_pt": candidatejet.pt,
                "FatJet0_phi": candidatejet.phi,
                "FatJet0_eta": candidatejet.eta,
                "FatJet0_msd": candidatejet.msd,
                "FatJet0_msdmatched": msd_matched,
                "FatJet0_n2b1": candidatejet.n2b1,
                "FatJet0_n3b1": candidatejet.n3b1,
                "FatJet0_pnetMass": candidatejet.pnetmass,
                "FatJet0_pnetTXbb": candidatejet.particleNet_XbbVsQCD,
                "FatJet0_pnetTXcc": candidatejet.particleNet_XccVsQCD,
                "FatJet0_pnetTXqq": candidatejet.particleNet_XqqVsQCD,
                "FatJet0_pnetTXgg": candidatejet.particleNet_XggVsQCD,
                "FatJet0_pnetTQCD": candidatejet.particleNet_QCD,
                "FatJet0_pnetXbbXcc": candidatejet.pnetXbbXcc,
                "VBFPair_mjj": vbf_mjj,
                "VBFPair_deta": vbf_deta,
                "MET": met.pt,
                "LeadingLep_pt": leadinglep.pt,
                "LeadingLep_flavor": leadinglep.flavor,
                "LeadingLep_phi": leadinglep.phi,
                "LeadingLep_eta": leadinglep.eta,
                "SubLeadingLep_pt": subleadinglep.pt,
                "SubLeadingLep_flavor": subleadinglep.flavor,
                "SubLeadingLep_phi": subleadinglep.phi,
                "SubLeadingLep_eta": subleadinglep.eta,
                "weight": nominal_weight,
                "genWeight": gen_weight,
                **gen_variables,
            }

            # reduced output array for energy variation shift
            energy_var_array = {
                "GenBoson_pt": genBosonPt,
                "GenFlavor": genflavor,
                "FatJet0_pt": candidatejet.pt,
                "FatJet0_msd": candidatejet.msd,
                "FatJet0_msdmatched": msd_matched,
                "FatJet0_pnetTXbb": candidatejet.particleNet_XbbVsQCD,
                "FatJet0_pnetTXcc": candidatejet.particleNet_XccVsQCD,
                "FatJet0_pnetXbbXcc": candidatejet.pnetXbbXcc,
                "VBFPair_mjj": vbf_mjj,
                "weight": nominal_weight,
                "genWeight": gen_weight,
            }

            if "v12" not in self._nano_version:
                parT_array = {
                    "FatJet0_ParTPQCD": candidatejet.ParTPQCD,
                    "FatJet0_ParTPXbb": candidatejet.ParTPXbb,
                    "FatJet0_ParTPXcc": candidatejet.ParTPXcc,
                    "FatJet0_ParTPXqq": candidatejet.ParTPXqq,
                    "FatJet0_ParTPXcs": candidatejet.ParTPXcs,
                    "FatJet0_ParTPXbbVsQCD": candidatejet.ParTPXbbVsQCD,
                    "FatJet0_ParTPXccVsQCD": candidatejet.ParTPXccVsQCD,
                    "FatJet0_ParTPXbbXcc": candidatejet.ParTPXbbXcc,
                    "FatJet0_ParTmassGeneric": candidatejet.ParTmassGeneric,
                    "FatJet0_ParTmassX2p": candidatejet.ParTmassX2p
                }
                output_array = {**output_array, **parT_array}

                energy_var_array_parT = {
                    "FatJet0_ParTPXbbVsQCD": candidatejet.ParTPXbbVsQCD,
                    "FatJet0_ParTPXccVsQCD": candidatejet.ParTPXccVsQCD,
                    "FatJet0_ParTPXbbXcc": candidatejet.ParTPXbbXcc,
                }
                energy_var_array = {**energy_var_array, **energy_var_array_parT}

            # extra variables for big array
            output_array_extra = {
                # AK4 Jets away from FatJet0
                "Jet0_pt": jet1_away.pt,
                "Jet0_eta": jet1_away.eta,
                "Jet0_phi": jet1_away.phi,
                "Jet0_mass": jet1_away.mass,
                "Jet0_btagPNetB": jet1_away.btagPNetB,
                "Jet0_btagPNetCvB": jet1_away.btagPNetCvB,
                "Jet0_btagPNetCvL": jet1_away.btagPNetCvL,
                "Jet0_btagPNetQvG": jet1_away.btagPNetQvG,
                "Jet1_pt": jet2_away.pt,
                "Jet1_eta": jet2_away.eta,
                "Jet1_phi": jet2_away.phi,
                "Jet1_mass": jet2_away.mass,
                "Jet1_btagPNetB": jet2_away.btagPNetB,
                "Jet1_btagPNetCvB": jet2_away.btagPNetCvB,
                "Jet1_btagPNetCvL": jet2_away.btagPNetCvL,
                "Jet1_btagPNetQvG": jet2_away.btagPNetQvG,
            }

        def skim(region, output_array):
            selections = regions[region]
            cut = selection.all(*selections)

            # to debug...
            # print(output_array.compute())
            # print(output_array[cut].compute())

            if "root:" in self._skim_outpath:
                skim_path = f"{self._skim_outpath}/{shift_name.replace('_', '')}/{self._year}/{dataset}/{region}"
            else:
                skim_path = (
                    Path(self._skim_outpath)
                    / shift_name.replace("_", "")
                    / self._year
                    / dataset
                    / region
                )
                skim_path.mkdir(parents=True, exist_ok=True)
            print("Saving skim to: ", skim_path)

            output["skim"][region] = dak.to_parquet(
                output_array[cut],
                str(skim_path),
                compute=False,
            )

            if shift_name == "nominal":

                # Fill cutflow hist
                allcuts = set()
                cut = selection.all(*allcuts)
                output["cutflow"].fill(
                    dataset=dataset,
                    region=region,
                    genflavor=self.normalize(genflavor, None),
                    cut=0,
                    weight=nominal_weight,
                )
                for i, cut in enumerate(selections):
                    allcuts.add(cut)
                    cumulative_cut = selection.all(*allcuts)
                    output["cutflow"].fill(
                        dataset=dataset,
                        region=region,
                        genflavor=self.normalize(genflavor, cumulative_cut),
                        cut=i + 1,
                        weight=nominal_weight[cumulative_cut],
                    )

                # Fill btag SF hist
                cut = selection.all(*selections)
                output["btagWeight"].fill(val=self.normalize(btag_SF, cut))

        if self._save_skim:
            if shift_name == "nominal":
                for region in regions:
                    if region == "signal-all":
                        skim(region, ak.zip({**output_array, **output_array_extra}, depth_limit=1))
                    else:
                        if isRealData:
                            skim(region, ak.zip(output_array, depth_limit=1))
                        else:
                            if "signal" in region:
                                skim(
                                    region, ak.zip({**output_array, **weights_dict}, depth_limit=1)
                                )

            else:  # energy variation shift case
                for region in regions:
                    if region != "signal-all":
                        if isRealData:
                            skim(region, ak.zip(energy_var_array, depth_limit=1))
                        else:
                            if "signal" in region:
                                skim(
                                    region,
                                    ak.zip({**energy_var_array, **weights_dict}, depth_limit=1),
                                )

        toc = time.time()
        output["filltime"] = toc - tic
        if shift_name is None:
            output["weightStats"] = weights.weightStatistics
        return output

    def postprocess(self, accumulator):
        pass
