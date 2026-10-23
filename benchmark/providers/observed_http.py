"""Opt-in, one-attempt transport diagnostics for future experiment versions.

Do not retrofit this into frozen runners. Records contain only an allowlisted
category, numeric HTTP status and elapsed time, never keys/URLs/body/error text.
"""

import json
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .http_json import ProviderRequestError, post_json


class DiagnosticRequestError(ProviderRequestError):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__('Provider request failed: '+diagnostic['category'])


def classify(error):
    if isinstance(error, HTTPError):
        code=error.code if type(error.code) is int and 100<=error.code<=599 else None
        return 'http_error',code,'error_response_received_execution_unknown'
    if isinstance(error, URLError):
        if isinstance(error.reason, BaseException): return classify(error.reason)
        return 'network_error',None,'unknown'
    if isinstance(error, TimeoutError): return 'timeout',None,'unknown'
    if isinstance(error, ssl.SSLError): return 'tls_error',None,'unknown'
    if isinstance(error, socket.gaierror): return 'dns_error',None,'unknown'
    if isinstance(error, (ConnectionError,OSError)): return 'network_error',None,'unknown'
    if isinstance(error, (json.JSONDecodeError,UnicodeError)):
        return 'unreadable_json',None,'response_received'
    if isinstance(error, ProviderRequestError) and error.__context__ is not None:
        return classify(error.__context__)
    return 'unclassified_error',None,'unknown'


def post_json_observed(endpoint,payload,*,auth_header,auth_value,timeout=120,
                       retries=0,opener=urlopen,clock=time.monotonic):
    if timeout<=0 or retries!=0:
        raise ValueError('Observed transport requires positive timeout and zero retries')
    started=clock()
    try:
        return post_json(endpoint,payload,auth_header=auth_header,auth_value=auth_value,
                         timeout=timeout,retries=0,opener=opener)
    except ProviderRequestError as exc:
        category,status,delivery=classify(exc)
        diagnostic={'version':'transport-diagnostic-v1','category':category,'http_status':status,
                    'elapsed_ms':max(0,round((clock()-started)*1000)),
                    'delivery':delivery,'attempts':1,'automatic_retries':0}
        raise DiagnosticRequestError(diagnostic) from None
