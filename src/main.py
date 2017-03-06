from datetime import datetime
from time import sleep

import config


class Setup:
    temp_min = 50.0
    temp_max = 90.0
    calc_external_temp = True
    external_temp_offset_c = 5
    phones_numbers = config.phone_numbers
    emails = config.emails
    user = config.user
    password = config.password
    sleep_between_get_temp = 300
    sleep_after_send_sms = 1800


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
    sim_exists = False
    last_msg_time = datetime.now()

    @staticmethod
    def battery_to_string(battery_status, battery_level):
        status_char_map =  \
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
        sleep(.5)

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
    def make_message(cls, temp_f):
        message = None
        if temp_f < Setup.temp_min:
            message = "Freezing below %s F: current temp %.0f F" % (Setup.temp_min, temp_f)

        if temp_f > Setup.temp_max:
            message = "Frying above %s F: current temp %.0f F" % (Setup.temp_max, temp_f)
        return message

    @classmethod
    def run(cls):
        cls.get_device().wakeLockAcquirePartial()
        while True:
            battery_status, battery_level, temp_f = cls.try_get_battery_info()

            message = cls.make_message(temp_f)
            if message is None:
                sleep_period = Setup.sleep_between_get_temp
            else:
                sleep_period = Setup.sleep_after_send_sms
                if cls.sim_exists:
                    cls.log("Texting to %s:" % Setup.phones_numbers, message)
                    for phone_number in Setup.phones_numbers:
                        cls.get_device().smsSend(phone_number, message)

                cls.log("Emailing to %s:" % Setup.emails, message)
                if cls.send_email(message):
                    cls.log("Email sent")

            if cls.stop:
                break

            cls.process_input(sleep_period)
        cls.get_device().wakeLockRelease()

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
            (simid, result, error) = cls.device.getSimState()
            cls.sim_exists = error is None
            cls.log("SIM state: ", simid, result, error)
        return cls.device

    @classmethod
    def send_email(cls, msg):
        if cls.mailer is None:
            import yagmail
            cls.mailer = yagmail.SMTP(Setup.user, Setup.password)
        if not cls.mailer.send(Setup.emails, 'Temperature monitor', msg):
            cls.mailer.login(Setup.password)
            return cls.mailer.send(Setup.emails, 'Temperature monitor', msg)
        else:
            return True


print("File name:", __file__, "Module name:", __name__)
if __name__ == '__main__':
    TempMonitor.run()
else:
    print("Unit testing")
