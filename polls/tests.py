from django.test import TestCase


class HomePageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kararsızım yakında burada")
        self.assertContains(response, 'name="csrf-token"')

    def test_unknown_url_uses_custom_404(self):
        response = self.client.get("/olmayan-sayfa/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
