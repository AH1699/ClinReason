import io
import json
import socket
import ssl
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError,URLError

from benchmark.providers.observed_http import DiagnosticRequestError,post_json_observed


class ObservedTransportTests(unittest.TestCase):
    def invoke(self,error):
        opener=Mock(side_effect=error)
        with self.assertRaises(DiagnosticRequestError) as caught:
            post_json_observed('https://example.invalid/secret-in-url',{},auth_header='Authorization',
                               auth_value='secret-key',opener=opener,clock=Mock(side_effect=[5,125]))
        self.assertEqual(opener.call_count,1)
        text=json.dumps(caught.exception.diagnostic)+str(caught.exception)
        self.assertNotIn('secret',text)
        return caught.exception.diagnostic

    def test_timeout_is_distinct_and_never_retried(self):
        result=self.invoke(TimeoutError('secret response'))
        self.assertEqual(result['category'],'timeout')
        self.assertEqual(result['elapsed_ms'],120000)
        self.assertEqual(result['delivery'],'unknown')

    def test_http_status_without_body_headers_or_url(self):
        error=HTTPError('https://secret.invalid',429,'secret response',{'secret':'secret'},io.BytesIO(b'secret'))
        result=self.invoke(error)
        self.assertEqual((result['category'],result['http_status']),('http_error',429))
        self.assertEqual(result['automatic_retries'],0)

    def test_dns_tls_and_unspecified_network_failures(self):
        for error,category in [(URLError(socket.gaierror('secret')),'dns_error'),
                               (URLError(ssl.SSLError('secret')),'tls_error'),
                               (URLError('secret'),'network_error')]:
            with self.subTest(category=category): self.assertEqual(self.invoke(error)['category'],category)

    def test_success_and_unreadable_body(self):
        result=post_json_observed('https://example.invalid',{},auth_header='X-Key',auth_value='unused',
                                 opener=lambda *a,**k:io.BytesIO(b'{"ok":true}'))
        self.assertEqual(result[0],{'ok':True})
        with self.assertRaises(DiagnosticRequestError) as caught:
            post_json_observed('https://example.invalid',{},auth_header='X-Key',auth_value='unused',
                               opener=lambda *a,**k:io.BytesIO(b'secret invalid response'))
        self.assertEqual(caught.exception.diagnostic['category'],'unreadable_json')
        self.assertNotIn('secret',str(caught.exception))
        with self.assertRaises(ValueError):
            post_json_observed('https://example.invalid',{},auth_header='X-Key',auth_value='unused',retries=1)


if __name__=='__main__': unittest.main()
