import unittest
from prepare_activation_window import streamed_text


class RecordedWindowTest(unittest.TestCase):
    def test_stream_channels_remain_separate_and_ordered(self):
        raw='\n'.join([
            'data: {"choices":[{"delta":{"reasoning_content":"reason "}}]}',
            'data: {"choices":[{"delta":{"reasoning_content":"continued"}}]}',
            'data: {"choices":[{"delta":{"content":"95 "}}]}',
            'data: {"choices":[{"delta":{"content":"million"}}]}',
            'data: [DONE]'])
        self.assertEqual(streamed_text(raw),('reason continued','95 million'))

    def test_missing_answer_is_not_a_capturable_failure(self):
        with self.assertRaisesRegex(ValueError,'No recorded assistant answer'):
            streamed_text('data: {"choices":[{"delta":{"reasoning_content":"unfinished"}}]}')
