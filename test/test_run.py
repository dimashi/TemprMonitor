import unittest
from datetime import datetime
from unittest.mock import Mock
from monitor import TempMonitor, c_to_f, BatteryStatus, get_external_temp_c
from monitor_setup import Setup


class TestRun(unittest.TestCase):
    def setUp(self):
        self.mon = TempMonitor()
        self.mon.device = Mock()
        self.mon.log = Mock()
        self.mon.log_error = Mock()

        self.mon.device.smsSend = Mock()
        self.mon.device.batteryGetStatus = Mock(return_value=(0, BatteryStatus.unknown, None))
        self.mon.device.batteryGetLevel = Mock(return_value=(0, 77, None))
        self.mon.device.get_device = Mock(return_value=self.mon.device)

    def test_get_external_temp(self):
        battery_C_temp = 30
        battery_F_temp = c_to_f(battery_C_temp)
        expected_external_C_temp = get_external_temp_c(battery_C_temp)
        expected_F_temp = c_to_f(expected_external_C_temp)
        Setup.calc_external_temp = True
        self.mon.device.batteryGetTemperature = Mock(return_value=(1, battery_C_temp * 10, None))

        battery_status, battery_level, temp_in_F = self.mon.get_battery_info()
        self.assertEquals(expected_F_temp, temp_in_F)
        self.mon.log.assert_called_with("77?, %.0fF, ext %.0fF" % (battery_F_temp, expected_F_temp))

    def test_run_normal(self):
        Setup.temp_min = 0
        Setup.temp_max = 200
        self.mon.get_battery_info = Mock(return_value=(1, 2, 60.0))
        self.mon.make_alerts = Mock(return_value=["alert1"])
        self.mon.send_notification = Mock()
        self.mon.stop = True

        self.mon.run()
        self.mon.get_battery_info.assert_called_once_with()
        self.assertTrue(self.mon.make_alerts.called)
        self.assertTrue(self.mon.send_notification.called)

    def test_run_freezing(self):
        Setup.temp_min = 40
        Setup.temp_max = 200
        temp = 30
        self.mon.get_battery_info = Mock(return_value=(1, 2, temp))
        self.mon.send_email = Mock()
        self.mon.stop = True
        self.mon.sim_exists = True
        device = self.mon.device

        self.mon.run()
        self.mon.get_battery_info.assert_called_once_with()
        self.mon.send_email.assert_called()
        device.sendSms.assert_called()

    def test_run_frying(self):
        Setup.temp_min = 40
        Setup.temp_max = 100
        temp = 200
        self.mon.get_battery_info = Mock(return_value=(1, 2, temp))
        expected_message = "Frying above %sF: 2?, %.0fF" % (Setup.temp_max, temp)
        self.mon.stop = True
        self.mon.sim_exists = True
        device = self.mon.device

        self.mon.run()
        self.mon.get_battery_info.assert_called_once_with()
        device.smsSend.assert_called_with(Setup.phones_numbers[len(Setup.phones_numbers) - 1], expected_message)

    def test_process_input(self):
        last_msg_time = datetime.now()
        self.mon.device.smsGetMessages = Mock(return_value=(
        0, [{"date": str(int(last_msg_time.timestamp() / 1000)), "address": "123456789", "body": "hi"}], None))
        self.mon.process_input(1)

    def test_execute_command(self):
        self.mon.execute_command("Setup.temp_max = 78.1")
        self.assertEquals(78.1, Setup.temp_max)

    def test_execute_command_failed(self):
        self.mon.log_error = Mock()
        self.mon.execute_command("No_Setup.temp_max = 78.33")
        self.assertNotEquals(78.33, Setup.temp_max)
        self.mon.log_error.assert_called_once_with(
            'Error execution command No_Setup.temp_max = 78.33. error ("name \'No_Setup\' is not defined",)')

    def test_execute_command_failed2(self):
        text = "Regular text message"
        self.mon.execute_command(text)
        self.assertNotEquals(78.33, Setup.temp_max)
        self.mon.log_error.assert_called_once_with(
            "Error execution command Regular text message. error ('invalid syntax', ('<string>', 1, 12, 'Regular text message\\n'))")
