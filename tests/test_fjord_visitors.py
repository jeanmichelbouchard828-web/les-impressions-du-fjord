import unittest
from unittest.mock import patch
import fjord_visitors as v


class VisitorStatisticsTests(unittest.TestCase):
    def test_validation_never_exposes_identifiers(self):
        data={"total":42,"online":3,"window_minutes":5,"ip":"secret","token":"secret"}
        self.assertEqual(v._validate_stats(data),{"total":42,"online":3,"window_minutes":5})

    def test_rejects_inconsistent_counts(self):
        for data in (
            {"total":1,"online":2,"window_minutes":5},
            {"total":1,"online":-1,"window_minutes":5},
            {"total":"1","online":0,"window_minutes":5},
            {"total":True,"online":0,"window_minutes":5},
        ):
            self.assertIsNone(v._validate_stats(data))

    def test_preview_uses_only_remote_aggregates(self):
        with patch.dict("os.environ", {"FJORD_PREVIEW_MODE":"1"}):
            with patch.object(v,"remote_stats",return_value={"total":8,"online":2,"window_minutes":5}):
                self.assertEqual(v.site_stats(lambda: self.fail("database access forbidden"))["total"],8)


if __name__=="__main__":
    unittest.main()
