#-----------------
# Florian Mueller
# December 2014
#-----------------

# see report.pdf, section 3.1



import Data
import numpy



class LayoutData(Data.Data):



    scalarFields = ['zeroBasedIndexing','N','E','nPl']
    indexFields  = ['sSpp_e','sRtn_e','nPl']



    def setNewYork(self):

        self.c['N'] = 20
        self.c['E'] = 21
        self.c['sSpp_e'] = numpy.array(   [[ 0, 1],
                                           [ 1, 2],
                                           [ 2, 3],
                                           [ 3, 4],
                                           [ 4, 5],
                                           [ 5, 6],
                                           [ 6, 7],
                                           [ 7, 8],
                                           [ 8, 9],
                                           [10, 8],
                                           [11,10],
                                           [12,11],
                                           [13,12],
                                           [14,13],
                                           [ 0,14],
                                           [ 9,16],
                                           [11,17],
                                           [17,18],
                                           [10,19],
                                           [19,15],
                                           [ 8,15]])
        self.c['sRtn_e'] = numpy.fliplr(self.c['sSpp_e'])
        self.c['nPl']    = 0

