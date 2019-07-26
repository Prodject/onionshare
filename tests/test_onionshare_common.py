"""
OnionShare | https://onionshare.org/

Copyright (C) 2014-2018 Micah Lee <micah@micahflee.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import contextlib
import inspect
import io
import os
import random
import re
import socket
import sys
import zipfile

import pytest

LOG_MSG_REGEX = re.compile(r"""
    ^\[Jun\ 06\ 2013\ 11:05:00\]
    \ TestModule\.<function\ TestLog\.test_output\.<locals>\.dummy_func
    \ at\ 0x[a-f0-9]+>(:\ TEST_MSG)?$""", re.VERBOSE)
PASSWORD_REGEX = re.compile(r'^([a-z]+)(-[a-z]+)?-([a-z]+)(-[a-z]+)?$')


# TODO: Improve the Common tests to test it all as a single class


class TestBuildPassword:
    @pytest.mark.parametrize('test_input,expected', (
        # VALID, two lowercase words, separated by a hyphen
        ('syrup-enzyme', True),
        ('caution-friday', True),

        # VALID, two lowercase words, with one hyphenated compound word
        ('drop-down-thimble', True),
        ('unmixed-yo-yo', True),

        # VALID, two lowercase hyphenated compound words, separated by hyphen
        ('yo-yo-drop-down', True),
        ('felt-tip-t-shirt', True),
        ('hello-world', True),

        # INVALID
        ('Upper-Case', False),
        ('digits-123', False),
        ('too-many-hyphens-', False),
        ('symbols-!@#$%', False)
    ))
    def test_build_password_regex(self, test_input, expected):
        """ Test that `PASSWORD_REGEX` accounts for the following patterns

        There are a few hyphenated words in `wordlist.txt`:
            * drop-down
            * felt-tip
            * t-shirt
            * yo-yo

        These words cause a few extra potential password patterns:
            * word-word
            * hyphenated-word-word
            * word-hyphenated-word
            * hyphenated-word-hyphenated-word
        """

        assert bool(PASSWORD_REGEX.match(test_input)) == expected

    def test_build_password_unique(self, common_obj, sys_onionshare_dev_mode):
        assert common_obj.build_password() != common_obj.build_password()


class TestDirSize:
    def test_temp_dir_size(self, common_obj, temp_dir_1024_delete):
        """ dir_size() should return the total size (in bytes) of all files
        in a particular directory.
        """

        assert common_obj.dir_size(temp_dir_1024_delete) == 1024


class TestEstimatedTimeRemaining:
    @pytest.mark.parametrize('test_input,expected', (
        ((2, 676, 12), '8h14m16s'),
        ((14, 1049, 30), '1h26m15s'),
        ((21, 450, 1), '33m42s'),
        ((31, 1115, 80), '11m39s'),
        ((336, 989, 32), '2m12s'),
        ((603, 949, 38), '36s'),
        ((971, 1009, 83), '1s')
    ))
    def test_estimated_time_remaining(
            self, common_obj, test_input, expected, time_time_100):
        assert common_obj.estimated_time_remaining(*test_input) == expected

    @pytest.mark.parametrize('test_input', (
        (10, 20, 100),  # if `time_elapsed == 0`
        (0, 37, 99)     # if `download_rate == 0`
    ))
    def test_raises_zero_division_error(self, common_obj, test_input, time_time_100):
        with pytest.raises(ZeroDivisionError):
            common_obj.estimated_time_remaining(*test_input)


class TestFormatSeconds:
    @pytest.mark.parametrize('test_input,expected', (
        (0, '0s'),
        (26, '26s'),
        (60, '1m'),
        (947.35, '15m47s'),
        (1847, '30m47s'),
        (2193.94, '36m34s'),
        (3600, '1h'),
        (13426.83, '3h43m47s'),
        (16293, '4h31m33s'),
        (18392.14, '5h6m32s'),
        (86400, '1d'),
        (129674, '1d12h1m14s'),
        (56404.12, '15h40m4s')
    ))
    def test_format_seconds(self, common_obj, test_input, expected):
        assert common_obj.format_seconds(test_input) == expected

    # TODO: test negative numbers?
    @pytest.mark.parametrize('test_input', (
        'string', lambda: None, [], {}, set()
    ))
    def test_invalid_input_types(self, common_obj, test_input):
        with pytest.raises(TypeError):
            common_obj.format_seconds(test_input)


class TestGetAvailablePort:
    @pytest.mark.parametrize('port_min,port_max', (
        (random.randint(1024, 1500),
         random.randint(1800, 2048)) for _ in range(50)
    ))
    def test_returns_an_open_port(self, common_obj, port_min, port_max):
        """ get_available_port() should return an open port within the range """

        port = common_obj.get_available_port(port_min, port_max)
        assert port_min <= port <= port_max
        with socket.socket() as tmpsock:
            tmpsock.bind(('127.0.0.1', port))


class TestGetPlatform:
    def test_darwin(self, platform_darwin, common_obj):
        assert common_obj.platform == 'Darwin'

    def test_linux(self, platform_linux, common_obj):
        assert common_obj.platform == 'Linux'

    def test_windows(self, platform_windows, common_obj):
        assert common_obj.platform == 'Windows'


# TODO: double-check these tests
class TestGetResourcePath:
    def test_onionshare_dev_mode(self, common_obj, sys_onionshare_dev_mode):
        prefix = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(
                        inspect.getfile(
                            inspect.currentframe())))), 'share')
        assert (
            common_obj.get_resource_path(os.path.join(prefix, 'test_filename')) ==
            os.path.join(prefix, 'test_filename'))

    def test_linux(self, common_obj, platform_linux, sys_argv_sys_prefix):
        prefix = os.path.join(sys.prefix, 'share/onionshare')
        assert (
            common_obj.get_resource_path(os.path.join(prefix, 'test_filename')) ==
            os.path.join(prefix, 'test_filename'))

    def test_frozen_darwin(self, common_obj, platform_darwin, sys_frozen, sys_meipass):
        prefix = os.path.join(sys._MEIPASS, 'share')
        assert (
            common_obj.get_resource_path(os.path.join(prefix, 'test_filename')) ==
            os.path.join(prefix, 'test_filename'))


class TestGetTorPaths:
    # @pytest.mark.skipif(sys.platform != 'Darwin', reason='requires MacOS') ?
    def test_get_tor_paths_darwin(self, platform_darwin, common_obj, sys_frozen, sys_meipass):
        base_path = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    common_obj.get_resource_path(''))))
        tor_path = os.path.join(
            base_path, 'Resources', 'Tor', 'tor')
        tor_geo_ip_file_path = os.path.join(
            base_path, 'Resources', 'Tor', 'geoip')
        tor_geo_ipv6_file_path = os.path.join(
            base_path, 'Resources', 'Tor', 'geoip6')
        obfs4proxy_file_path = os.path.join(
            base_path, 'Resources', 'Tor', 'obfs4proxy')
        assert (common_obj.get_tor_paths() ==
                (tor_path, tor_geo_ip_file_path, tor_geo_ipv6_file_path, obfs4proxy_file_path))

    # @pytest.mark.skipif(sys.platform != 'Linux', reason='requires Linux') ?
    def test_get_tor_paths_linux(self, platform_linux, common_obj):
        assert (common_obj.get_tor_paths() ==
                ('/usr/bin/tor', '/usr/share/tor/geoip', '/usr/share/tor/geoip6', '/usr/bin/obfs4proxy'))

    # @pytest.mark.skipif(sys.platform != 'Windows', reason='requires Windows') ?
    def test_get_tor_paths_windows(self, platform_windows, common_obj, sys_frozen):
        base_path = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    common_obj.get_resource_path(''))), 'tor')
        tor_path = os.path.join(
            os.path.join(base_path, 'Tor'), 'tor.exe')
        obfs4proxy_file_path = os.path.join(
            os.path.join(base_path, 'Tor'), 'obfs4proxy.exe')
        tor_geo_ip_file_path = os.path.join(
            os.path.join(
                os.path.join(base_path, 'Data'), 'Tor'), 'geoip')
        tor_geo_ipv6_file_path = os.path.join(
            os.path.join(
                os.path.join(base_path, 'Data'), 'Tor'), 'geoip6')
        assert (common_obj.get_tor_paths() ==
                (tor_path, tor_geo_ip_file_path, tor_geo_ipv6_file_path, obfs4proxy_file_path))


class TestHumanReadableFilesize:
    @pytest.mark.parametrize('test_input,expected', (
        (1024 ** 0, '1.0 B'),
        (1024 ** 1, '1.0 KiB'),
        (1024 ** 2, '1.0 MiB'),
        (1024 ** 3, '1.0 GiB'),
        (1024 ** 4, '1.0 TiB'),
        (1024 ** 5, '1.0 PiB'),
        (1024 ** 6, '1.0 EiB'),
        (1024 ** 7, '1.0 ZiB'),
        (1024 ** 8, '1.0 YiB')
    ))
    def test_human_readable_filesize(self, common_obj, test_input, expected):
        assert common_obj.human_readable_filesize(test_input) == expected


class TestLog:
    @pytest.mark.parametrize('test_input', (
        ('[Jun 06 2013 11:05:00]'
         ' TestModule.<function TestLog.test_output.<locals>.dummy_func'
         ' at 0xdeadbeef>'),
        ('[Jun 06 2013 11:05:00]'
         ' TestModule.<function TestLog.test_output.<locals>.dummy_func'
         ' at 0xdeadbeef>: TEST_MSG')
    ))
    def test_log_msg_regex(self, test_input):
        assert bool(LOG_MSG_REGEX.match(test_input))

    def test_output(self, common_obj, time_strftime):
        def dummy_func():
            pass

        common_obj.verbose = True

        # From: https://stackoverflow.com/questions/1218933
        with io.StringIO() as buf, contextlib.redirect_stdout(buf):
            common_obj.log('TestModule', dummy_func)
            common_obj.log('TestModule', dummy_func, 'TEST_MSG')
            output = buf.getvalue()

        line_one, line_two, _ = output.split('\n')
        assert LOG_MSG_REGEX.match(line_one)
        assert LOG_MSG_REGEX.match(line_two)
