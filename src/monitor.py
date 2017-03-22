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

    stop = False
    device = None
    mailer = None
    sim_exists = None
    last_msg_time = datetime.now()

    @classmethod
    def battery_to_string(cls, battery_status, battery_level):
        status_char_map = \
            {BatteryStatus.unknown:         "?",
             BatteryStatus.charging:         "+",
             BatteryStatus.discharging:      "-",
             BatteryStatus.notcharging:      "_",
             BatteryStatus.full:             "^"}
        return "%s%s" % (battery_level, status_char_map[battery_status])

    @classmethod
    def get_battery_info(cls):
        phone = cls.get_device()
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

        battery_status_str = cls.battery_to_string(battery_status, battery_level)

        # divides so temp will come out correct in C
        temp_c = temp_in_c10 / 10.0
        temp_f = c_to_f(temp_c)
        if Setup.calc_external_temp:
            external_temp_c = get_external_temp_c(temp_c)
            external_temp_f = c_to_f(external_temp_c)
            cls.log("%s, %.0fF, ext %.0fF" % (battery_status_str, temp_f, external_temp_f))
            temp_f = external_temp_f
        else:
            cls.log("%s, %.0fF" % (battery_status_str, temp_f))

        return battery_status, battery_level, temp_f

    @classmethod
    def try_get_battery_info(cls):
        try:
            return cls.get_battery_info()
        except Exception as err:
            cls.log_error(err.args)

    @classmethod
    def make_alerts(cls, temp_f, battery_status, battery_level):
        alerts = []
        if temp_f < Setup.temp_min:
            alert = Alert("Freezing", "Freezing below %s F: current temp %.0f F" % (Setup.temp_min, temp_f))
            alerts.append(alert)
        elif temp_f > Setup.temp_max:
            alert = Alert("Freezing", "Frying above %s F: current temp %.0f F" % (Setup.temp_max, temp_f))
            alerts.append(alert)
        if battery_status in [BatteryStatus.notcharging, BatteryStatus.discharging]:
            if battery_level < Setup.low_battery:
                alert = Alert("Power loss", "Battery: " + cls.battery_to_string(battery_status, battery_level))
                alerts.append(alert)

        return alerts

    @classmethod
    def run(cls):

        while True:
            cls.acquire_device()
            battery_status, battery_level, temp_f = cls.try_get_battery_info()

            alerts = cls.make_alerts(temp_f)
            if len(alerts) == 0:
                sleep_period = Setup.sleep_between_get_temp
            else:
                sleep_period = Setup.sleep_after_send_sms
                cls.send_notification(alerts)

            if cls.stop:
                break

            if Setup.process_input:
                cls.process_input(sleep_period)
            else:
                sleep(sleep_period)
            cls.release_device()

        cls.release_device()

    @classmethod
    def acquire_device(cls):
        cls.get_device().wakeLockAcquirePartial()

    @classmethod
    def send_notification(cls, alerts):
        for alert in alerts:
            if cls.sim_exists:
                cls.log("Texting to %s:" % Setup.phones_numbers, alert.title)
                for phone_number in Setup.phones_numbers:
                    cls.get_device().smsSend(phone_number, alert.msg)
            cls.log("Emailing to %s:" % Setup.emails, alert.title)
            if cls.try_send_email(alert):
                cls.log("Email sent")


    @classmethod
    def process_input(cls, sleep_time):
        slept = 0
        short_sleep = 5
        while slept < sleep_time:
            now = datetime.now()
            (msgid, messages, error) = cls.get_device().smsGetMessages(False, 'inbox')
            if error is not None:
                cls.log_error("smsGetMessages returned error:", error)

            for m in messages:
                if datetime.fromtimestamp(int(m["date"])/1000) >= cls.last_msg_time:
                    cls.log("Received message", m)
                    cls.last_msg_time = now

                    if cls.execute_command(m["body"]):
                        return

            sleep(short_sleep)
            slept += short_sleep

    @classmethod
    def execute_command(cls, text):
        try:
            exec(text)
            cls.log("Executed:", text)
            return True
        except Exception as err:
            cls.log_error("Error execution command %s. error %s" % (text, err.args))

    @staticmethod
    def log(*args):
        log(*args)

    @classmethod
    def log_error(cls, *args):
        cls.log(*args)

    @classmethod
    def get_device(cls):
        if cls.device is None:
            import android
            cls.device = android.Android()
            (opid, result, error) = cls.device.getNetworkOperatorName()
            sim_exists = len(result) > 1
            if cls.sim_exists != sim_exists:
                cls.log("getNetworkOperatorName: ", opid, result, error)
                cls.sim_exists = sim_exists
        return cls.device

    @classmethod
    def send_email(cls, alert):
        ret = False
        try:
            cls.ensure_wifi()
            if cls.mailer is None:
                import yagmail
                cls.mailer = yagmail.SMTP(Setup.user, Setup.password)
            else:
                cls.mailer.login(Setup.password)

            ret = cls.mailer.send(Setup.emails, alert.title, alert.msg)
        except:
            info = traceback.format_exc()
            cls.log(info)

        if cls.mailer is not None:
            cls.mailer.close()

        if ret == False:
            return False
        elif isinstance(ret, dict):
            if len(ret) == 0:
                return True
            else:
                cls.log("Refused recipients:", ret)
        else:
            cls.log("Unexpected return value from send:", ret)
        return False


    @classmethod
    def ensure_wifi(cls):
        phone = cls.get_device()
        for i in range(3):
            (wifiid, is_connected, error) = phone.checkWifiState()
            if is_connected:
                if i > 0: # not first attempt
                    cls.log("Connected to WiFi. attempt", i)
                return
            (wifiid, is_connected, error) = phone.toggleWifiState(1)
            if is_connected:
                cls.log("Re-connected to WiFi after", i, "attempt")
                return
            else:
                cls.log("Failed attempt", i, "re-connecting WiFi. Error", error)
            sleep(2)
        cls.log("Cannot connect to WiFi")

    @classmethod
    def try_send_email(cls, alert):
        for i in range(3):
            if cls.send_email(alert):
                return True
            sleep(2)
        return False

    @classmethod
    def release_device(cls):
        if cls.device is None:
            return
        cls.get_device().wakeLockRelease()
        cls.device = None
