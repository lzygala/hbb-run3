import logging
import numpy as np
import awkward as ak
import dask
import json
from coffea import processor
from hist.dask import Hist
from coffea.analysis_tools import Weights, PackedSelection
from boostedhiggs.common import (
    getBosons,
    bosonFlavor,
)
from boostedhiggs.corrections import (
    lumiMasks
)


logger = logging.getLogger(__name__)


def update(events, collections):
    """Return a shallow copy of events array with some collections swapped out"""
    out = events
    for name, value in collections.items():
        out = ak.with_field(out, value, name)
    return out


class test_processor(processor.ProcessorABC):
    def __init__(self, year='2017', jet_arbitration='pt', tagger='v2',
                 nnlops_rew=False, skipJER=False, tightMatch=False,
                 ak4tagger='deepJet',ewkHcorr=False,systematics=False
                 ):
        self._year = year
        self._tagger  = tagger
        self._ak4tagger = ak4tagger
        self._jet_arbitration = jet_arbitration
        self._skipJER = skipJER
        self._tightMatch = tightMatch
        self._ewkHcorr = ewkHcorr
        self._systematics = systematics
        self._ak4tagBranch = 'btagDeepFlavB'

        with open('fitting/muon_triggers.json') as f:
            self._muontriggers = json.load(f)

        with open('fitting/triggers.json') as f:
            self._triggers = json.load(f)

        # https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFiltersRun2                                                                    
        with open('fitting/metfilters.json') as f:
            self._met_filters = json.load(f)

        optbins = np.r_[np.linspace(0, 0.15, 30, endpoint=False), np.linspace(0.15, 1, 86)]
        self.make_output = lambda: {
            'sumw': {},
            'cutflow': Hist.new
                .StrCat([],growth=True, name="region", label='Region')
                .StrCat([],growth=True, name='dataset', label='Dataset')
                .Reg(15, 0, 15, name='cut', label='Cut index')
                .Variable([0, 1, 2, 3, 4], name='genflavor', label='Gen. jet flavor')
            ,
            'btagWeight': Hist.new
                .Reg(50, 0, 3, name='val', label='BTag correction')
                .Weight()
            ,
            'templates': Hist.new
                .StrCat([], growth=True, name='dataset', label='Dataset')
                .StrCat([], growth=True, name='region', label='Region')
                .StrCat([], growth=True, name='systematic', label='Systematic')
                .Variable([0, 1, 3, 4], name='genflavor', label='Gen. jet flavor')
                .Variable([400, 450, 500, 550, 600, 675, 800, 1200], name='pt1', label='Jet $p_{T}$ [GeV]')
                .Reg(23, 40, 201, name='msd1', label="Jet $m_{sd}$")
                .Variable([0, 0.4, 0.5, 0.64, 1], name='ddb1', label='Jet ddb score')
                .Variable([1000,2000,13000], name='mjj', label='$m_{jj}$ [GeV]')
                .Weight()
        }

    def process(self, events):
        isRealData = not hasattr(events, "genWeight")
        isQCDMC = 'QCD' in events.metadata['dataset']

        fatjets = events.FatJet
        jets = events.Jet
        met = events.MET

        shifts = [({"Jet": jets, "FatJet": fatjets, "MET": met}, None)]
        #TODO return processor.accumulate(self.process_shift(update(events, collections), name) for collections, name in shifts)
        return self.process_shift(events, None)

    def process_shift(self, events, shift_name):

        dataset = events.metadata['dataset']
        isRealData = not hasattr(events, "genWeight")
        isQCDMC = 'QCD' in dataset
        selection = PackedSelection()
        weights = Weights(None, storeIndividual=True)
        output = self.make_output()
        if shift_name is None and not isRealData:
            output['sumw'][dataset] = ak.sum(events.genWeight)

        total_entries = ak.num(events, axis=0)
        if isRealData:
            trigger = ak.values_astype(ak.zeros_like(events.run), bool)
            for t in self._triggers[self._year]:
                if t in events.HLT.fields:
                    trigger = trigger | events.HLT[t]
            selection.add('trigger', trigger)
            del trigger
        else:
            selection.add('trigger', ak.values_astype(ak.ones_like(events.run), bool))

        if isRealData:
            selection.add('lumimask', lumiMasks[self._year[:4]](events.run, events.luminosityBlock))
        else:
            selection.add('lumimask', ak.values_astype(ak.ones_like(events.run), bool))

        if isRealData:
            trigger = ak.values_astype(ak.zeros_like(events.run), bool)
            for t in self._muontriggers[self._year]:
                if t in events.HLT.fields:
                    trigger = trigger | events.HLT[t]
            selection.add('muontrigger', trigger)
            del trigger
        else:
            selection.add('muontrigger', ak.values_astype(ak.ones_like(events.run), bool))

        metfilter = ak.values_astype(ak.ones_like(events.run), bool)
        for flag in self._met_filters[self._year]['data' if isRealData else 'mc']:
            metfilter = dask.array.bitwise_and(metfilter, events.Flag[flag])
        selection.add('metfilter', metfilter)
        del metfilter

        fatjets = events.FatJet
        fatjets['msdcorr'] = fatjets.msoftdrop
        fatjets['qcdrho'] = 2 * np.log(fatjets.msdcorr / fatjets.pt)

        selection.add('2FJ', ak.num(fatjets, axis=1) == 2)
        selection.add('not2FJ', ak.num(fatjets, axis=1) != 2)

        candidatejet = fatjets[
            (fatjets.pt > 200)
            & (abs(fatjets.eta) < 2.5)
            & fatjets.isTight 
        ]

        candidatejet = candidatejet[:, :2]
        candidatejet = ak.firsts(candidatejet[ak.argmax(candidatejet.particleNet_XbbVsQCD, axis=1, keepdims=True)])

        bvl = candidatejet.particleNet_XbbVsQCD

        selection.add('minjetkin',
            (candidatejet.pt >= 450)
            & (candidatejet.pt < 1200)
            & (candidatejet.msdcorr >= 40.)
            & (candidatejet.msdcorr < 201.)
            & (abs(candidatejet.eta) < 2.5)
        )
        selection.add('minjetkinmu',
            (candidatejet.pt >= 400)
            & (candidatejet.pt < 1200)
            & (candidatejet.msdcorr >= 40.)
            & (candidatejet.msdcorr < 201.)
            & (abs(candidatejet.eta) < 2.5)
        )
        selection.add('jetid', candidatejet.isTight)
        selection.add('ddbpass', (bvl >= 0.5))

        jets = events.Jet
        jets = jets[
            (jets.pt > 30.)
            & (abs(jets.eta) < 5.0)
            & jets.isTight
        ]

        # only consider first 4 jets to be consistent with old framework
        jets = jets[:, :4]
        dphi = abs(jets.delta_phi(candidatejet))
        selection.add('antiak4btagMediumOppHem', ak.max(jets[dphi > np.pi / 2].btagDeepFlavB, axis=1, mask_identity=False) < 0.3086) 
        ak4_away = jets[dphi > 0.8]
        selection.add('ak4btagMedium08', ak.max(ak4_away.btagDeepFlavB, axis=1, mask_identity=False) > 0.3086) 

        met = events.MET
        selection.add('met', met.pt < 140.)

        # VBF specific variables                                                      
        dR = jets.delta_r(candidatejet)
        ak4_outside_ak8 = jets[dR > 0.8]

        jet1 = ak4_outside_ak8[:, 0:1]
        jet2 = ak4_outside_ak8[:, 1:2]

        deta = abs(ak.firsts(jet1).eta - ak.firsts(jet2).eta)
        mjj = ( ak.firsts(jet1) + ak.firsts(jet2) ).mass

        isvbf = ((deta > 3.5) & (mjj > 1000))
        isvbf = ak.fill_none(isvbf,False)
        selection.add('isvbf', isvbf)

        isnotvbf = ak.fill_none(~isvbf,True)
        selection.add('notvbf', isnotvbf)

        goodmuon = (
            (events.Muon.pt > 10)
            & (abs(events.Muon.eta) < 2.4)
            & (events.Muon.pfRelIso04_all < 0.25)
            & events.Muon.looseId
        )
        nmuons = ak.sum(goodmuon, axis=1)
        leadingmuon = ak.firsts(events.Muon[goodmuon])

        goodelectron = (
            (events.Electron.pt > 10)
            & (abs(events.Electron.eta) < 2.5)
            & (events.Electron.cutBased >= 2)
        )
        nelectrons = ak.sum(goodelectron, axis=1)

        ntaus = ak.sum(
            (
                (events.Tau.pt > 20)
                & (abs(events.Tau.eta) < 2.3)
                & (events.Tau.rawIso < 5)
                & (events.Tau.idDeepTau2017v2p1VSjet)
                & ak.all(events.Tau.metric_table(events.Muon[goodmuon]) > 0.4, axis=2)
                & ak.all(events.Tau.metric_table(events.Electron[goodelectron]) > 0.4, axis=2)
            ),
            axis=1,
        )

        selection.add('noleptons', (nmuons == 0) & (nelectrons == 0) & (ntaus == 0))
        selection.add('onemuon', (nmuons == 1) & (nelectrons == 0) & (ntaus == 0))
        selection.add('muonkin', (leadingmuon.pt > 55.) & (abs(leadingmuon.eta) < 2.1))
        selection.add('muonDphiAK8', abs(leadingmuon.delta_phi(candidatejet)) > 2*np.pi/3)

        if isRealData :
            genflavor = ak.zeros_like(candidatejet.pt)
            weights.add('genweight', ak.ones_like(events.run))
        else:
            weights.add('genweight', events.genWeight)

            bosons = getBosons(events.GenPart)
            matchedBoson = candidatejet.nearest(bosons, axis=None, threshold=0.8)
            if self._tightMatch:
                match_mask = ((candidatejet.pt - matchedBoson.pt)/matchedBoson.pt < 0.5) & ((candidatejet.msdcorr - matchedBoson.mass)/matchedBoson.mass < 0.3)
                selmatchedBoson = ak.mask(matchedBoson, match_mask)
                genflavor = bosonFlavor(selmatchedBoson)
            else:
                genflavor = bosonFlavor(matchedBoson)
            genBosonPt = ak.fill_none(ak.firsts(bosons.pt), 0)

            logger.debug("Weight statistics: %r" % weights.weightStatistics)

        msd_matched = candidatejet.msdcorr * (genflavor > 0) + candidatejet.msdcorr * (genflavor == 0)

        regions = {
            'signal-ggf': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','notvbf','not2FJ'],
            'signal-vh': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','notvbf','2FJ'],
            'signal-vbf': ['trigger','lumimask','metfilter','minjetkin','jetid','antiak4btagMediumOppHem','met','noleptons','isvbf'],
            'muoncontrol': ['muontrigger','lumimask','metfilter','minjetkinmu', 'jetid',  'ak4btagMedium08', 'onemuon', 'muonkin', 'muonDphiAK8'],
        }

        def normalize(val, cut):
            if cut is None:
                ar = ak.fill_none(val, np.nan)
                return ar
            else:
                ar = ak.fill_none(val[cut], np.nan)
                return ar

        import time
        tic = time.time()

        if shift_name is None:
            systematics = [None] + list(weights.variations)
        else:
            systematics = [shift_name]

        def fill(region, systematic, wmod=None):
            selections = regions[region]
            cut = selection.all(*selections)
            sname = 'nominal' if systematic is None else systematic
            if wmod is None:
                if systematic in weights.variations:
                    weight = weights.weight(modifier=systematic)[cut]
                else:
                    weight = weights.weight()[cut]
            else:
                weight = weights.weight()[cut] * wmod[cut]

            output['templates'].fill(
                dataset=dataset,
                region=region,
                systematic=sname,
                genflavor=normalize(genflavor,cut),
                pt1=normalize(candidatejet.pt, cut),
                msd1=normalize(msd_matched, cut),
                ddb1=normalize(bvl, cut),
                mjj=normalize(mjj, cut),
                weight=weight,
            )

        for region in regions:
            for systematic in systematics:
                if isRealData and systematic is not None:
                    continue
                fill(region, systematic)

        toc = time.time()
        output["filltime"] = toc - tic
        if shift_name is None:
            output["weightStats"] = weights.weightStatistics
        return output

    def postprocess(self, accumulator):
        return accumulator
