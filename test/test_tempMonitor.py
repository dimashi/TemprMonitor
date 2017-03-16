import socket
from unittest import TestCase
from unittest.mock import patch, Mock

import private_info
from monitor_setup import Setup
from monitor import TempMonitor, BatteryStatus


class TestTempMonitor(TestCase):

    def setUp(self):
        Setup.emails = private_info.test_emails

    @patch('monitor.TempMonitor.ensure_wifi')
    def test_send_email(self, ensure_wifi_mock):
        ensure_wifi_mock()
        # test sending real email
        # ensure_wifi_mock.side_effect
        self.assertTrue(TempMonitor.send_email("test1"))
        self.assertTrue(TempMonitor.send_email("test2"))

    @patch('monitor.TempMonitor.ensure_wifi')
    @patch('monitor.TempMonitor.mailer')
    def test_send_email_mock(self, mailer_mock, ensure_wifi_mock):
        ensure_wifi_mock()
        self.assertTrue(TempMonitor.send_email("test"))
        # assert ensure_wifi_mock.called
        assert mailer_mock.login.called
        assert mailer_mock.send.called
        assert mailer_mock.close.called


    @patch('monitor.TempMonitor.send_email')
    def test_send_try_email(self, send_email_mock):
        send_email_mock.return_value = True
        self.assertTrue(TempMonitor.try_send_email("test"))
        self.assertEqual(1, send_email_mock.call_count)

    @patch('monitor.TempMonitor.send_email')
    def test_send_try_email_failed(self, send_email_mock):
        send_email_mock.return_value = False
        self.assertFalse(TempMonitor.try_send_email("test"))
        self.assertEqual(3, send_email_mock.call_count)

    @patch('monitor.TempMonitor.ensure_wifi')
    @patch('monitor.TempMonitor.mailer')
    def test_send_email_mock_failed_send_exception(self, mailer_mock, ensure_wifi_mock):
        ensure_wifi_mock()
        mailer_mock.send.side_effect = socket.gaierror
        self.assertFalse(TempMonitor.send_email("test"))
        assert mailer_mock.login.called
        assert mailer_mock.send.called
        assert mailer_mock.close.called

    @patch('monitor.TempMonitor.ensure_wifi')
    @patch('monitor.TempMonitor.mailer')
    def test_send_email_mock_failed_send_false(self, mailer_mock, ensure_wifi_mock):
        ensure_wifi_mock()
        mailer_mock.send.return_value = False
        self.assertFalse(TempMonitor.send_email("test"))
        assert mailer_mock.login.called
        assert mailer_mock.send.called
        assert mailer_mock.close.called

    @patch('monitor.TempMonitor.ensure_wifi')
    @patch('monitor.TempMonitor.mailer')
    def test_send_email_mock_failed_login(self, mailer_mock, ensure_wifi_mock):
        ensure_wifi_mock()
        mailer_mock.login.side_effect = socket.gaierror
        self.assertFalse(TempMonitor.send_email("test"))
        assert mailer_mock.login.called
        assert mailer_mock.login.not_called
        assert mailer_mock.close.called

    def test_battery_to_string(self):
        self.assertEqual("10+", TempMonitor.battery_to_string(BatteryStatus.charging, 10))
        self.assertEqual("11-", TempMonitor.battery_to_string(BatteryStatus.discharging, 11))
        self.assertEqual("12^", TempMonitor.battery_to_string(BatteryStatus.full, 12))
        self.assertEqual("13_", TempMonitor.battery_to_string(BatteryStatus.notcharging, 13))
        self.assertEqual("14?", TempMonitor.battery_to_string(BatteryStatus.unknown, 14))

    @patch('monitor.TempMonitor.device')
    def test_get_battery_info(self, device_mock):
        id_temp = "id_temp"
        temp_in_c10 = 200.0
        error_temp = None
        device_mock.batteryGetTemperature.return_value=(id_temp, temp_in_c10, error_temp)

        id_level = "id_level"
        battery_level = 20
        error_level = None
        device_mock.batteryGetLevel.return_value=(id_level, battery_level, error_level)

        id_status = "id_status"
        battery_status = BatteryStatus.charging
        error_status = None
        device_mock.batteryGetStatus.return_value=(id_status, battery_status, error_status)

        (actual_battery_status, actual_battery_level, temp_f) = TempMonitor.get_battery_info()

        self.assertEqual(battery_status, actual_battery_status)
        self.assertEqual(battery_level, actual_battery_level)
        self.assertEqual(59.0, temp_f)

        assert device_mock.batteryStartMonitoring.called
        assert device_mock.batteryGetTemperature.called
        assert device_mock.batteryGetLevel.called
        assert device_mock.batteryGetStatus.called

    @patch('monitor.TempMonitor.log')
    @patch('monitor.TempMonitor.device')
    def test_ensure_wifi_connected(self, device_mock, log_mock):
        device_mock.checkWifiState.return_value = (1, True, None)
        TempMonitor.ensure_wifi()
        self.assertEqual(1, device_mock.checkWifiState.call_count)
        self.assertEqual(0, device_mock.wifiReconnect.call_count)
        self.assertEqual(0, log_mock.call_count)

    @patch('monitor.TempMonitor.log')
    @patch('monitor.TempMonitor.device')
    def test_ensure_wifi_disconnected_reconnectfails_connected(self, device_mock, log_mock):
        device_mock.checkWifiState.side_effect = [(1, False, None), (1, True, None)]
        device_mock.wifiReconnect.return_value = (1, False, None)
        TempMonitor.ensure_wifi()
        self.assertEqual(2, device_mock.checkWifiState.call_count)
        self.assertEqual(1, device_mock.wifiReconnect.call_count)
        log_mock.assert_called_with("Connected to WiFi. attempt", 1)

    @patch('monitor.TempMonitor.log')
    @patch('monitor.TempMonitor.device')
    def test_ensure_wifi_disconnected_reconnects(self, device_mock, log_mock):
        device_mock.checkWifiState.return_value = (1, False, None)
        device_mock.wifiReconnect.return_value = (1, True, None)
        TempMonitor.ensure_wifi()
        self.assertEqual(1, device_mock.checkWifiState.call_count)
        self.assertEqual(1, device_mock.wifiReconnect.call_count)
        log_mock.assert_called_with("Re-connected to WiFi after", 0, "attempt")

    @patch('monitor.TempMonitor.log')
    @patch('monitor.TempMonitor.device')
    def test_ensure_wifi_disconnected_reconnectfails(self, device_mock, log_mock):
        device_mock.checkWifiState.return_value = (1, False, None)
        device_mock.wifiReconnect.return_value = (1, False, None)
        TempMonitor.ensure_wifi()
        self.assertEqual(3, device_mock.checkWifiState.call_count)
        self.assertEqual(3, device_mock.wifiReconnect.call_count)
        log_mock.assert_called_with("Cannot connect to WiFi")


