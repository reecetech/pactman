from datetime import datetime
from unittest import TestCase

from pactman import Format


class FormatTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formatter = Format()

    def test_identifier(self):
        identifier = self.formatter.identifier.ruby_protocol()
        self.assertEqual(identifier, {"json_class": "Pact::SomethingLike", "contents": 1})

    def test_integer(self):
        integer = self.formatter.integer.ruby_protocol()
        self.assertEqual(integer, {"json_class": "Pact::SomethingLike", "contents": 1})

    def test_decimal(self):
        decimal = self.formatter.integer.ruby_protocol()
        self.assertEqual(decimal, {"json_class": "Pact::SomethingLike", "contents": 1.0})

    def test_ip_address(self):
        ip_address = self.formatter.ip_address.ruby_protocol()
        self.assertEqual(
            ip_address,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.ip_address.value,
                        "o": 0,
                    },
                    "generate": "127.0.0.1",
                },
            },
        )

    def test_hexadecimal(self):
        hexadecimal = self.formatter.hexadecimal.ruby_protocol()
        self.assertEqual(
            hexadecimal,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.hexadecimal.value,
                        "o": 0,
                    },
                    "generate": "3F",
                },
            },
        )

    def test_ipv6_address(self):
        ipv6_address = self.formatter.ipv6_address.ruby_protocol()
        self.assertEqual(
            ipv6_address,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.ipv6_address.value,
                        "o": 0,
                    },
                    "generate": "::ffff:192.0.2.128",
                },
            },
        )

    def test_uuid(self):
        uuid = self.formatter.uuid.ruby_protocol()
        self.assertEqual(
            uuid,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.uuid.value,
                        "o": 0,
                    },
                    "generate": "fc763eba-0905-41c5-a27f-3934ab26786c",
                },
            },
        )

    def test_timestamp(self):
        timestamp = self.formatter.timestamp.ruby_protocol()
        self.assertEqual(
            timestamp,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.timestamp.value,
                        "o": 0,
                    },
                    "generate": datetime(2000, 2, 1, 12, 30, 0, 0).isoformat(),
                },
            },
        )

    def test_date(self):
        date = self.formatter.date.ruby_protocol()
        self.assertEqual(
            date,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.date.value,
                        "o": 0,
                    },
                    "generate": datetime(2000, 2, 1, 12, 30, 0, 0).date().isoformat(),
                },
            },
        )

    def test_time(self):
        time = self.formatter.time.ruby_protocol()
        self.assertEqual(
            time,
            {
                "json_class": "Pact::Term",
                "data": {
                    "matcher": {
                        "json_class": "Regexp",
                        "s": self.formatter.Regexes.time_regex.value,
                        "o": 0,
                    },
                    "generate": datetime(2000, 2, 1, 12, 30, 0, 0).time().isoformat(),
                },
            },
        )
