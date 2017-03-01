from datetime import datetime
from time import sleep

from src import config


class Setup:
    temp_min = 50.0
    temp_max = 90.0
    calc_external_temp = True
    external_temp_offset_C = 5
    phones_numbers = config.phone_numbers
    emails = config.emails
    user = config.user
    password = config.password
    sleep_between_get_temp = 300
    sleep_after_send_sms = 1800

def C_to_F(temp_in_C):
    return temp_in_C * 1.8 + 32

def log(*args):
    print(datetime.now().strftime('%c'), end = " ")
    print(*args)

def get_external_temp_C(temp_in_C):
    ## http://opensignal.com/reports/battery-temperature-weather/
    # return 2.55 * temp_in_C - 60.55  # does not work well on Galaxy4
    return temp_in_C - Setup.external_temp_offset_C

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

        #program halt to allow time for battery information
        sleep(.5)

        #Gets temp from system and sets temp_in_C100 as temp in celcius( * 100)
        (id_temp, temp_in_C100, error_temp) =       phone.batteryGetTemperature()
        (id_level, battery_level, error_level) =    phone.batteryGetLevel()
        (id_status, battery_status, error_status) = phone.batteryGetStatus()

        phone.batteryStopMonitoring()

        for name, error in [("temperature", error_temp), ("level", error_level), ("status", error_status)]:
            if error is not None:
                raise RuntimeError("Error getting battery %s: %s" % (name, error))

        battery_status_str = cls.battery_to_string(battery_status, battery_level)

        #divides so temp will come out correct in C
        temp_in_C = temp_in_C100 / 10.0
        temp_in_F = C_to_F(temp_in_C)
        if Setup.calc_external_temp:
            external_temp_in_C = get_external_temp_C(temp_in_C)
            external_temp_in_F = C_to_F(external_temp_in_C)
            cls.log("%s, %.2fF, external %.2fF" % (battery_status_str, temp_in_F, external_temp_in_F))
            temp_in_F = external_temp_in_F
        else:
            cls.log("%s, %.2fF" % (battery_status_str, temp_in_F))

        return battery_status, battery_level, temp_in_F

    @classmethod
    def try_get_battery_info(cls):
        try:
            return cls.get_battery_info()
        except Exception as err:
            cls.log_error(err.args)

    @classmethod
    def make_message(cls, temp_in_F):
        message = None
        if temp_in_F < Setup.temp_min:
            message = "Freezing below %s F: current temp %.2f F" % (Setup.temp_min, temp_in_F)

        if temp_in_F > Setup.temp_max:
            message = "Frying above %s F: current temp %.2f F" % (Setup.temp_max, temp_in_F)
        return message

    @classmethod
    def run(cls):
        cls.get_device().wakeLockAcquirePartial()
        while True:
            battery_status, battery_level, temp_in_F = cls.try_get_battery_info()

            message = cls.make_message(temp_in_F)
            if message is None:
                sleep_period = Setup.sleep_between_get_temp
            else:
                sleep_period = Setup.sleep_after_send_sms
                cls.log("Texting to %s:" % Setup.phones_numbers, message)
                for phone_number in Setup.phones_numbers:
                    cls.get_device().smsSend(phone_number, message)

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
            (id, messages, error) = cls.get_device().smsGetMessages(False, 'inbox')
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
        return cls.device

    @classmethod
    def send_email(cls, msg):
        if cls.mailer is None:
            import yagmail
            cls.mailer = yagmail.SMTP(Setup.user, Setup.password)
        cls.mailer.send(Setup.emails, 'Temperature monitor', msg)

print("File name:", __file__, "Module name:", __name__)
if __name__ == '__main__':
    TempMonitor.run()
else:
    print("Unit testing")













