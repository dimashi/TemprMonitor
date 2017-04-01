from unittest.mock import Mock

from unittest import TestCase

from monitor import TempMonitor


class TestWifi(TestCase):

    def setUp(self):
        self.mon = TempMonitor()
        self.mon.device = Mock()
        self.mon.log = Mock()

    def test_ensure_wifi_connected(self):
        self.mon.device.checkWifiState.return_value = (1, True, None)
        self.mon.device.wifiGetConnectionInfo.return_value = (2, {"supplicant_state" : "completed", "ip" : 101}, None)
        self.mon.ensure_wifi()
        self.assertEqual(1, self.mon.device.checkWifiState.call_count)
        self.assertEqual(0, self.mon.device.wifiReconnect.call_count)
        self.assertEqual(0, self.mon.log.call_count)

    def test_ensure_wifi_disconnected_reconnectfails_connected(self):
        self.mon.device.checkWifiState.side_effect = [(1, False, None), (2, True, None)]
        self.mon.device.toggleWifiState.return_value = (3, False, None)
        self.mon.device.wifiGetConnectionInfo.side_effect = [
            (4, {"supplicant_state" : "scanning", "ip" : 0}, None),
            (5, {"supplicant_state" : "completed", "ip" : 101}, None)
            ]
        self.mon.ensure_wifi()
        self.assertEqual(2, self.mon.device.checkWifiState.call_count)
        self.assertEqual(1, self.mon.device.toggleWifiState.call_count)
        self.mon.log.assert_called_with("Connected to WiFi. attempt", 1)

    def test_ensure_wifi_disconnected_reconnects(self):
        self.mon.device.checkWifiState.return_value = (1, False, None)
        self.mon.device.toggleWifiState.return_value = (1, True, None)
        self.mon.device.wifiGetConnectionInfo.return_value = (2, {"supplicant_state" : "completed", "ip" : 101}, None)
        self.mon.ensure_wifi()
        self.assertEqual(1, self.mon.device.checkWifiState.call_count)
        self.assertEqual(1, self.mon.device.toggleWifiState.call_count)
        self.mon.log.assert_called_with("Re-connected to WiFi after", 0, "attempt")

    def test_ensure_wifi_disconnected_reconnectfails(self):
        self.mon.device.checkWifiState.return_value = (1, False, None)
        self.mon.device.toggleWifiState.return_value = (1, False, None)
        self.mon.ensure_wifi()
        self.assertEqual(3, self.mon.device.checkWifiState.call_count)
        self.assertEqual(3, self.mon.device.toggleWifiState.call_count)
        self.mon.log.assert_called_with("Cannot connect to WiFi")
