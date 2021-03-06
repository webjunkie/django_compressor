from __future__ import with_statement
import os
import re

from BeautifulSoup import BeautifulSoup

from django.core.cache.backends import locmem
from django.test import TestCase

from compressor.base import SOURCE_HUNK, SOURCE_FILE
from compressor.conf import settings
from compressor.css import CssCompressor
from compressor.js import JsCompressor


def css_tag(href, **kwargs):
    rendered_attrs = ''.join(['%s="%s" ' % (k, v) for k, v in kwargs.items()])
    template = u'<link rel="stylesheet" href="%s" type="text/css" %s/>'
    return template % (href, rendered_attrs)


test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class CompressorTestCase(TestCase):

    def setUp(self):
        settings.COMPRESS_ENABLED = True
        settings.COMPRESS_PRECOMPILERS = {}
        settings.COMPRESS_DEBUG_TOGGLE = 'nocompress'
        self.css = """\
<link rel="stylesheet" href="/media/css/one.css" type="text/css" />
<style type="text/css">p { border:5px solid green;}</style>
<link rel="stylesheet" href="/media/css/two.css" type="text/css" />"""
        self.css_node = CssCompressor(self.css)

        self.js = """\
<script src="/media/js/one.js" type="text/javascript"></script>
<script type="text/javascript">obj.value = "value";</script>"""
        self.js_node = JsCompressor(self.js)

    def test_css_split(self):
        out = [
            (SOURCE_FILE, os.path.join(settings.COMPRESS_ROOT, u'css/one.css'), u'css/one.css', u'<link rel="stylesheet" href="/media/css/one.css" type="text/css" />'),
            (SOURCE_HUNK, u'p { border:5px solid green;}', None, u'<style type="text/css">p { border:5px solid green;}</style>'),
            (SOURCE_FILE, os.path.join(settings.COMPRESS_ROOT, u'css/two.css'), u'css/two.css', u'<link rel="stylesheet" href="/media/css/two.css" type="text/css" />'),
        ]
        split = self.css_node.split_contents()
        split = [(x[0], x[1], x[2], self.css_node.parser.elem_str(x[3])) for x in split]
        self.assertEqual(out, split)

    def test_css_hunks(self):
        out = ['body { background:#990; }', u'p { border:5px solid green;}', 'body { color:#fff; }']
        hunks = [h for m, h in self.css_node.hunks()]
        self.assertEqual(out, hunks)

    def test_css_output(self):
        out = u'body { background:#990; }\np { border:5px solid green;}\nbody { color:#fff; }'
        hunks = '\n'.join([h for m, h in self.css_node.hunks()])
        self.assertEqual(out, hunks)

    def test_css_mtimes(self):
        is_date = re.compile(r'^\d{10}[\.\d]+$')
        for date in self.css_node.mtimes:
            self.assertTrue(is_date.match(str(float(date))),
                "mtimes is returning something that doesn't look like a date: %s" % date)

    def test_css_return_if_off(self):
        settings.COMPRESS_ENABLED = False
        self.assertEqual(self.css, self.css_node.output())

    def test_cachekey(self):
        is_cachekey = re.compile(r'\w{12}')
        self.assertTrue(is_cachekey.match(self.css_node.cachekey),
            "cachekey is returning something that doesn't look like r'\w{12}'")

    def test_css_return_if_on(self):
        output = css_tag('/media/CACHE/css/e41ba2cc6982.css')
        self.assertEqual(output, self.css_node.output().strip())

    def test_js_split(self):
        out = [
            (SOURCE_FILE, os.path.join(settings.COMPRESS_ROOT, u'js/one.js'), u'js/one.js', '<script src="/media/js/one.js" type="text/javascript"></script>'),
            (SOURCE_HUNK, u'obj.value = "value";', None, '<script type="text/javascript">obj.value = "value";</script>'),
        ]
        split = self.js_node.split_contents()
        split = [(x[0], x[1], x[2], self.js_node.parser.elem_str(x[3])) for x in split]
        self.assertEqual(out, split)

    def test_js_hunks(self):
        out = ['obj = {};', u'obj.value = "value";']
        hunks = [h for m, h in self.js_node.hunks()]
        self.assertEqual(out, hunks)

    def test_js_output(self):
        out = u'<script type="text/javascript" src="/media/CACHE/js/066cd253eada.js"></script>'
        self.assertEqual(out, self.js_node.output())

    def test_js_return_if_off(self):
        try:
            enabled = settings.COMPRESS_ENABLED
            precompilers = settings.COMPRESS_PRECOMPILERS
            settings.COMPRESS_ENABLED = False
            settings.COMPRESS_PRECOMPILERS = {}
            self.assertEqual(self.js, self.js_node.output())
        finally:
            settings.COMPRESS_ENABLED = enabled
            settings.COMPRESS_PRECOMPILERS = precompilers

    def test_js_return_if_on(self):
        output = u'<script type="text/javascript" src="/media/CACHE/js/066cd253eada.js"></script>'
        self.assertEqual(output, self.js_node.output())

    def test_custom_output_dir(self):
        try:
            old_output_dir = settings.COMPRESS_OUTPUT_DIR
            settings.COMPRESS_OUTPUT_DIR = 'custom'
            output = u'<script type="text/javascript" src="/media/custom/js/066cd253eada.js"></script>'
            self.assertEqual(output, JsCompressor(self.js).output())
            settings.COMPRESS_OUTPUT_DIR = ''
            output = u'<script type="text/javascript" src="/media/js/066cd253eada.js"></script>'
            self.assertEqual(output, JsCompressor(self.js).output())
            settings.COMPRESS_OUTPUT_DIR = '/custom/nested/'
            output = u'<script type="text/javascript" src="/media/custom/nested/js/066cd253eada.js"></script>'
            self.assertEqual(output, JsCompressor(self.js).output())
        finally:
            settings.COMPRESS_OUTPUT_DIR = old_output_dir


class CssMediaTestCase(TestCase):
    def setUp(self):
        self.css = """\
<link rel="stylesheet" href="/media/css/one.css" type="text/css" media="screen">
<style type="text/css" media="print">p { border:5px solid green;}</style>
<link rel="stylesheet" href="/media/css/two.css" type="text/css" media="all">
<style type="text/css">h1 { border:5px solid green;}</style>"""
        self.css_node = CssCompressor(self.css)

    def test_css_output(self):
        links = BeautifulSoup(self.css_node.output()).findAll('link')
        media = [u'screen', u'print', u'all', None]
        self.assertEqual(len(links), 4)
        self.assertEqual(media, [l.get('media', None) for l in links])

    def test_avoid_reordering_css(self):
        css = self.css + '<style type="text/css" media="print">p { border:10px solid red;}</style>'
        node = CssCompressor(css)
        media = [u'screen', u'print', u'all', None, u'print']
        links = BeautifulSoup(node.output()).findAll('link')
        self.assertEqual(media, [l.get('media', None) for l in links])


class VerboseTestCase(CompressorTestCase):

    def setUp(self):
        super(VerboseTestCase, self).setUp()
        settings.COMPRESS_VERBOSE = True


class CacheBackendTestCase(CompressorTestCase):

    def test_correct_backend(self):
        from compressor.cache import cache
        self.assertEqual(cache.__class__, locmem.CacheClass)
