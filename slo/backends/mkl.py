import logging
import os, sys, time
from ctypes import *

import numpy as np
from numpy.ctypeslib import ndpointer

from .backend import Backend

log = logging.getLogger(__name__)

# Find MKL library
MKLROOT = os.environ.get("MKLROOT", '/opt/intel/mkl')
for libpath in [
    'lib/intel64/libmkl_rt.so', # linux
    'lib/libmkl_rt.dylib',      # macos
    'lib/libmkl_rt.so',         # anaconda
]:
    libmkl_rt_path = os.path.join(MKLROOT, libpath)
    if os.path.exists( libmkl_rt_path ):
        log.debug("using MKL library at path <%s>." % libmkl_rt_path)
        libmkl_rt = cdll.LoadLibrary( libmkl_rt_path )
        break
else:
    log.critical("Could not locate MKL at path <%s>.", MKLROOT)
    log.critical("Try setting MKLROOT environment variable.")
    sys.exit(1)


class MklBackend(Backend):

    def __init__(self, device_id=0):
        self._fft_descs = dict()

    def wrap(fn):
        libfn = getattr(libmkl_rt, fn.__name__)
        libfn.argtypes = [fn.__annotations__[arg] for arg in fn.__code__.co_varnames]
        libfn.restype  =  fn.__annotations__['return']
        def wrapped(self, *args, **kwargs):
            res = libfn(*args, **kwargs)
            if isinstance(res, c_long) and res.value != 0:
                s = self.DftiErrorMessage( res )
                raise RuntimeError( s.decode('ascii') )
            return res
        return wrapped

    # -----------------------------------------------------------------------
    # Arrays
    # -----------------------------------------------------------------------
    class dndarray(Backend.dndarray):
        def _copy_from(self, arr, stream=0):
            self._arr.flat[:] = arr.flat

        def _copy_to(self, arr, stream=0):
            arr.flat[:] = self._arr.flat

        def _copy(self, d_arr, stream=0):
            dst = self._arr.reshape(-1, order='F')
            src = d_arr._arr.reshape(-1, order='F')
            dst.flat[:] = src.flat

        def _malloc(self, shape, dtype):
            return np.ndarray(shape, dtype, order='F')

        def _free(self):
            del self._arr

        def _zero(self):
            self._arr[:] = 0

        def __getitem__(self, slc):
            ld = self._leading_dims
            d = self._arr.reshape(self.shape, order='F')[slc]
            return self._backend.dndarray( self._backend, d.shape, d.dtype,
                ld=ld, own=False, data=d )

        def to_host(self):
            return self._arr

        @staticmethod
        def from_param(obj):
            if not isinstance(obj, MklBackend.dndarray):
                raise ArgumentError('{} is not a dndarray'.format( type(obj) ))
            return obj._arr.ctypes.get_as_parameter()

        def as_nparray(self):
            return self._arr
    
    @wrap
    def mkl_get_max_threads() -> c_int:
        pass

    def get_max_threads(self):
        return self.mkl_get_max_threads()

    # -----------------------------------------------------------------------
    # BLAS Routines
    # -----------------------------------------------------------------------
    def axpy(self, y, alpha, x):
        """ y += alpha * x """
        assert isinstance(x, self.dndarray)
        assert isinstance(y, self.dndarray)
        alpha = np.array(alpha, dtype=np.complex64)
        self.cblas_caxpy( y.size, alpha, x._arr, 1, y._arr, 1 )

    def dot(self, x, y):
        """ returns x^T * y """
        assert isinstance(x, self.dndarray)
        assert isinstance(y, self.dndarray)
        dotc = np.array(0, dtype=np.complex64)
        self.cblas_cdotc_sub( x.size, x._arr, 1, y._arr, 1, dotc )
        return dotc.real

    def norm2(self, x):
        """ returns ||x||_2"""
        assert isinstance(x, self.dndarray)
        res = self.cblas_scnrm2( x.size, x._arr, 1 )
        return res**2

    def scale(self, x, alpha):
        """ x *= alpha """
        assert isinstance(x, self.dndarray)
        a = np.array(alpha, dtype=np.complex64)
        self.cblas_cscal( x.size, a, x._arr, 1 )

    def cgemm(self, y, M, x, alpha, beta, forward):
        layout = MklBackend.CBlasLayout.ColMajor
        if forward:
            transa = MklBackend.CBlasTranspose.NoTrans
        else:
            transa = MklBackend.CBlasTranspose.ConjTrans
        transb = MklBackend.CBlasTranspose.NoTrans
        (m, n), k = y.shape, x.shape[0]
        alpha = np.array(alpha, dtype=np.complex64)
        beta  = np.array( beta, dtype=np.complex64)
        lda = M.shape[0]
        ldb = x.shape[0]
        ldc = y.shape[0]
        self.cblas_cgemm(
            layout, transa, transb, m, n, k,
            alpha, M, lda, x, ldb, beta, y, ldc
        )

    class CBlasLayout(c_uint):
        RowMajor = 101
        ColMajor = 102

    class CBlasTranspose(c_uint):
        NoTrans   = 111
        Trans     = 112
        ConjTrans = 113

    @wrap
    def cblas_cgemm(
        layout : CBlasLayout,
        transa : CBlasTranspose,
        transb : CBlasTranspose,
        m     : c_int,
        n     : c_int,
        k     : c_int,
        alpha : ndpointer(dtype=np.complex64, ndim=0),
        a     : dndarray,
        lda   : c_int,
        b     : dndarray,
        ldb   : c_int,
        beta  : ndpointer(dtype=np.complex64, ndim=0),
        c     : dndarray,
        ldc   : c_int,
    ) -> c_void_p:
        pass

    @wrap
    def cblas_caxpy(
        n : c_int,
        a : ndpointer(dtype=np.complex64, ndim=0),
        x : ndpointer(dtype=np.complex64),
        incx : c_int,
        y : ndpointer(dtype=np.complex64),
        incy : c_int,
    ) -> c_void_p:
        pass

    @wrap
    def cblas_cdotc_sub(
        n    : c_int,
        x    : ndpointer(dtype=np.complex64),
        incx : c_int,
        y    : ndpointer(dtype=np.complex64),
        incy : c_int,
        dotc : ndpointer(dtype=np.complex64, ndim=0),
    ) -> c_void_p:
        pass

    @wrap
    def cblas_scnrm2(
        n : c_int,
        x    : ndpointer(dtype=np.complex64),
        incx : c_int,
    ) -> c_float:
        pass

    @wrap
    def cblas_cscal(
        n    : c_int,
        a    : ndpointer(dtype=np.complex64, ndim=0),
        x    : ndpointer(dtype=np.complex64),
        incx : c_int,
    ) -> c_void_p:
        pass



    # -----------------------------------------------------------------------
    # FFT Routines
    # -----------------------------------------------------------------------
    class DFTI_DESCRIPTOR_HANDLE(c_void_p):
        pass

    class status_t(c_long):
        pass

    # read these values out of `gcc -E mkl.h | grep DFTI_WHATEVER`
    # they could change so we're living on the edge here
    DFTI_SINGLE = 35
    DFTI_COMPLEX = 32
    DFTI_INPUT_DISTANCE = 14
    DFTI_OUTPUT_DISTANCE = 15
    DFTI_NUMBER_OF_TRANSFORMS = 7
    DFTI_PLACEMENT = 11
    DFTI_INPLACE = 43
    DFTI_NOT_INPLACE = 44

    def _get_or_create_fft_desc(self, x, axes):
        assert axes == (0,1,2)
        key = (x.shape, x.dtype, axes)
        if key not in self._fft_descs:
            N = x.shape[:3][::-1]
            batch = int(x.size / np.prod(N))
            desc = self.DFTI_DESCRIPTOR_HANDLE()
            lengths = (c_long*3)(*N)
            self.DftiCreateDescriptor( byref(desc),
                self.DFTI_SINGLE, self.DFTI_COMPLEX, 3, lengths)
            self.DftiSetValue( desc, self.DFTI_NUMBER_OF_TRANSFORMS, batch )
            self.DftiSetValue( desc, self.DFTI_PLACEMENT, self.DFTI_NOT_INPLACE )
            self.DftiSetValue( desc, self.DFTI_INPUT_DISTANCE, np.prod(N) )
            self.DftiSetValue( desc, self.DFTI_OUTPUT_DISTANCE, np.prod(N) )
            self.DftiCommitDescriptor( desc )
            self._fft_descs[key] = desc
        return self._fft_descs[key]

    def fftn(self, y, x, stream=None):
        desc = self._get_or_create_fft_desc( x, axes=(0,1,2) )
        self.DftiComputeForward( desc, x, y )

    def ifftn(self, y, x, stream=None):
        desc = self._get_or_create_fft_desc( x, axes=(0,1,2) )
        self.DftiComputeBackward( desc, x, y )

    def __del__(self):
        for desc in self._fft_descs.values():
            self.DftiFreeDescriptor( byref(desc) )

    @wrap
    def DftiErrorMessage(
        status : status_t,
    ) -> c_char_p:
        pass

    @wrap
    def DftiComputeForward(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
        x_in        : dndarray,
        y_out       : dndarray,
    ) -> status_t:
        pass

    @wrap
    def DftiComputeBackward(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
        x_in        : dndarray,
        y_out       : dndarray,
    ) -> status_t:
        pass

    @wrap
    def DftiCommitDescriptor(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
    ) -> status_t:
        pass

    @wrap
    def DftiSetValue(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
        param       : c_uint,
        value       : c_uint,
    ) -> status_t:
        pass

    @wrap
    def DftiCreateDescriptor(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
        precision   : c_uint,
        domain      : c_uint,
        dimension   : c_long,
        length      : c_long*3,
    ) -> status_t:
        pass

    @wrap
    def DftiFreeDescriptor(
        desc_handle : DFTI_DESCRIPTOR_HANDLE,
    ) -> status_t:
        pass

    # -----------------------------------------------------------------------
    # CSRMM Routines
    # -----------------------------------------------------------------------
    class csr_matrix(Backend.csr_matrix):
        _index_base = 1

    @wrap
    def mkl_ccsrmm(
        transA   : c_char*1,
        m        : ndpointer(dtype=np.int32,     ndim=0),
        n        : ndpointer(dtype=np.int32,     ndim=0),
        k        : ndpointer(dtype=np.int32,     ndim=0),
        alpha    : ndpointer(dtype=np.dtype('complex64'), ndim=1),
        matdescA : c_char * 6,
        val      : dndarray,
        indx     : dndarray,
        pntrb    : dndarray,
        pntre    : dndarray,
        b        : dndarray,
        ldb      : ndpointer(dtype=np.int32,     ndim=0),
        beta     : ndpointer(dtype=np.dtype('complex64'), ndim=1),
        c        : dndarray,
        ldc      : ndpointer(dtype=np.int32,     ndim=0),
    ) -> c_void_p :
        pass

    def ccsrmm(self, y, A_shape, A_indx, A_ptr, A_vals, x, alpha, beta, adjoint=False, stream=None):
        transA = create_string_buffer(1)
        if adjoint:
            transA[0] = b'C'
        else:
            transA[0] = b'N' 
        ldx = np.array(x._leading_dims[0], dtype=np.int32)
        ldy = np.array(y._leading_dims[0], dtype=np.int32)

        A_ptrb = A_ptr[:-1]
        A_ptre = A_ptr[1:]

        m     = np.array(A_shape[0], dtype=np.int32)
        n     = np.array(x.shape[1], dtype=np.int32)
        k     = np.array(A_shape[1], dtype=np.int32)
        alpha = np.array([alpha],    dtype=np.dtype('complex64'))
        beta  = np.array([beta],     dtype=np.dtype('complex64'))

        descrA = create_string_buffer(6)
        descrA[0] = b'G'
        descrA[2] = b'N'
        descrA[3] = b'F'

        self.mkl_ccsrmm(transA, m, n, k, alpha,
            descrA, A_vals, A_indx, A_ptrb, A_ptre,
            x, ldx, beta, y, ldy)