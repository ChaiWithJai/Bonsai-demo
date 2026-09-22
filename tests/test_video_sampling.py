import math
import unittest
from workspace_data.vision import sample_times

class VideoSamplingTest(unittest.TestCase):
    def test_short_clip_covers_beginning_middle_and_end(self):
        times=sample_times(15)
        self.assertEqual(times,[0,7.375,14.75])
    def test_bounded_ordered_and_inside_duration(self):
        for duration in [.1,.5,1,8.445,30,299,300]:
            times=sample_times(duration)
            self.assertLessEqual(len(times),20)
            self.assertEqual(times,sorted(set(times)))
            self.assertEqual(times[0],0)
            self.assertTrue(all(0<=t<duration for t in times))
    def test_sparse_frames_stay_before_the_last_frame_end(self):
        self.assertEqual(sample_times(5,1),[0,2,4])
        self.assertEqual(sample_times(.5,1),[0])
    def test_invalid_durations(self):
        for duration in [0,-1,301,math.inf,math.nan]:
            with self.assertRaises(ValueError):sample_times(duration)
