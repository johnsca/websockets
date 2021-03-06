import asyncio
import unittest

from websockets.http import *
from websockets.http import read_headers


class HTTPAsyncTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.stream = asyncio.StreamReader(loop=self.loop)

    def tearDown(self):
        self.loop.close()
        super().tearDown()

    def test_read_request(self):
        # Example from the protocol overview in RFC 6455
        self.stream.feed_data(
            b'GET /chat HTTP/1.1\r\n'
            b'Host: server.example.com\r\n'
            b'Upgrade: websocket\r\n'
            b'Connection: Upgrade\r\n'
            b'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
            b'Origin: http://example.com\r\n'
            b'Sec-WebSocket-Protocol: chat, superchat\r\n'
            b'Sec-WebSocket-Version: 13\r\n'
            b'\r\n'
        )
        path, headers = self.loop.run_until_complete(read_request(self.stream))
        self.assertEqual(path, '/chat')
        self.assertEqual(headers['Upgrade'], 'websocket')

    def test_read_response(self):
        # Example from the protocol overview in RFC 6455
        self.stream.feed_data(
            b'HTTP/1.1 101 Switching Protocols\r\n'
            b'Upgrade: websocket\r\n'
            b'Connection: Upgrade\r\n'
            b'Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n'
            b'Sec-WebSocket-Protocol: chat\r\n'
            b'\r\n'
        )
        status_code, reason, headers = self.loop.run_until_complete(
            read_response(self.stream)
        )
        self.assertEqual(status_code, 101)
        self.assertEqual(reason, 'Switching Protocols')
        self.assertEqual(headers['Upgrade'], 'websocket')

    def test_request_method(self):
        self.stream.feed_data(b'OPTIONS * HTTP/1.1\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_request(self.stream))

    def test_request_version(self):
        self.stream.feed_data(b'GET /chat HTTP/1.0\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_request(self.stream))

    def test_response_version(self):
        self.stream.feed_data(b'HTTP/1.0 400 Bad Request\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_response(self.stream))

    def test_response_status(self):
        self.stream.feed_data(b'HTTP/1.1 007 My name is Bond\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_response(self.stream))

    def test_response_reason(self):
        self.stream.feed_data(b'HTTP/1.1 200 \x7f\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_response(self.stream))

    def test_header_name(self):
        self.stream.feed_data(b'foo bar: baz qux\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_headers(self.stream))

    def test_header_value(self):
        self.stream.feed_data(b'foo: \x00\x00\x0f\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_headers(self.stream))

    def test_headers_limit(self):
        self.stream.feed_data(b'foo: bar\r\n' * 257 + b'\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_headers(self.stream))

    def test_line_limit(self):
        # Header line contains 5 + 4090 + 2 = 4097 bytes.
        self.stream.feed_data(b'foo: ' + b'a' * 4090 + b'\r\n\r\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_headers(self.stream))

    def test_line_ending(self):
        self.stream.feed_data(b'foo: bar\n\n')
        with self.assertRaises(ValueError):
            self.loop.run_until_complete(read_headers(self.stream))


class HeadersTests(unittest.TestCase):
    def setUp(self):
        self.headers = Headers([('Connection', 'Upgrade'), ('Server', USER_AGENT)])

    def test_str(self):
        self.assertEqual(
            str(self.headers),
            "Connection: Upgrade\r\nServer: {}\r\n\r\n".format(USER_AGENT),
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.headers),
            "Headers([('Connection', 'Upgrade'), "
            "('Server', '{}')])".format(USER_AGENT),
        )

    def test_multiple_values_error_str(self):
        self.assertEqual(str(MultipleValuesError('Connection')), "'Connection'")
        self.assertEqual(str(MultipleValuesError()), "")

    def test_contains(self):
        self.assertIn('Server', self.headers)

    def test_contains_case_insensitive(self):
        self.assertIn('server', self.headers)

    def test_contains_not_found(self):
        self.assertNotIn('Date', self.headers)

    def test_iter(self):
        self.assertEqual(set(iter(self.headers)), {'connection', 'server'})

    def test_len(self):
        self.assertEqual(len(self.headers), 2)

    def test_getitem(self):
        self.assertEqual(self.headers['Server'], USER_AGENT)

    def test_getitem_case_insensitive(self):
        self.assertEqual(self.headers['server'], USER_AGENT)

    def test_getitem_key_error(self):
        with self.assertRaises(KeyError):
            self.headers['Upgrade']

    def test_getitem_multiple_values_error(self):
        self.headers['Server'] = '2'
        with self.assertRaises(MultipleValuesError):
            self.headers['Server']

    def test_setitem(self):
        self.headers['Upgrade'] = 'websocket'
        self.assertEqual(self.headers['Upgrade'], 'websocket')

    def test_setitem_case_insensitive(self):
        self.headers['upgrade'] = 'websocket'
        self.assertEqual(self.headers['Upgrade'], 'websocket')

    def test_setitem_multiple_values(self):
        self.headers['Connection'] = 'close'
        with self.assertRaises(MultipleValuesError):
            self.headers['Connection']

    def test_delitem(self):
        del self.headers['Connection']
        with self.assertRaises(KeyError):
            self.headers['Connection']

    def test_delitem_case_insensitive(self):
        del self.headers['connection']
        with self.assertRaises(KeyError):
            self.headers['Connection']

    def test_delitem_multiple_values(self):
        self.headers['Connection'] = 'close'
        del self.headers['Connection']
        with self.assertRaises(KeyError):
            self.headers['Connection']

    def test_eq(self):
        other_headers = self.headers.copy()
        self.assertEqual(self.headers, other_headers)

    def test_eq_not_equal(self):
        self.assertNotEqual(self.headers, [])

    def test_clear(self):
        self.headers.clear()
        self.assertFalse(self.headers)
        self.assertEqual(self.headers, Headers())

    def test_get_all(self):
        self.assertEqual(self.headers.get_all('Connection'), ['Upgrade'])

    def test_get_all_case_insensitive(self):
        self.assertEqual(self.headers.get_all('connection'), ['Upgrade'])

    def test_get_all_no_values(self):
        self.assertEqual(self.headers.get_all('Upgrade'), [])

    def test_get_all_multiple_values(self):
        self.headers['Connection'] = 'close'
        self.assertEqual(self.headers.get_all('Connection'), ['Upgrade', 'close'])

    def test_raw_items(self):
        self.assertEqual(
            list(self.headers.raw_items()),
            [('Connection', 'Upgrade'), ('Server', USER_AGENT)],
        )
