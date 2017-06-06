import time
import logging
import numpy as np
import scipy.sparse as spp
from ctypes import cdll, c_int

log = logging.getLogger(__name__)

def rand64c(*shape, order='F'):
    """
    Constructs a `np.ndarray` of the requested shape and
    populates it with random np.complex64 values.
    """
    r = np.random.rand(*shape).astype(np.float32)
    i = np.random.rand(*shape).astype(np.float32)
    arr = (r + 1j*i).astype(np.complex64)
    if order == 'F':
        arr = np.asfortranarray(arr)
    return arr


def randM(M, N, density):
    """
    Constructs a `scipy.sparse.spmatrix'  of the requested shape and
    density and populates it with random np.complex64 values.
    """
    A_r = spp.random(M, N, density=density, format='csr', dtype=np.float32).astype(np.complex64)
    A_i = spp.random(M, N, density=density, format='csr', dtype=np.float32)
    A = A_r + 1j * A_i
    return A


class profile(object):
    extra = dict()

    def __init__(self, event, **kwargs):
        self._event = event
        self._kwargs = kwargs

    def __enter__(self):
        self._start = time.time()

    def __exit__(self, exc_type, exc_value, traceback):
        data = dict(
            duration = time.time() - self._start,
            event    = self._event,
        )
        data.update(self.extra)
        data.update(self._kwargs)

        if 'nflops' in self._kwargs:
            data['gflop_rate'] = data['nflops'] / data['duration'] * 1e-9

        if 'nbytes' in self._kwargs:
            data['membw_rate'] = data['nbytes'] / data['duration'] * 1e-9

        kvs = sorted(data.items(), key=lambda kv: kv[0])
        msg = "PROFILE(%s)" % ", ".join("%s=%s" % (k,repr(v)) for k,v in kvs)
        log.debug(msg)


class Timer(object):
    def __init__(self):
        self._times = []

    def __enter__(self):
        self._start = time.time()

    def __exit__(self, exc_type, exc_value, traceback):
        self._times.append( time.time() - self._start )

    @property
    def median(self):
        return np.median( self._times )

    @property
    def mean(self):
        return np.mean( self._times )

    @property
    def max(self):
        return np.amax( self._times )

    @property
    def min(self):
        return np.amin( self._times )

