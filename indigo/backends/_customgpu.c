#include <complex.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include "Python.h"
#include <numpy/arrayobject.h>

#include "_customgpu.h"

static PyObject*
py_exw_csrmm_H(PyObject *self, PyObject *args)
{
    void *cublasHandle;
    PyObject *py_alpha, *py_beta;
    unsigned int ldx, ldy, M, N, K;
    unsigned long rowPtrs, colInds, values, X, Y;
    if (!PyArg_ParseTuple(args, "kiiiOkkkkiOki",
        &cublasHandle, &M, &N, &K, &py_alpha,
        &values, &colInds, &rowPtrs,
        &X, &ldx, &py_beta, &Y, &ldy))
        return NULL;

    float alpha_r = (float) PyComplex_RealAsDouble( py_alpha ),
          alpha_i = (float) PyComplex_ImagAsDouble( py_alpha ),
           beta_r = (float) PyComplex_RealAsDouble( py_beta  ),
           beta_i = (float) PyComplex_ImagAsDouble( py_beta  );
    complex float alpha = alpha_r + I * alpha_i,
                   beta =  beta_r + I *  beta_i;

    c_exw_csrmm_H(cublasHandle, M, N, K, alpha, (complex float*) values, (unsigned int *) colInds, (unsigned int *) rowPtrs, (complex float *) X, ldx, beta, (complex float *) Y, ldy);

    Py_RETURN_NONE;
}

static PyObject*
py_onemm(PyObject *self, PyObject *args)
{
    PyObject *py_alpha, *py_beta;
    unsigned int ldx, ldy, M, N, K;
    unsigned long Y, X;
    if (!PyArg_ParseTuple(args, "iiiOkiOki",
        &M, &N, &K, &py_alpha, &X, &ldx, &py_beta, &Y, &ldy))
        return NULL;

    float alpha_r = (float) PyComplex_RealAsDouble( py_alpha ),
          alpha_i = (float) PyComplex_ImagAsDouble( py_alpha ),
           beta_r = (float) PyComplex_RealAsDouble( py_beta  ),
           beta_i = (float) PyComplex_ImagAsDouble( py_beta  );
    complex float alpha = alpha_r + I * alpha_i,
                   beta =  beta_r + I *  beta_i;

    c_onemm(M, N, K, alpha, (complex float *) X, ldx,
                     beta,  (complex float *) Y, ldy);

    Py_RETURN_NONE;
}

static PyObject*
py_diamm(PyObject *self, PyObject *args)
{
    PyObject *py_alpha, *py_beta;
    unsigned int ldx, ldy, M, N, K, nOffsets, adjoint;
    unsigned long Y, X, offsets, data;
    if (!PyArg_ParseTuple(args, "iiiikkOkiOkip",
        &M, &N, &K, &nOffsets, &offsets, &data,
        &py_alpha, &X, &ldx, &py_beta, &Y, &ldy, &adjoint))
        return NULL;

    float alpha_r = (float) PyComplex_RealAsDouble( py_alpha ),
          alpha_i = (float) PyComplex_ImagAsDouble( py_alpha ),
           beta_r = (float) PyComplex_RealAsDouble( py_beta  ),
           beta_i = (float) PyComplex_ImagAsDouble( py_beta  );
    complex float alpha = alpha_r + I * alpha_i,
                   beta =  beta_r + I *  beta_i;

    c_diamm(M, N, K, nOffsets, (int*) offsets, (complex float *) data,
        alpha, (complex float *) X, ldx,
        beta,  (complex float *) Y, ldy, adjoint);

    Py_RETURN_NONE;
}

static PyObject*
py_max(PyObject *self, PyObject *args)
{
    float val;
    unsigned int N;
    unsigned long arr;
    if (!PyArg_ParseTuple(args, "Ifk", &N, &val, &arr))
        return NULL;
    // promote complex float array to float array
    c_max(N, val, (float*) arr);
    Py_RETURN_NONE;
}


static PyMethodDef _customgpuMethods[] = {
    { "exw_csrmm", py_exw_csrmm_H, METH_VARARGS, NULL },
    { "onemm", py_onemm, METH_VARARGS, NULL },
    { "diamm", py_diamm, METH_VARARGS, NULL },
    { "max", py_max, METH_VARARGS, NULL },
    {NULL, NULL, 0, NULL} /* Sentinel */
};

static struct PyModuleDef _customgpu = {
    PyModuleDef_HEAD_INIT, "_customgpu", NULL, -1, _customgpuMethods,
};

PyMODINIT_FUNC
PyInit__customgpu(void)
{
    import_array();
    return PyModule_Create(&_customgpu);
}
