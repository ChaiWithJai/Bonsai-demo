import unittest
from svg_output import inspect_svg
from comparison_api import ComparisonAPI

class SvgOutputTest(unittest.TestCase):
    def test_fenced_svg_preserved(self):
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="20"/></svg>'
        result=inspect_svg('```svg\n'+svg+'\n```')
        self.assertTrue(result['valid']);self.assertEqual(result['source'],svg)
    def test_incomplete_or_active_content_rejected(self):
        for body in ['<svg>', '<!DOCTYPE svg><svg/>', '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.com/a.svg"/></svg>', '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', '<svg xmlns="http://www.w3.org/2000/svg"><style>@import "https://example.com/a";</style></svg>']:
            self.assertFalse(inspect_svg(body)['valid'])
    def test_pelican_budget_and_native_prompt(self):
        prompt='Generate an SVG of a pelican riding a bicycle'
        options=ComparisonAPI.validate({'prompt':prompt,'task':'pelican_svg','max_tokens':4096})
        request=ComparisonAPI._request('bonsai',options)
        self.assertEqual(request['messages'],[{'role':'user','content':prompt}]);self.assertNotIn('tools',request)
        with self.assertRaises(ValueError):ComparisonAPI.validate({'prompt':prompt,'task':'text','max_tokens':4096})
        with self.assertRaises(ValueError):ComparisonAPI.validate({'prompt':prompt,'task':'pelican_svg','max_tokens':4097})
