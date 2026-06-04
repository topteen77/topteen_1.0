"""Tests for vocational career recommendations lookup."""

from unittest.mock import patch

from django.test import TestCase

from app.vocational_recommendations import (
    below_area_vocational_urls,
    normalize_reasoning_area_code,
    vocational_cards_for_below_areas,
    vocational_guidance_cards_for_below_areas,
    vocational_guidance_grouped_for_below_areas,
)
from careers.models import Career, CareerCluster, VocationalCareerReasoningMapping
from core import choices


class VocationalRecommendationsTest(TestCase):
    def setUp(self):
        self.cluster = CareerCluster.objects.create(
            name='Vocational',
            slug='vocational',
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.cluster_patcher = patch(
            'careers.vocational_cluster.vocational_career_cluster_id',
            return_value=self.cluster.id,
        )
        self.cluster_patcher.start()
        self.career = Career.objects.create(
            name='Test Communication Career',
            slug='test-communication-career',
            publish_status=choices.PublishStatus.PUBLISHED,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        self.career.career_cluster.add(self.cluster)
        VocationalCareerReasoningMapping.objects.create(
            career=self.career,
            reasoning_area='VERBAL',
            priority=1,
            object_status=choices.ObjectStatus.ACTIVE,
        )

    def tearDown(self):
        self.cluster_patcher.stop()

    def test_returns_all_mapped_careers_for_below_area(self):
        other = Career.objects.create(
            name='Other Verbal Career',
            slug='other-verbal-career',
            publish_status=choices.PublishStatus.PUBLISHED,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        other.career_cluster.add(self.cluster)
        VocationalCareerReasoningMapping.objects.create(
            career=other,
            reasoning_area='VERBAL',
            priority=2,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        cards = vocational_guidance_cards_for_below_areas(['VERBAL', 'LOGICAL'])
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]['reasoning_area'], 'VERBAL')
        self.assertEqual(cards[0]['career'].pk, self.career.pk)
        self.assertEqual(cards[1]['career'].pk, other.pk)
        self.assertIn('reasoning_area=VERBAL', cards[0]['reasoning_area_careers_url'])
        self.assertIn('mapped=1', cards[0]['reasoning_area_careers_url'])
        self.assertIn(f'/careers/cluster/vocational-{self.cluster.id}/', cards[0]['reasoning_area_careers_url'])

    def test_grouped_listing_by_reasoning_area(self):
        logical = Career.objects.create(
            name='Logical Career',
            slug='logical-career',
            publish_status=choices.PublishStatus.PUBLISHED,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        logical.career_cluster.add(self.cluster)
        VocationalCareerReasoningMapping.objects.create(
            career=logical,
            reasoning_area='LOGICAL',
            priority=1,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        groups = vocational_guidance_grouped_for_below_areas(['VERBAL', 'LOGICAL'])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['reasoning_area_label'], 'Verbal')
        self.assertEqual(len(groups[0]['careers']), 1)
        self.assertEqual(groups[0]['careers'][0]['name'], self.career.name)
        self.assertEqual(groups[1]['reasoning_area_label'], 'Logical')
        self.assertEqual(groups[1]['careers'][0]['name'], 'Logical Career')

    def test_alias_matches_full_listing(self):
        cards = vocational_cards_for_below_areas(['VERBAL'])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['career'].pk, self.career.pk)

    def test_empty_when_no_below_areas(self):
        self.assertEqual(vocational_cards_for_below_areas([]), [])
        self.assertEqual(vocational_cards_for_below_areas(None), [])

    def test_respects_priority(self):
        other = Career.objects.create(
            name='Other Verbal Career',
            slug='other-verbal-career-priority',
            publish_status=choices.PublishStatus.PUBLISHED,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        other.career_cluster.add(self.cluster)
        VocationalCareerReasoningMapping.objects.create(
            career=other,
            reasoning_area='VERBAL',
            priority=2,
            object_status=choices.ObjectStatus.ACTIVE,
        )
        cards = vocational_guidance_cards_for_below_areas(['VERBAL'])
        self.assertEqual(cards[0]['career'].pk, self.career.pk)

    def test_below_area_urls_point_to_vocational_cluster(self):
        urls = below_area_vocational_urls(['VERBAL'])
        self.assertIn('reasoning_area=VERBAL', urls['VERBAL'])
        self.assertIn('mapped=1', urls['VERBAL'])
        self.assertIn(f'/careers/cluster/vocational-{self.cluster.id}/', urls['VERBAL'])

    def test_normalize_reasoning_area_code(self):
        self.assertEqual(normalize_reasoning_area_code('verbal'), 'VERBAL')
        self.assertIsNone(normalize_reasoning_area_code('EMOTIONAL'))
