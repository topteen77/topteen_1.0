from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from institute.utils import (
    _career_clusters_from_psychometric_scores,
    _finalize_heatmap_payload,
    aggregate_student_career_data,
    get_empty_heatmap_data,
)


class PsychometricHeatmapClusterTests(SimpleTestCase):
    def test_cluster_mapping_uses_dominant_riasec_score(self):
        clusters = _career_clusters_from_psychometric_scores(
            {
                "Realistic": 2,
                "Investigative": 8,
                "Artistic": 1,
                "Social": 4,
                "Enterprising": 3,
                "Conventional": 2,
            }
        )
        self.assertEqual(
            clusters,
            ["Healthcare & Biotech", "AI & Digital Tech", "Cybersecurity"],
        )

    def test_empty_scores_create_no_clusters(self):
        self.assertEqual(
            _career_clusters_from_psychometric_scores(
                {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}
            ),
            [],
        )

    def test_empty_payload_locks_heatmap(self):
        payload = get_empty_heatmap_data()
        self.assertFalse(payload["enabled"])
        self.assertIn("unlocks", payload["disabledMessage"])

    def test_payload_with_psychometric_cells_enables_heatmap(self):
        payload = _finalize_heatmap_payload(
            [
                {
                    "cluster": "Creative Arts",
                    "demographic": "Class 10",
                    "category": "Monitor",
                    "clarityGap": 10,
                }
            ]
        )
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["disabledMessage"], "")

    @staticmethod
    def _student():
        return SimpleNamespace(
            id=101,
            student=SimpleNamespace(id=1),
            student_id=1,
            institute=SimpleNamespace(id=1),
            class_and_section=SimpleNamespace(
                class_and_section="Class 10 A",
                stream="PCM",
            ),
        )

    @patch("institute.utils.TestCompletion.objects")
    @patch("institute.utils.Results.objects")
    def test_unattempted_student_is_excluded(self, results_objects, completion_objects):
        results_objects.filter.return_value.only.return_value = []
        completion_objects.filter.return_value.values_list.return_value = []

        payload = aggregate_student_career_data([self._student()])

        self.assertEqual(payload, [])

    @patch("institute.utils.TestCompletion.objects")
    @patch("institute.utils.Results.objects")
    def test_completed_student_clusters_do_not_come_from_stream(
        self, results_objects, completion_objects
    ):
        rows = [
            SimpleNamespace(
                id=1,
                user_id=1,
                test_paper="test1",
                scores={},
                results={"personality": 70},
            ),
            SimpleNamespace(
                id=2,
                user_id=1,
                test_paper="test2",
                scores={
                    "Realistic": 1,
                    "Investigative": 2,
                    "Artistic": 9,
                    "Social": 4,
                    "Enterprising": 3,
                    "Conventional": 2,
                },
                results={},
            ),
            SimpleNamespace(
                id=3,
                user_id=1,
                test_paper="test3",
                scores={"language": 6, "spatial": 8},
                results={},
            ),
        ]
        results_objects.filter.return_value.only.return_value = rows
        completion_objects.filter.return_value.values_list.return_value = [1]

        payload = aggregate_student_career_data([self._student()])
        clusters = {row["cluster"] for row in payload}

        self.assertEqual(
            clusters,
            {"Creative Arts", "Media & Communications", "Green Architecture"},
        )
        self.assertNotIn("Robotics & Automation", clusters)
        self.assertTrue(all(row["studentCount"] == 1 for row in payload))
