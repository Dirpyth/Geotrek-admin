import os
from unittest import mock
from shutil import rmtree
from tempfile import mkdtemp
from io import StringIO

from django.test import TestCase
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from django.template.exceptions import TemplateDoesNotExist

from geotrek.authent.factories import StructureFactory
from geotrek.trekking.models import Trek
from geotrek.common.models import Organism, FileType, Attachment
from geotrek.common.parsers import ExcelParser, AttachmentParserMixin, TourInSoftParser


class OrganismParser(ExcelParser):
    model = Organism
    fields = {'organism': 'nOm'}


class OrganismEidParser(ExcelParser):
    model = Organism
    fields = {'organism': 'nOm'}
    eid = 'organism'


class AttachmentParser(AttachmentParserMixin, OrganismEidParser):
    non_fields = {'attachments': 'photo'}


class ParserTests(TestCase):
    def test_bad_parser_class(self):
        with self.assertRaisesRegexp(CommandError, "Failed to import parser class 'DoesNotExist'"):
            call_command('import', 'geotrek.common.tests.test_parsers.DoesNotExist', '', verbosity=0)

    def test_bad_parser_file(self):
        with self.assertRaisesRegexp(CommandError, "Failed to import parser file 'geotrek/common.py'"):
            call_command('import', 'geotrek.common.DoesNotExist', '', verbosity=0)

    def test_no_filename_no_url(self):
        with self.assertRaisesRegexp(CommandError, "File path missing"):
            call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', '', verbosity=0)

    def test_bad_filename(self):
        with self.assertRaisesRegexp(CommandError, "File does not exists at: find_me/I_am_not_there.shp"):
            call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', 'find_me/I_am_not_there.shp', verbosity=0)

    def test_progress(self):
        output = StringIO()
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', filename, verbosity=2, stdout=output)
        self.assertIn('(100%)', output.getvalue())

    def test_create(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', filename, verbosity=0)
        self.assertEqual(Organism.objects.count(), 1)
        organism = Organism.objects.get()
        self.assertEqual(organism.organism, "Comité Théodule")

    def test_create_with_file_option(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'OrganismParser', filename, file='geotrek/common/tests/test_parsers.py', verbosity=0)
        self.assertEqual(Organism.objects.count(), 1)
        organism = Organism.objects.get()
        self.assertEqual(organism.organism, "Comité Théodule")

    def test_duplicate_without_eid(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', filename, verbosity=0)
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismParser', filename, verbosity=0)
        self.assertEqual(Organism.objects.count(), 2)

    def test_unmodified_with_eid(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismEidParser', filename, verbosity=0)
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismEidParser', filename, verbosity=0)
        self.assertEqual(Organism.objects.count(), 1)

    def test_updated_with_eid(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        filename2 = os.path.join(os.path.dirname(__file__), 'data', 'organism2.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismEidParser', filename, verbosity=0)
        call_command('import', 'geotrek.common.tests.test_parsers.OrganismEidParser', filename2, verbosity=0)
        self.assertEqual(Organism.objects.count(), 2)
        organisms = Organism.objects.order_by('pk')
        self.assertEqual(organisms[0].organism, "Comité Théodule")
        self.assertEqual(organisms[1].organism, "Comité Hippolyte")

    def test_report_format_text(self):
        parser = OrganismParser()
        self.assertRegex(parser.report(), '0/0 lines imported.')
        self.assertNotRegex(parser.report(), r'<div id=\"collapse-\$celery_id\" class=\"collapse\">')

    def test_report_format_html(self):
        parser = OrganismParser()
        self.assertRegex(parser.report(output_format='html'),
                         r'<div id=\"collapse-\$celery_id\" class=\"collapse\">')

    def test_report_format_bad(self):
        parser = OrganismParser()
        with self.assertRaises(TemplateDoesNotExist):
            parser.report(output_format='toto')


@override_settings(MEDIA_ROOT=mkdtemp('geotrek_test'))
class AttachmentParserTests(TestCase):
    def setUp(self):
        self.filetype = FileType.objects.create(type="Photographie")

    def tearDown(self):
        if os.path.exists(settings.MEDIA_ROOT):
            rmtree(settings.MEDIA_ROOT)

    @mock.patch('requests.get')
    def test_attachment(self, mocked):
        mocked.return_value.status_code = 200
        mocked.return_value.content = ''
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.AttachmentParser', filename, verbosity=0)
        organism = Organism.objects.get()
        attachment = Attachment.objects.get()
        self.assertEqual(attachment.content_object, organism)
        self.assertEqual(attachment.attachment_file.name, 'paperclip/common_organism/{pk}/titi.png'.format(pk=organism.pk))
        self.assertEqual(attachment.filetype, self.filetype)
        self.assertTrue(os.path.exists(attachment.attachment_file.path), True)

    @mock.patch('requests.get')
    def test_attachment_with_other_filetype_with_structure(self, mocked):
        """
        It will always take the one without structure first
        """
        structure = StructureFactory.create(name="Structure")
        FileType.objects.create(type="Photographie", structure=structure)
        mocked.return_value.status_code = 200
        mocked.return_value.content = ''
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.AttachmentParser', filename, verbosity=0)
        organism = Organism.objects.get()
        attachment = Attachment.objects.get()
        self.assertEqual(attachment.content_object, organism)
        self.assertEqual(attachment.attachment_file.name, 'paperclip/common_organism/{pk}/titi.png'.format(pk=organism.pk))
        self.assertEqual(attachment.filetype, self.filetype)
        self.assertEqual(attachment.filetype.structure, None)
        self.assertTrue(os.path.exists(attachment.attachment_file.path), True)

    @mock.patch('requests.get')
    def test_attachment_with_no_filetype_photographie(self, mocked):
        self.filetype.delete()
        mocked.return_value.status_code = 200
        mocked.return_value.content = ''
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        with self.assertRaisesRegexp(CommandError, "FileType 'Photographie' does not exists in Geotrek-Admin. Please add it"):
            call_command('import', 'geotrek.common.tests.test_parsers.AttachmentParser', filename, verbosity=0)

    @mock.patch('requests.get')
    @mock.patch('requests.head')
    def test_attachment_not_updated(self, mocked_head, mocked_get):
        mocked_get.return_value.status_code = 200
        mocked_get.return_value.content = ''
        mocked_head.return_value.headers = {'content-length': 0}
        filename = os.path.join(os.path.dirname(__file__), 'data', 'organism.xls')
        call_command('import', 'geotrek.common.tests.test_parsers.AttachmentParser', filename, verbosity=0)
        call_command('import', 'geotrek.common.tests.test_parsers.AttachmentParser', filename, verbosity=0)
        self.assertEqual(mocked_get.call_count, 1)
        self.assertEqual(Attachment.objects.count(), 1)


class TourInSoftParserTests(TestCase):

    def test_attachment(self):
        class TestTourParser(TourInSoftParser):
            separator = '##'
            separator2 = '||'

            def __init__(self):
                self.model = Trek
                super(TestTourParser, self).__init__()

        parser = TestTourParser()
        result = parser.filter_attachments('', 'a||b||c##||||##d||e||f')
        self.assertListEqual(result, [['a', 'b', 'c'], ['d', 'e', 'f']])
