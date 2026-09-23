import unittest
from unittest.mock import patch
from gb10_vision_mcp import dispatch, capture

class CameraTests(unittest.TestCase):
    def test_discovery_does_not_capture(self):
        with patch('gb10_vision_mcp.capture') as cap:
            result=dispatch({'jsonrpc':'2.0','id':1,'method':'tools/list'})
            self.assertEqual(len(result['result']['tools']),3)
            cap.assert_not_called()
    def test_path_injection_rejected(self):
        for device in ['/dev/video0;echo x','/tmp/x','../video0']:
            with self.assertRaises(ValueError): capture(device,'/tmp/no-write')
    def test_unknown_arguments_rejected(self):
        result=dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'capture_frame','arguments':{'device':'/dev/video0','continuous':True}}})
        self.assertTrue(result['result']['isError'])
