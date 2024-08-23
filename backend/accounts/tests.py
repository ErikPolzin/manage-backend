from django.contrib.auth.models import User
from django.test import TestCase

from . import models


class TestProfileModel(TestCase):

    def test_profile_creation(self):
        user = User.objects.create(username="testuser")
        self.assertIsInstance(user.profile, models.UserProfile)
        old_id = user.profile.id
        # No new profile created
        user.save()
        self.assertEqual(old_id, user.profile.id)
