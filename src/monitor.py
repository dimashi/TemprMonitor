import traceback
from datetime import datetime
from time import sleep

from alert import Alert
from monitor_setup import Setup


def c_to_f(temp_c):
    return temp_c * 1.8 + 32


def log(*args):
    print(datetime.now().strftime('%a %x %X'), end=" ")
    print(*args)


def get_external_temp_c(temp_c):
    # http://opensignal.com/reports/battery-temperature-weather/
    # return 2.55 * temp_c - 60.55  # does not work well on Galaxy4
    return temp_c - Setup.external_temp_offset_c


class BatteryStatus:
    unknown = 1
    charging = 2
    discharging = 3
    notcharging = 4
    full = 5


class TempMonitor:

    def __init__(self):
        self.stop = False
        self.device = None
        self.mailer = None
        self.sim_exists = None
        self.last_msg_time = datetime.now()

    @staticmethod
    def battery_to_string(battery_status, battery_level):
        status_char_map = \
            {BatteryStatus.unknown:         "?",
             BatteryStatus.charging:         "+",
             BatteryStatus.discharging:      "-",
             BatteryStatus.notcharging:      "_",
             BatteryStatus.full:             "^"}
        return "%s%s" % (battery_level, status_char_map[battery_status])

    def get_battery_info(self):
        phone = self.get_device()
        phone.batteryStartMonitoring()

        # program halt to allow time for battery information
        sleep(10)

        # gets temp from system and sets temp_c10 as temp in celcius( * 10)
        (id_temp, temp_in_c10, error_temp) = phone.batteryGetTemperature()
        (id_level, battery_level, error_level) = phone.batteryGetLevel()
        (id_status, battery_status, error_status) = phone.batteryGetStatus()

        phone.batteryStopMonitoring()

        for name, error in [("temperature", error_temp), ("level", error_level), ("status", error_status)]:
            if error is not None:
                raise RuntimeError("Error getting battery %s: %s" % (name, error))

        battery_status_str = self.battery_to_string(battery_status, battery_level)

        # divides so temp will come out correct in C
        temp_c = temp_in_c10 / 10.0
        temp_f = c_to_f(temp_c)
        if Setup.calc_external_temp:
            external_temp_c = get_external_temp_c(temp_c)
            external_temp_f = c_to_f(external_temp_c)
            self.log(self.make_info_string(battery_status_str, temp_f, external_temp_f))
            temp_f = external_temp_f
        else:
            self.log(self.make_info_string(battery_status_str, temp_f))

        return battery_status, battery_level, temp_f

    @staticmethod
    def make_info_string(battery_status_str, temp_f, external_temp_f=None):
        if external_temp_f is None:
            return "%s, %.0fF" % (battery_status_str, temp_f)
        else:
            return "%s, %.0fF, ext %.0fF" % (battery_status_str, temp_f, external_temp_f)

    def try_get_battery_info(self):
        try:
            return self.get_battery_info()
        except Exception as err:
            self.log_error(err.args)

    def make_alerts(self, battery_status, battery_level, temp_f):
        alerts = []
        current_info = self.make_info_string(self.battery_to_string(battery_status, battery_level), temp_f)
        if temp_f < Setup.temp_min:
            alert = Alert("Freezing", ("Freezing below %sF: " % Setup.temp_min) + current_info)
            alerts.append(alert)
        elif temp_f > Setup.temp_max:
            alert = Alert("Frying", ("Frying above %sF: " % Setup.temp_max) + current_info)
            alerts.append(alert)
        if battery_status in [BatteryStatus.notcharging, BatteryStatus.discharging]:
            if battery_level < Setup.low_battery:
                alert = Alert("Power loss", ("Battery level below %s" % Setup.low_battery) + current_info)
                alerts.append(alert)

        return alerts

    def run(self):

        while True:
            self.acquire_device()
            battery_status, battery_level, temp_f = self.try_get_battery_info()

            alerts = self.make_alerts(battery_status, battery_level, temp_f)
            if len(alerts) == 0:
                sleep_period = Setup.sleep_between_get_temp
            else:
                sleep_period = Setup.sleep_after_send_sms
                self.send_notification(alerts)

            if self.stop:
                break

            if Setup.process_input:
                self.process_input(sleep_period)
            else:
                sleep(sleep_period)
            self.release_device()

        self.release_device()

    def acquire_device(self):
        self.get_device().wakeLockAcquirePartial()

    def send_notification(self, alerts):
        for alert in alerts:
            if self.sim_exists:
                self.log("Texting to %s:" % Setup.phones_numbers, alert.title)
                for phone_number in Setup.phones_numbers:
                    self.get_device().smsSend(phone_number, alert.msg)
            self.log("Emailing to %s:" % Setup.emails, alert.title)
            if self.try_send_email(alert):
                self.log("Email sent")

    def process_input(self, sleep_time):
        slept = 0
        short_sleep = 5
        while slept < sleep_time:
            now = datetime.now()
            (msgid, messages, error) = self.get_device().smsGetMessages(False, 'inbox')
            if error is not None:
                self.log_error("smsGetMessages returned error:", error)

            for m in messages:
                if datetime.fromtimestamp(int(m["date"])/1000) >= self.last_msg_time:
                    self.log("Received message", m)
                    self.last_msg_time = now

                    if self.execute_command(m["body"]):
                        return

            sleep(short_sleep)
            slept += short_sleep

    def execute_command(self, text):
        try:
            exec(text)
            self.log("Executed:", text)
            return True
        except Exception as err:
            self.log_error("Error execution command %s. error %s" % (text, err.args))

    @staticmethod
    def log(*args):
        log(*args)

    def log_error(self, *args):
        self.log(*args)

    def get_device(self):
        if self.device is None:
            import android
            self.device = android.Android()
            (opid, result, error) = self.device.getNetworkOperatorName()
            sim_exists = len(result) > 1
            if self.sim_exists != sim_exists:
                self.log("getNetworkOperatorName: ", opid, result, error)
                self.sim_exists = sim_exists
        return self.device

    def send_email(self, alert):
        ret = False
        try:
            self.ensure_wifi()
            if self.mailer is None:
                import yagmail
                self.mailer = yagmail.SMTP(Setup.user, Setup.password)
            else:
                self.mailer.login(Setup.password)

            ret = self.mailer.send(Setup.emails, alert.title, alert.msg)
        except:
            info = traceback.format_exc()
            self.log(info)

        if self.mailer is not None:
            self.mailer.close()

        if ret is False:
            return False
        elif isinstance(ret, dict):
            if len(ret) == 0:
                return True
            else:
                self.log("Refused recipients:", ret)
        else:
            self.log("Unexpected return value from send:", ret)
        return False

    def ensure_wifi(self):
        phone = self.get_device()
        if self.reconnect_wifi():
            for i in range(10):
                (info_id, info, error) = phone.wifiGetConnectionInfo()
                if error is None:
                    if info["supplicant_state"] == "completed" and info["ip"] > 0:
                        return
                sleep(Setup.sleep_waiting_wifi)

    def reconnect_wifi(self):
        phone = self.get_device()
        for i in range(3):
            (wifiid, is_connected, error) = phone.checkWifiState()
            if is_connected:
                if i > 0:  # not first attempt
                    self.log("Connected to WiFi. attempt", i)
                return True
            (wifiid, is_connected, error) = phone.toggleWifiState(1)
            if is_connected:
                self.log("Re-connected to WiFi after", i, "attempt")
                return True
            else:
                self.log("Failed attempt", i, "re-connecting WiFi. Error", error)
            sleep(2)
        self.log("Cannot connect to WiFi")
        return False

    def try_send_email(self, alert):
        for i in range(3):
            if self.send_email(alert):
                return True
            sleep(2)
        return False

    def release_device(self):
        if self.device is None:
            return
        self.get_device().wakeLockRelease()
        self.device = None
