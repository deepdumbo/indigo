import time
import logging
import numpy as np
import scipy.sparse as spp

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
    A_r = spp.random(M, N, density=density, format='csr', dtype=np.float32)
    A_i = spp.random(M, N, density=density, format='csr', dtype=np.float32)
    A = (A_r + 1j * A_i).astype(np.dtype('complex64'))
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
        msg = "PROFILE(%s)" % ", ".join("%s=%s" % (k,repr(v)) for k,v in data.items())
        log.critical(msg)

