import argparse
import types

from owmeta_core.command import OWM
from owmeta.data_trans.wormbase import (MuscleWormBaseCSVTranslator, WormBaseCSVDataSource,
                                        WormbaseIonChannelCSVDataSource, WormbaseIonChannelCSVTranslator,
                                        NeuronWormBaseCSVTranslator, WormbaseTextMatchCSVTranslator,
                                        WormbaseTextMatchCSVDataSource, WormbaseIDSetter)
from owmeta.data_trans.neuron_data import NeuronCSVDataSource, NeuronCSVDataTranslator
from owmeta.data_trans.connections import (NeuronConnectomeCSVTranslator,
                                           ConnectomeCSVDataSource,
                                           NeuronConnectomeSynapseClassTranslator)
from owmeta.data_trans.context_merge import ContextMergeDataTranslator
from owmeta.data_trans.data_with_evidence_ds import DataWithEvidenceDataSource as DWEDS


# metaclass stuff to keep track of the order of data sources in DSMethods.
# Copied from PEP 3115
class member_table(dict):
    def __init__(self):
        self.member_names = []

    def __setitem__(self, key, value):
        if key not in self:
            self.member_names.append(key)

        dict.__setitem__(self, key, value)


class OrderedClass(type):
    @classmethod
    def __prepare__(metacls, name, bases): # No keywords in this case
        return member_table()

    def __new__(cls, name, bases, classdict):
        result = type.__new__(cls, name, bases, dict(classdict))
        result.member_names = classdict.member_names
        return result


class DSMethods(metaclass=OrderedClass):
    # Note: Keep the ordering of
    def __init__(self):
        self.owm = OWM()
        self.ctx = self.owm.default_context.stored

    def muscles(self):
        muscles = self.owm.translate(MuscleWormBaseCSVTranslator(),
                data_sources=[WormBaseCSVDataSource(key='wormbase_celegans_cells')],
                output_key='muscles')
        self.ctx(muscles).description(
                "Contains descriptions of C. elegans muscles and is the"
                " principle such list for OpenWorm")

    def neurons(self):
        neurons = self.owm.translate(NeuronCSVDataTranslator(),
                data_sources=[NeuronCSVDataSource(key='neurons')],
                output_key='neurons')
        self.ctx(neurons).description(
                "Contains descriptions of C. elegans neurons and is the"
                " principle such list for OpenWorm")

    def ion_channels(self):
        ion_channels = self.owm.translate(
                WormbaseIonChannelCSVTranslator(),
                data_sources=[WormbaseIonChannelCSVDataSource(key='ion_channels')],
                output_key='ion_channels')
        self.ctx(ion_channels).description(
                "Contains Channels and ExpressionPatterns")

    def wormbase_neurons(self):
        wb_neurons = self.owm.translate(
                NeuronWormBaseCSVTranslator(),
                data_sources=[WormBaseCSVDataSource(key='wormbase_celegans_cells')],
                output_key='wormbase_neurons')
        self.ctx(wb_neurons).description(
                'Contains neurons and links to C. elegans. Partially redundant to the Worm Atlas'
                ' data source')

    def bently_expression(self):
        bently_expression = self.owm.translate(
                NeuronCSVDataTranslator(),
                data_sources=[NeuronCSVDataSource(key='bently_expression')],
                output_key='bently_expression')
        self.ctx(bently_expression).description(
                'Adds receptor, neurotransmitter, and neuropeptide relationships for Neurons')

    def muscle_ion_channels(self):
        muscle_ion_channels = self.owm.translate(
                WormbaseTextMatchCSVTranslator(),
                data_sources=[WormbaseTextMatchCSVDataSource(key='muscle_ion_channels')],
                output_key='muscle_ion_channels')
        self.ctx(muscle_ion_channels).description(
                'Adds relationships between muscles and ion channels')

    def neuron_ion_channels(self):
        neuron_ion_channels = self.owm.translate(
                WormbaseTextMatchCSVTranslator(),
                data_sources=[WormbaseTextMatchCSVDataSource(key='neuron_ion_channels')],
                output_key='neuron_ion_channels')
        self.ctx(neuron_ion_channels).description(
                'Adds relationships between neurons and ion channels')

    def connectome(self):
        emmons_connectome = self.owm.translate(
                NeuronConnectomeCSVTranslator(),
                data_sources=[ConnectomeCSVDataSource(key='emmons')],
                named_data_sources=dict(
                    muscles_source=DWEDS(key='muscles'),
                    neurons_source=DWEDS(key='neurons')),
                output_key='connectome')
        self.ctx(emmons_connectome).description(
                'C. elegans connectome')

    def synclass(self):
        connectome_synclass = self.owm.translate(
                NeuronConnectomeSynapseClassTranslator(),
                data_sources=[DWEDS(key='connectome')],
                named_data_sources=dict(
                    neurotransmitter_source=ConnectomeCSVDataSource(key='connectome')),
                output_key='synclass')
        self.ctx(connectome_synclass).description(
                'Adds inferred relationships between connections and neurotransmitters that'
                ' mediates communication')

    def cells_source(self):
        cells_source = self.owm.translate(
                ContextMergeDataTranslator(),
                data_sources=[
                    DWEDS(key='muscles'),
                    DWEDS(key='neurons')],
                output_key='cells_source')
        self.ctx(cells_source).description(
                'Combination of C. elegans muscles and neurons')

    def wormbase_ids(self):
        wormbase_ids = self.owm.translate(
                WormbaseIDSetter(),
                data_sources=[
                    WormBaseCSVDataSource(key='wormbase_celegans_cells'),
                    DWEDS(key='cells_source')],
                output_key='wormbase_ids')
        self.ctx(wormbase_ids).description(
                'Adds identifiers from Wormbase.org for cells')

    def openworm_data(self):
        combined_data_source = self.owm.translate(
                ContextMergeDataTranslator(),
                data_sources=[
                    DWEDS(key='cells_source'),
                    DWEDS(key='ion_channels'),
                    DWEDS(key='wormbase_neurons'),
                    DWEDS(key='bently_expression'),
                    DWEDS(key='muscle_ion_channels'),
                    DWEDS(key='neuron_ion_channels'),
                    DWEDS(key='connectome'),
                    DWEDS(key='synclass'),
                    DWEDS(key='wormbase_ids')],
                output_identifier='http://openworm.org/data')

    def methods(self):
        return list(x for x in self.member_names
                if x not in ('save', 'methods') and
                not x.startswith('_') and
                isinstance(getattr(self, x), types.MethodType))

    def save(self):
        self.ctx.save()


def main():
    parser = argparse.ArgumentParser()
    m = DSMethods()
    parser.add_argument('source', nargs='*', choices=m.methods() + ['all'])

    ns = parser.parse_args()
    for src in m.methods():
        if 'all' in ns.source or src in ns.source:
            print(f"Building {src}...")
            getattr(m, src)()


if __name__ == '__main__':
    main()
