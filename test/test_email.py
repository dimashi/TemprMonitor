import socket
from unittest.mock import Mock

from unittest import TestCase

import private_info
from alert import Alert
from monitor import TempMonitor
from monitor_setup import Setup


class TestEmail(TestCase):

    def setUp(self):
        Setup.emails = private_info.test_emails
        self.mon = TempMonitor()
        self.mon.ensure_wifi = Mock()

    def test_send_email(self):
        # test sending real email
        # ensure_wifi_mock.side_effect
        self.assertTrue(self.mon.send_email(Alert("test1", "msg1")))
        self.assertTrue(self.mon.send_email(Alert("test2", "msg2")))

    def test_send_email_mock(self):
        self.mon.mailer = Mock()
        self.mon.mailer.send.return_value = {}
        self.assertTrue(self.mon.send_email(Alert("test", "msg")))
        # assert ensure_wifi_mock.called
        assert self.mon.mailer.login.called
        assert self.mon.mailer.send.called
        assert self.mon.mailer.close.called

    def test_send_try_email(self):
        self.mon.send_email = Mock(return_value=True)
        self.assertTrue(self.mon.try_send_email("test"))
        self.assertEqual(1, self.mon.send_email.call_count)

    def test_send_try_email_failed(self):
        self.mon.send_email = Mock(return_value=False)
        self.assertFalse(self.mon.try_send_email("test"))
        self.assertEqual(3, self.mon.send_email.call_count)

    def test_send_email_mock_failed_send_exception(self):
        self.mon.ensure_wifi = Mock()
        self.mon.mailer = Mock()
        self.mon.mailer.send.side_effect = socket.gaierror
        self.assertFalse(self.mon.send_email(Alert("test1", "msg1")))
        assert self.mon.mailer.login.called
        assert self.mon.mailer.send.called
        assert self.mon.mailer.close.called

    def test_send_email_mock_failed_send_false(self):
        self.mon.ensure_wifi = Mock()
        self.mon.mailer = Mock()
        self.mon.mailer.send.return_value = False
        self.assertFalse(self.mon.send_email(Alert("test1", "msg1")))
        assert self.mon.mailer.login.called
        assert self.mon.mailer.send.called
        assert self.mon.mailer.close.called

    def test_send_email_mock_failed_login(self):
        self.mon.ensure_wifi = Mock()
        self.mon.mailer = Mock()
        self.mon.mailer.login.side_effect = socket.gaierror
        self.assertFalse(self.mon.send_email(Alert("test1", "msg1")))
        assert self.mon.mailer.login.called
        assert self.mon.mailer.login.not_called
        assert self.mon.mailer.close.called
