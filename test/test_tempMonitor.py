from unittest import TestCase
from unittest.mock import patch, Mock

from src.main import TempMonitor, BatteryStatus


class TestTempMonitor(TestCase):

    def test_send_email(self):
        # test sending real email
        TempMonitor.send_email("test1")
        TempMonitor.send_email("test2")


    @patch('src.main.TempMonitor.mailer')
    def test_send_email_mock(self, mailer_mock):
        TempMonitor.send_email("test")
        assert mailer_mock.send.called

    def test_battery_to_string(self):
        self.assertEqual("10+", TempMonitor.battery_to_string(BatteryStatus.charging, 10))
        self.assertEqual("11-", TempMonitor.battery_to_string(BatteryStatus.discharging, 11))
        self.assertEqual("12^", TempMonitor.battery_to_string(BatteryStatus.full, 12))
        self.assertEqual("13_", TempMonitor.battery_to_string(BatteryStatus.notcharging, 13))
        self.assertEqual("14?", TempMonitor.battery_to_string(BatteryStatus.unknown, 14))

    @patch('src.main.TempMonitor.device')
    def test_get_battery_info(self, device_mock):
        id_temp = "id_temp"
        temp_in_c10 = 200.0
        error_temp = None
        device_mock.batteryGetTemperature = Mock(return_value=(id_temp, temp_in_c10, error_temp))

        id_level = "id_level"
        battery_level = 20
        error_level = None
        device_mock.batteryGetLevel = Mock(return_value=(id_level, battery_level, error_level))

        id_status = "id_status"
        battery_status = BatteryStatus.charging
        error_status = None
        device_mock.batteryGetStatus = Mock(return_value=(id_status, battery_status, error_status))

        (actual_battery_status, actual_battery_level, temp_f) = TempMonitor.get_battery_info()

        self.assertEqual(battery_status, actual_battery_status)
        self.assertEqual(battery_level, actual_battery_level)
        self.assertEqual(59.0, temp_f)

        assert device_mock.batteryStartMonitoring.called
        assert device_mock.batteryGetTemperature.called
        assert device_mock.batteryGetLevel.called
        assert device_mock.batteryGetStatus.called
