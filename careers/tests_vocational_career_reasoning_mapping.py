"""Tests for VocationalCareerReasoningMapping upsert/reactivate behaviour."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from careers.models import Career, CareerCluster, VocationalCareerReasoningMapping
from core import choices


class VocationalCareerReasoningMappingSaveTest(TestCase):
    def setUp(self):
        self.cluster = CareerCluster.objects.create(
            name='Vocational',
            slug='vocational-test',
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.career = Career.objects.create(
            name='AI-ML Technician',
            slug='ai-ml-technician-test',
            publish_status=choices.PublishStatus.PUBLISHED,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.career.career_cluster.add(self.cluster)

    def test_reactivates_soft_deleted_mapping_on_add(self):
        deleted = VocationalCareerReasoningMapping.objects.create(
            career=self.career,
            reasoning_area='LOGICAL',
            priority=3,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        deleted_id = deleted.pk
        deleted.delete()

        replacement = VocationalCareerReasoningMapping(
            career=self.career,
            reasoning_area='LOGICAL',
            priority=1,
        )
        replacement.save()

        self.assertEqual(replacement.pk, deleted_id)
        reloaded = VocationalCareerReasoningMapping.objects.get(pk=deleted_id)
        self.assertEqual(reloaded.object_status, choices.ObjectStatus.ACTIVE)
        self.assertEqual(reloaded.priority, 1)
        self.assertEqual(
            VocationalCareerReasoningMapping.objects.complete().filter(
                career=self.career,
                reasoning_area='LOGICAL',
            ).count(),
            1,
        )

    def test_active_duplicate_raises_validation_error(self):
        VocationalCareerReasoningMapping.objects.create(
            career=self.career,
            reasoning_area='LOGICAL',
            priority=1,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        duplicate = VocationalCareerReasoningMapping(
            career=self.career,
            reasoning_area='LOGICAL',
            priority=2,
        )
        with self.assertRaises(ValidationError):
            duplicate.save()
