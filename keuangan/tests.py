from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Kabupaten, Kecamatan, Kios, Armada, JenisPupuk
from gudang.models import Distribution
from keuangan.models import Invoice, Payment


class InvoiceListProofButtonTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username='owner',
            email='owner@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)

        self.kab = Kabupaten.objects.create(name='Semarang', code='SMG')
        self.kec = Kecamatan.objects.create(name='Ungaran', code='UNG', kabupaten=self.kab)
        self.kios = Kios.objects.create(
            name='Kios Maju',
            pic_name='Pak Tono',
            kecamatan=self.kec,
            address='Jl. Merdeka 1',
            phone='08123',
        )
        self.armada = Armada.objects.create(
            plate_number='H-9988-AB',
            vehicle_type='Engkel',
            driver_name='Supir Test',
        )
        self.jenis = JenisPupuk.objects.create(name='NPK', code='NPK')

        self.distribution = Distribution.objects.create(
            date=date(2026, 4, 1),
            pkp_date=date(2026, 4, 1),
            kios=self.kios,
            armada=self.armada,
            source_type='PHYSICAL',
            jenis_pupuk=self.jenis,
            tonnage=1,
        )
        self.invoice = Invoice.objects.create(
            distribution=self.distribution,
            inv_number='INV/TEST/001',
            issue_date=date(2026, 4, 1),
            due_date=date(2026, 4, 30),
            total_amount=1000000,
            total_paid=0,
            status='UNPAID',
        )

    def test_invoice_and_history_show_proof_buttons(self):
        Payment.objects.create(
            invoice=self.invoice,
            date=date(2026, 4, 2),
            amount=250000,
            method='Transfer',
            proof='keuangan/payment/test-proof.jpg',
        )

        response = self.client.get(reverse('invoice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="Lihat Bukti Pembayaran"', count=1)
        self.assertContains(response, 'title="Lihat Bukti"', count=1)
        self.assertContains(response, '/media/keuangan/payment/test-proof.jpg', count=2)

    def test_invoice_without_proof_hides_proof_buttons(self):
        Payment.objects.create(
            invoice=self.invoice,
            date=date(2026, 4, 2),
            amount=250000,
            method='Transfer',
        )

        response = self.client.get(reverse('invoice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Lihat Bukti')
