from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from foodsaving.tests.utils import ExtractPaginationMixin

from foodsaving.groups.factories import GroupFactory
from foodsaving.groups.models import GroupMembership
from foodsaving.pickups.factories import PickupDateFactory, \
    PickupDateSeriesFactory
from foodsaving.pickups.models import PickupDate
from foodsaving.places.factories import PlaceFactory
from foodsaving.users.factories import UserFactory

history_url = '/api/history/'


class TestHistoryAPICreateGroup(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()

    def test_create_group(self):
        self.client.force_login(self.member)
        self.client.post('/api/groups/', {'name': 'xyzabc', 'timezone': 'Europe/Berlin'})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'GROUP_CREATE')


class TestHistoryAPIOrdering(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()

    def test_ordering(self):
        self.client.force_login(self.member)
        self.client.post('/api/groups/', {'name': 'Group 1', 'timezone': 'Europe/Berlin'})
        self.client.post('/api/groups/', {'name': 'Group 2', 'timezone': 'Europe/Berlin'})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['payload']['name'], 'Group 2')


class TestHistoryAPIWithExistingGroup(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member], is_open=True)
        self.group_url = '/api/groups/{}/'.format(self.group.id)

    def test_modify_group(self):
        self.client.force_login(self.member)
        self.client.patch(self.group_url, {'name': 'something new'})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'GROUP_MODIFY')
        self.assertEqual(response.data[0]['payload']['name'], 'something new')

    def test_dont_modify_group(self):
        self.client.force_login(self.member)
        self.client.patch(self.group_url, {'name': self.group.name})
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 0)

    def test_join_group(self):
        user = UserFactory()
        self.client.force_login(user)
        self.client.post(self.group_url + 'join/')
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'GROUP_JOIN')

    def test_leave_group(self):
        user = UserFactory()
        GroupMembership.objects.create(group=self.group, user=user)
        self.client.force_login(user)
        self.client.post(self.group_url + 'leave/')

        self.client.force_login(self.member)
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'GROUP_LEAVE')

    def test_member_becomes_editor(self):
        user = UserFactory()
        GroupMembership.objects.create(group=self.group, user=user)
        url = reverse('group-trust-user', args=(self.group.id, user.id))
        self.client.force_login(self.member)

        self.client.post(url)

        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'MEMBER_BECAME_EDITOR')

    def test_create_place(self):
        self.client.force_login(self.member)
        self.client.post('/api/places/', {'name': 'xyzabc', 'group': self.group.id})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'STORE_CREATE')


class TestHistoryAPIWithExistingPlace(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group)
        self.place_url = '/api/places/{}/'.format(self.place.id)

    def test_modify_place(self):
        self.client.force_login(self.member)
        self.client.patch(
            self.place_url,
            {
                'name': 'newnew',  # new value
                'description': self.place.description  # no change
            }
        )
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 1, response.data)
        self.assertEqual(response.data[0]['typus'], 'STORE_MODIFY')
        self.assertEqual(response.data[0]['payload']['name'], 'newnew')
        self.assertEqual(len(response.data[0]['payload']), 1)

    def test_dont_modify_place(self):
        self.client.force_login(self.member)
        self.client.patch(self.place_url, {'name': self.place.name})
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 0)

    def test_create_pickup(self):
        self.client.force_login(self.member)
        self.client.post(
            '/api/pickup-dates/',
            {
                'date': timezone.now() + relativedelta(days=1),
                'place': self.place.id
            }
        )
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_CREATE')

    def test_create_series(self):
        self.client.force_login(self.member)
        self.client.post(
            '/api/pickup-date-series/',
            {
                'start_date': timezone.now(),
                'rule': 'FREQ=WEEKLY',
                'place': self.place.id
            }
        )
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'SERIES_CREATE')


class TestHistoryAPIWithExistingPickups(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group)
        self.pickup = PickupDateFactory(place=self.place)
        self.pickup_url = '/api/pickup-dates/{}/'.format(self.pickup.id)
        self.series = PickupDateSeriesFactory(place=self.place)
        self.series_url = '/api/pickup-date-series/{}/'.format(self.series.id)

    def test_modify_pickup(self):
        self.client.force_login(self.member)
        self.client.patch(self.pickup_url, {'max_collectors': '11'})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_MODIFY')
        self.assertEqual(response.data[0]['payload']['max_collectors'], '11')

    def test_dont_modify_pickup(self):
        self.client.force_login(self.member)
        self.client.patch(self.pickup_url, {'date': self.pickup.date})
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 0)

    def test_delete_pickup(self):
        self.client.force_login(self.member)
        self.client.delete(self.pickup_url)
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_DELETE')

    def test_modify_series(self):
        self.client.force_login(self.member)
        self.client.patch(self.series_url, {'max_collectors': '11'})
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'SERIES_MODIFY')
        self.assertEqual(response.data[0]['payload']['max_collectors'], '11')

    def test_dont_modify_series(self):
        self.client.force_login(self.member)
        self.client.patch(self.series_url, {'rule': self.series.rule})
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 0)

    def test_delete_series(self):
        self.client.force_login(self.member)
        self.client.delete(self.series_url)
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'SERIES_DELETE')
        self.assertEqual(response.data[0]['payload']['rule'], self.series.rule)

    def test_join_pickup(self):
        self.client.force_login(self.member)
        self.client.post(self.pickup_url + 'add/')
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_JOIN')
        self.assertEqual(parse(response.data[0]['payload']['date']), self.pickup.date)

    def test_leave_pickup(self):
        self.client.force_login(self.member)
        self.pickup.add_collector(self.member)
        self.client.post(self.pickup_url + 'remove/')
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_LEAVE')
        self.assertEqual(parse(response.data[0]['payload']['date']), self.pickup.date)


class TestHistoryAPIWithDonePickup(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group)
        self.pickup = PickupDateFactory(place=self.place, date=timezone.now() - relativedelta(days=1))
        self.pickup.add_collector(self.member)
        PickupDate.objects.process_finished_pickup_dates()

    def test_pickup_done(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_DONE')
        self.assertLess(parse(response.data[0]['date']), timezone.now() - relativedelta(hours=22))

    def test_filter_pickup_done(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url, {'typus': 'PICKUP_DONE'})
        self.assertEqual(response.data[0]['typus'], 'PICKUP_DONE')
        response = self.get_results(history_url, {'typus': 'GROUP_JOIN'})  # unrelated event should give no result
        self.assertEqual(len(response.data), 0)


class TestHistoryAPIWithMissedPickup(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group)
        self.pickup = PickupDateFactory(place=self.place, date=timezone.now() - relativedelta(days=1))
        # No one joined the pickup
        PickupDate.objects.process_finished_pickup_dates()

    def test_pickup_missed(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url)
        self.assertEqual(response.data[0]['typus'], 'PICKUP_MISSED')
        self.assertLess(parse(response.data[0]['date']), timezone.now() - relativedelta(hours=22))

    def test_filter_pickup_missed(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url, {'typus': 'PICKUP_MISSED'})
        self.assertEqual(response.data[0]['typus'], 'PICKUP_MISSED')
        response = self.get_results(history_url, {'typus': 'GROUP_JOIN'})  # unrelated event should give no result
        self.assertEqual(len(response.data), 0)


class TestHistoryAPIPickupForInactivePlace(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group, status='archived')
        self.pickup = PickupDateFactory(place=self.place, date=timezone.now() - relativedelta(days=1))
        self.pickup.add_collector(self.member)

        PickupDateFactory(place=self.place, date=timezone.now() - relativedelta(days=1))
        PickupDate.objects.process_finished_pickup_dates()

    def test_no_pickup_done_for_inactive_place(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url, {'typus': 'PICKUP_DONE'})
        self.assertEqual(len(response.data), 0)

    def test_no_pickup_missed_for_inactive_place(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url, {'typus': 'PICKUP_MISSED'})
        self.assertEqual(len(response.data), 0)


class TestHistoryAPIWithDeletedPickup(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()
        self.group = GroupFactory(members=[self.member])
        self.place = PlaceFactory(group=self.group)
        self.pickup = PickupDateFactory(
            place=self.place,
            date=timezone.now() - relativedelta(days=1),
            deleted=True,
        )
        PickupDate.objects.process_finished_pickup_dates()

    def test_no_history_for_deleted_pickup(self):
        self.client.force_login(self.member)
        response = self.get_results(history_url)
        self.assertEqual(len(response.data), 0)


class TestHistoryAPIDateFiltering(APITestCase, ExtractPaginationMixin):
    def setUp(self):
        self.member = UserFactory()

    def test_filter_by_date(self):
        self.client.force_login(self.member)
        self.client.post('/api/groups/', {'name': 'xyzabc', 'timezone': 'Europe/Berlin'})
        response = self.get_results(history_url, data={'date_max': timezone.now()})
        self.assertEqual(len(response.data), 1)
        response = self.get_results(history_url, data={'date_min': timezone.now()})
        self.assertEqual(len(response.data), 0)
