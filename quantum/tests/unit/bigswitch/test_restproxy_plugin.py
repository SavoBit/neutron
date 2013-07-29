# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2012 Big Switch Networks, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from mock import patch
from oslo.config import cfg

import quantum.common.test_lib as test_lib
from quantum.extensions import portbindings
from quantum.manager import QuantumManager
from quantum.tests.unit import _test_extension_portbindings as test_bindings
import quantum.tests.unit.test_db_plugin as test_plugin

RESTPROXY_PKG_PATH = 'quantum.plugins.bigswitch.plugin'


class HTTPResponseMock():
    status = 200
    reason = 'OK'

    def __init__(self, sock, debuglevel=0, strict=0, method=None,
                 buffering=False):
        pass

    def read(self):
        return "{'status': '200 OK'}"


class HTTPResponseMock404():
    status = 404
    reason = 'Not Found'

    def __init__(self, sock, debuglevel=0, strict=0, method=None,
                 buffering=False):
        pass

    def read(self):
        return "{'status': '404 Not Found'}"


class HTTPResponseMock500():
    status = 500
    reason = 'Internal Server Error'

    def __init__(self, sock, debuglevel=0, strict=0, method=None,
                 buffering=False):
        pass

    def read(self):
        return "{'status': '500 Internal Server Error'}"


class HTTPConnectionMock():

    def __init__(self, server, port, timeout):
        if port == 9000:
            self.response = HTTPResponseMock500(None)
            self.broken = True
        else:
            self.response = HTTPResponseMock(None)
            self.broken = False

    def request(self, action, uri, body, headers):
        if self.broken:
            if "ExceptOnBadServer" in uri:
                raise Exception("Broken server got an unexpected request")
            return
        if uri.endswith('attachment') and action == 'DELETE':
            self.response = HTTPResponseMock404(None)
        else:
            self.response = HTTPResponseMock(None)
        return

    def getresponse(self):
        return self.response

    def close(self):
        pass


class BigSwitchProxyPluginV2TestCase(test_plugin.QuantumDbPluginV2TestCase):

    _plugin_name = ('%s.QuantumRestProxyV2' % RESTPROXY_PKG_PATH)

    def setUp(self):
        etc_path = os.path.join(os.path.dirname(__file__), 'etc')
        test_lib.test_config['config_files'] = [os.path.join(etc_path,
                                                'restproxy.ini.test')]

        self.httpPatch = patch('httplib.HTTPConnection', create=True,
                               new=HTTPConnectionMock)
        self.addCleanup(self.httpPatch.stop)
        MockHTTPConnection = self.httpPatch.start()
        super(BigSwitchProxyPluginV2TestCase,
              self).setUp(self._plugin_name)


class TestBigSwitchProxyBasicGet(test_plugin.TestBasicGet,
                                 BigSwitchProxyPluginV2TestCase):

    pass


class TestBigSwitchProxyV2HTTPResponse(test_plugin.TestV2HTTPResponse,
                                       BigSwitchProxyPluginV2TestCase):

    def test_failover_memory(self):
        # first request causes failover so next shouldn't hit bad server
        with self.network() as net:
            kwargs = {'tenant_id': 'ExceptOnBadServer'}
            with self.network(**kwargs) as net:
                req = self.new_show_request('networks', net['network']['id'])
                res = req.get_response(self.api)
                self.assertEqual(res.status_int, 200)


class TestBigSwitchProxyPortsV2(test_plugin.TestPortsV2,
                                BigSwitchProxyPluginV2TestCase,
                                test_bindings.PortBindingsTestCase):

    VIF_TYPE = portbindings.VIF_TYPE_OVS
    HAS_PORT_FILTER = False


class TestBigSwitchProxyPortsV2IVS(test_plugin.TestPortsV2,
                                   BigSwitchProxyPluginV2TestCase,
                                   test_bindings.PortBindingsTestCase):
    VIF_TYPE = portbindings.VIF_TYPE_IVS
    HAS_PORT_FILTER = False

    def setUp(self):
        super(TestBigSwitchProxyPortsV2IVS,
              self).setUp()
        cfg.CONF.set_override('vif_type', 'ivs', 'NOVA')


class TestBigSwitchProxyNetworksV2(test_plugin.TestNetworksV2,
                                   BigSwitchProxyPluginV2TestCase):

    pass


class TestBigSwitchProxySubnetsV2(test_plugin.TestSubnetsV2,
                                  BigSwitchProxyPluginV2TestCase):

    pass


class TestBigSwitchProxySync(BigSwitchProxyPluginV2TestCase):

    def test_send_data(self):
        plugin_obj = QuantumManager.get_plugin()
        result = plugin_obj._send_all_data()
        self.assertEqual(result[0], 200)
