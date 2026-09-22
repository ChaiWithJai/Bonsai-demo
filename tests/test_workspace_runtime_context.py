import unittest
from workspace_runtime import context_capacity, server_command, model_server


class RuntimeContextTest(unittest.TestCase):
    def test_default_and_candidate_use_explicit_single_slot_capacity(self):
        for config, expected in [({'alias':'bonsai'},16384),({'alias':'bonsai','context':32768},32768)]:
            command=server_command(config,'/runtime/llama-server','/models/bonsai.gguf',12345)
            self.assertEqual(command[command.index('-c')+1],str(expected))
            self.assertEqual(context_capacity(config),expected)
            self.assertEqual(command[command.index('-np')+1],'1')
            self.assertEqual(command[command.index('--reasoning-budget')+1],'0')

    def test_invalid_capacity_fails_before_files_or_gpu_queue_are_touched(self):
        for value in (0,-1,True,None,'32768',32768.0,4095,262145):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'Workspace context'):
                with model_server({'context':value},'/nonexistent-output'):
                    self.fail('Invalid context reached a server')
