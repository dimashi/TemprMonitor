from unittest import TestCase

from mock import Mock

from monitor import TempMonitor, BatteryStatus, c_to_f
from monitor_setup import Setup


class TestBatteryInfo(TestCase):

    def setUp(self):
        self.device = Mock()
        self.device.batteryGetStatus = Mock(return_value=(0, BatteryStatus.unknown, None))
        self.device.batteryGetLevel = Mock(return_value=(0, 77, None))
        self.mon = TempMonitor()
        self.mon.init_device = Mock(return_value=self.device)
        self.mon.device = self.device
        self.mon.log = Mock()
        self.mon.log_error = Mock()

    def test_battery_to_string(self):
        self.assertEqual("10+", self.mon.battery_to_string(BatteryStatus.charging, 10))
        self.assertEqual("11-", self.mon.battery_to_string(BatteryStatus.discharging, 11))
        self.assertEqual("12^", self.mon.battery_to_string(BatteryStatus.full, 12))
        self.assertEqual("13_", self.mon.battery_to_string(BatteryStatus.notcharging, 13))
        self.assertEqual("14?", self.mon.battery_to_string(BatteryStatus.unknown, 14))

    def test_get_battery_info(self):
        id_temp = "id_temp"
        temp_in_c10 = 200.0
        error_temp = None
        self.device.batteryGetTemperature.return_value = (id_temp, temp_in_c10, error_temp)

        id_level = "id_level"
        battery_level = 20
        error_level = None
        self.device.batteryGetLevel.return_value = (id_level, battery_level, error_level)

        id_status = "id_status"
        battery_status = BatteryStatus.charging
        error_status = None
        self.device.batteryGetStatus.return_value = (id_status, battery_status, error_status)

        (actual_battery_status, actual_battery_level, temp_f) = self.mon.get_battery_info()

        self.assertEqual(battery_status, actual_battery_status)
        self.assertEqual(battery_level, actual_battery_level)
        self.assertEqual(59.0, temp_f)
        assert self.device.batteryStartMonitoring.called
        assert self.device.batteryGetTemperature.called
        assert self.device.batteryGetLevel.called
        assert self.device.batteryGetStatus.called

    def test_get_temp(self):
        expected_c_temp = 10.12345
        expected_f_temp = c_to_f(expected_c_temp)
        Setup.calc_external_temp = False
        self.device.batteryGetTemperature = Mock(return_value=(1, expected_c_temp * 10, None))

        battery_status, battery_level, temp_in_f = self.mon.get_battery_info()
        self.assertEquals(expected_f_temp, temp_in_f)
        self.assertEquals(BatteryStatus.unknown, battery_status)
        self.assertEquals(77, battery_level)
        self.mon.log.assert_called_with("77?, 50F")

    def test_try_get_temp_error(self):
        error = "Mock error"
        self.device.batteryGetTemperature = Mock(return_value=(1, 0, error))

        self.assertIsNone(self.mon.try_get_battery_info())
        self.mon.log_error.assert_called_with(("Error getting battery temperature: " + error,))
