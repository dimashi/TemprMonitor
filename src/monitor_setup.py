import private_info


class Setup:
    temp_min = 50.0
    temp_max = 90.0
    calc_external_temp = True
    external_temp_offset_c = 5
    phones_numbers = private_info.phone_numbers
    emails = private_info.emails
    user = private_info.user
    password = private_info.password
    sleep_between_get_temp = 300
    sleep_after_send_sms = 1800
    process_input = False
