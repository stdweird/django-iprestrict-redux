from django.core import exceptions
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings

from iprestrict import models
from iprestrict.middleware import IPRestrictMiddleware

LOCAL_IP = "192.168.1.1"
PROXY = "1.1.1.1"


class MiddlewareRestrictsTest(TestCase):
    """
    When the middleware is enabled it should restrict all IPs(but localhost)/URLs by default.
    """

    def setUp(self):
        models.ReloadRulesRequest.request_reload()

    def assert_url_is_restricted(self, url):
        response = self.client.get(url, REMOTE_ADDR=LOCAL_IP)
        self.assertEqual(response.status_code, 403)

    def assert_ip_is_restricted(self, ip):
        response = self.client.get("", REMOTE_ADDR=ip)
        self.assertEqual(response.status_code, 403)

    def test_middleware_restricts_every_url(self):
        self.assert_url_is_restricted("")
        self.assert_url_is_restricted("/every")
        self.assert_url_is_restricted("/url")
        self.assert_url_is_restricted("/is_restricted")
        self.assert_url_is_restricted("/every/url/is_restricted")

    def test_middleware_restricts_ips(self):
        self.assert_ip_is_restricted("192.168.1.1")
        self.assert_ip_is_restricted("10.10.10.1")
        self.assert_ip_is_restricted("169.254.0.1")

    def test_middleware_allows_localhost(self):
        response = self.client.get("/some/url", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 404)


def create_ip_allow_rule(ip=LOCAL_IP):
    localip = models.RangeBasedIPGroup.objects.create(name="localip")
    models.IPRange.objects.create(ip_group=localip, first_ip=LOCAL_IP)
    models.Rule.objects.create(url_pattern="ALL", ip_group=localip, action="A")


class MiddlewareAllowsTest(TestCase):
    def setUp(self):
        create_ip_allow_rule()
        models.ReloadRulesRequest.request_reload()

    def test_middleware_allows_localhost(self):
        response = self.client.get("")
        self.assertEqual(response.status_code, 404)

    def test_middleware_allows_ip_just_added(self):
        response = self.client.get("", REMOTE_ADDR=LOCAL_IP)
        self.assertEqual(response.status_code, 404)

    def test_middleware_restricts_other_ip(self):
        response = self.client.get("", REMOTE_ADDR="10.1.1.1")
        self.assertEqual(response.status_code, 403)

    @override_settings(IPRESTRICT_TRUSTED_PROXIES=(PROXY,))
    def test_middleware_allows_if_proxy_is_trusted(self):
        response = self.client.get("", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=LOCAL_IP)
        self.assertEqual(response.status_code, 404)

    def test_middleware_restricts_if_proxy_is_not_trusted(self):
        response = self.client.get("", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=LOCAL_IP)
        self.assertEqual(response.status_code, 403)

    @override_settings(
        IPRESTRICT_TRUSTED_PROXIES=(LOCAL_IP,), IPRESTRICT_USE_PROXY_IF_UNKNOWN=True
    )
    def test_middleware_allows_if_PROXY_is_used_and_allowed_when_IP_is_unknown(self):
        response = self.client.get(
            "", REMOTE_ADDR=LOCAL_IP, HTTP_X_FORWARDED_FOR="unknown"
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(IPRESTRICT_USE_PROXY_IF_UNKNOWN=True)
    def test_middleware_restricts_if_PROXY_is_used_but_NOT_allowed_when_IP_is_unknown(
        self,
    ):
        response = self.client.get(
            "", REMOTE_ADDR=LOCAL_IP, HTTP_X_FORWARDED_FOR="unknown"
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(IPRESTRICT_TRUSTED_PROXIES=(PROXY,))
    def test_middleware_restricts_if_IP_is_unknown(self):
        response = self.client.get(
            "", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR="unknown"
        )
        self.assertEqual(response.status_code, 403)


class ReloadRulesTest(TestCase):
    def setUp(self):
        create_ip_allow_rule()

    def test_reload_with_custom_command(self):
        from django.core.management import call_command

        call_command("reload_rules", verbosity=0)

        response = self.client.get("", REMOTE_ADDR=LOCAL_IP)
        self.assertEqual(response.status_code, 404)


def dummy_get_response():
    return None


class MiddlewareExtractClientIpTest(TestCase):
    def setUp(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        self.factory = RequestFactory()

    def test_remote_addr_only(self):
        request = self.factory.get("", REMOTE_ADDR=LOCAL_IP)

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, LOCAL_IP)

    def test_remote_addr_empty(self):
        request = self.factory.get("", REMOTE_ADDR="")

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, "")

    @override_settings(IPRESTRICT_TRUSTED_PROXIES=(PROXY,))
    def test_single_proxy(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        request = self.factory.get("", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=LOCAL_IP)

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, LOCAL_IP)

    @override_settings(IPRESTRICT_TRUSTED_PROXIES=(PROXY, "2.2.2.2", "4.4.4.4"))
    def test_multiple_proxies_one_not_trusted(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        proxies = ["2.2.2.2", "3.3.3.3", "4.4.4.4"]
        request = self.factory.get(
            "", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=", ".join([LOCAL_IP] + proxies)
        )

        try:
            _ = self.middleware.extract_client_ip(request)
        except exceptions.PermissionDenied:
            pass
        else:
            self.fail("Should raise PermissionDenied exception")

    @override_settings(
        IPRESTRICT_TRUSTED_PROXIES=(PROXY, "2.2.2.2", "3.3.3.3", "4.4.4.4")
    )
    def test_multiple_proxies_all_trusted(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        proxies = ["2.2.2.2", "3.3.3.3", "4.4.4.4"]
        request = self.factory.get(
            "", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=", ".join([LOCAL_IP] + proxies)
        )

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, LOCAL_IP)

    @override_settings(IPRESTRICT_TRUST_ALL_PROXIES=True)
    def test_trust_all_proxies_on(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        proxies = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]
        request = self.factory.get(
            "", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=", ".join([LOCAL_IP] + proxies)
        )

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, LOCAL_IP)

    @override_settings(
        IPRESTRICT_TRUST_ALL_PROXIES=True, IPRESTRICT_USE_PROXY_IF_UNKNOWN=True
    )
    def test_use_proxy_if_unknown(self):
        self.middleware = IPRestrictMiddleware(dummy_get_response)
        proxies = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]
        request = self.factory.get(
            "", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=", ".join(["unknown"] + proxies)
        )

        client_ip = self.middleware.extract_client_ip(request)
        self.assertEqual(client_ip, PROXY)
