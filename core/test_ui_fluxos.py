"""RUN_BROWSER_TESTS=1 habilita os testes reais com Playwright/Chromium."""
import os
from concurrent.futures import ThreadPoolExecutor
from django.db import connections
from datetime import datetime, time, timedelta
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from .models import Atividade


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Requer RUN_BROWSER_TESTS=1 e requirements-dev.txt")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FluxosNavegadorTests(StaticLiveServerTestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright
        self.usuario = get_user_model().objects.create_user(username="teste_browser")
        self.client.force_login(self.usuario)
        self.db_pool = ThreadPoolExecutor(max_workers=1)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(channel="chromium", headless=True)
        self.context = self.browser.new_context(viewport={"width":1280,"height":900})
        self.context.add_cookies([{"name":"sessionid", "value":self.client.cookies["sessionid"].value, "url":self.live_server_url}])
        self.page = self.context.new_page()
        self.dia = timezone.localdate() + timedelta(days=10)

    def db(self, operation):
        return self.db_pool.submit(operation).result()

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()
        self.db(connections.close_all)
        self.db_pool.shutdown()

    def test_quatro_checkboxes_individuais_e_filtros_apos_mudar_data(self):
        from playwright.sync_api import expect
        self.db(lambda: Atividade.objects.bulk_create([Atividade(usuario_id=self.usuario.id, titulo=f"UI Lista {i:02d}", tipo="lista", prazo=timezone.make_aware(datetime.combine(self.dia,time(13)))) for i in range(25)]))
        self.page.goto(self.live_server_url + "/tarefas/?busca=UI&tipo=lista&ordem=titulo&page=1")
        boxes = self.page.locator('input[name="atividades"]')
        expect(boxes).to_have_count(20)
        for i in range(4):
            boxes.nth(i).check()
        expect(self.page.locator('#quantidade-selecionadas')).to_have_text("4 selecionadas")
        assert self.page.locator('#selecionar-todas').evaluate('(el) => el.indeterminate')
        self.page.select_option('#lote select[name="acao"]', "adiar")
        novo = self.dia + timedelta(days=3)
        self.page.fill('#lote input[name="nova_data"]', novo.isoformat())
        self.page.get_by_role("button", name="Aplicar às selecionadas").click()
        self.page.wait_for_url("**/tarefas/?**")
        expect(self.page.locator('input[name="busca"]')).to_have_value("UI")
        expect(self.page.locator('select[name="tipo"]')).to_have_value("lista")
        expect(self.page.locator(".org-message")).to_contain_text("4 tarefa(s)")
        self.assertEqual(self.db(lambda: Atividade.objects.filter(prazo__date=novo).count()), 4)
        self.assertEqual(self.db(lambda: Atividade.objects.filter(prazo__date=self.dia).count()), 21)
        self.page.get_by_role("link", name="Próxima", exact=False).click()
        expect(self.page.locator('input[name="atividades"]')).to_have_count(5)

    def test_modal_cria_serie_com_inicio_e_termino(self):
        from playwright.sync_api import expect
        self.page.goto(self.live_server_url + "/tarefas/")
        self.page.get_by_role("link", name="+ Nova tarefa").click()
        expect(self.page.get_by_role("dialog")).to_be_visible()
        self.page.get_by_role("dialog").locator('[name="titulo"]').fill("UI Recorrente")
        self.page.get_by_role("dialog").locator('[name="tipo"]').select_option("lista")
        self.page.get_by_role("dialog").locator('[name="data_entrega"]').fill(self.dia.isoformat())
        self.page.get_by_role("dialog").locator('[name="horario"]').fill("13:00")
        self.page.get_by_role("dialog").locator('[name="horario_fim"]').fill("14:00")
        self.page.get_by_role("dialog").locator('[name="frequencia"]').select_option("diaria")
        self.page.get_by_role("dialog").locator('[name="repetir_ate"]').fill((self.dia+timedelta(days=2)).isoformat())
        self.page.get_by_role("button", name="Salvar tarefa", exact=False).click()
        expect(self.page.get_by_role("dialog")).to_have_count(0)
        self.assertEqual(self.db(lambda: Atividade.objects.filter(titulo="UI Recorrente").count()), 3)
        self.assertEqual(self.db(lambda: set(Atividade.objects.filter(titulo="UI Recorrente").values_list("duracao_estimada_min",flat=True))), {60})
        self.page.select_option('select[name="recorrencia"]', "sim")
        self.page.get_by_role("button", name="Filtrar", exact=True).click()
        expect(self.page.locator('input[name="atividades"]')).to_have_count(3)
