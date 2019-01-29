from django.test import TestCase
from django.utils import translation

from geotrek.infrastructure.models import Infrastructure
from geotrek.infrastructure.factories import InfrastructureFactory
from geotrek.signage.factories import SignageFactory
from geotrek.maintenance.models import Intervention
from geotrek.maintenance.factories import (InterventionFactory,
                                           InfrastructureInterventionFactory,
                                           InfrastructurePointInterventionFactory,
                                           SignageInterventionFactory,
                                           ProjectFactory, ManDayFactory)
from geotrek.core.factories import PathFactory, TopologyFactory, StakeFactory


class InterventionTest(TestCase):
    def test_topology_has_intervention_kind(self):
        topo = TopologyFactory.create()
        self.assertEqual('TOPOLOGY', topo.kind)
        i = InterventionFactory.create(topology=topo)
        self.assertEqual('INTERVENTION', i.topology.kind)

    def test_infrastructure(self):
        i = InterventionFactory.create()
        self.assertFalse(i.on_existing_topology)
        infra = InfrastructureFactory.create()
        i.set_topology(infra)
        self.assertTrue(i.on_existing_topology)
        sign = SignageFactory.create()
        i.set_topology(sign)
        self.assertTrue(i.on_existing_topology)

    def test_default_stake(self):
        i = InterventionFactory.create()
        i.stake = None
        self.assertTrue(i.stake is None)
        i.save()
        self.assertTrue(i.stake is None)

        lowstake = StakeFactory.create()
        highstake = StakeFactory.create()
        if lowstake > highstake:
            tmp = lowstake
            lowstake = highstake
            highstake = tmp

        # Add paths to topology
        infra = InfrastructureFactory.create(no_path=True)
        infra.add_path(PathFactory.create(stake=lowstake))
        infra.add_path(PathFactory.create(stake=highstake))
        infra.add_path(PathFactory.create(stake=lowstake))
        i.set_topology(infra)
        # Stake is not None anymore
        i.save()
        self.assertFalse(i.stake is None)
        # Make sure it took higher stake
        self.assertEqual(i.stake, highstake)

    def test_mandays(self):
        i = InterventionFactory.create()
        ManDayFactory.create(intervention=i, nb_days=5)
        ManDayFactory.create(intervention=i, nb_days=8)
        self.assertEqual(i.total_manday, 14)  # intervention haz a default manday

    def test_path_helpers(self):
        p = PathFactory.create()

        self.assertEqual(len(p.interventions), 0)
        self.assertEqual(len(p.projects), 0)

        sign = SignageFactory.create(no_path=True)
        sign.add_path(p, start=0.5, end=0.5)

        infra = InfrastructureFactory.create(no_path=True)
        infra.add_path(p)

        i1 = InterventionFactory.create()
        i1.set_topology(sign)
        i1.save()

        self.assertCountEqual(p.interventions, [i1])

        i2 = InterventionFactory.create()
        i2.set_topology(infra)
        i2.save()

        self.assertCountEqual(p.interventions, [i1, i2])

        proj = ProjectFactory.create()
        proj.interventions.add(i1)
        proj.interventions.add(i2)

        self.assertCountEqual(p.projects, [proj])

    def test_helpers(self):
        infra = InfrastructureFactory.create()
        sign = SignageFactory.create()
        interv = InterventionFactory.create()
        proj = ProjectFactory.create()

        self.assertFalse(interv.on_existing_topology)
        self.assertEqual(interv.infrastructure, None)

        interv.set_topology(infra)
        self.assertTrue(interv.on_existing_topology)
        self.assertFalse(interv.is_signage)
        self.assertTrue(interv.is_infrastructure)
        self.assertEqual(interv.signages, [])
        self.assertEqual(interv.infrastructures, [infra])
        self.assertEqual(interv.infrastructure, infra)

        interv.set_topology(sign)
        self.assertTrue(interv.on_existing_topology)
        self.assertTrue(interv.is_signage)
        self.assertFalse(interv.is_infrastructure)
        self.assertEqual(interv.signages, [sign])
        self.assertEqual(interv.infrastructures, [])
        self.assertEqual(interv.signage, sign)

        self.assertFalse(interv.in_project)
        interv.project = proj
        self.assertTrue(interv.in_project)

    def test_delete_topology(self):
        infra = InfrastructureFactory.create()
        interv = InterventionFactory.create()
        interv.set_topology(infra)
        interv.save()
        infra.delete()
        self.assertEqual(Infrastructure.objects.existing().count(), 0)
        self.assertEqual(Intervention.objects.existing().count(), 0)

    def test_denormalized_fields(self):
        infra = InfrastructureFactory.create()
        infra.save()
        self.assertNotEqual(infra.length, 0.0)

        # After setting related infrastructure
        interv = InterventionFactory.create()
        interv.set_topology(infra)
        interv.save()
        self.assertEqual(interv.length, infra.length)

        # After update related infrastructure
        infra.length = 3.14
        infra.save()
        interv.reload()
        self.assertEqual(interv.length, infra.length)

    def test_length_auto(self):
        # Line intervention has auto length from topology
        interv = InfrastructureInterventionFactory.create()
        interv.length = 3.14
        interv.save()
        self.assertNotEqual(interv.length, 3.14)
        # Point intervention has manual length
        interv = InfrastructurePointInterventionFactory.create()
        interv.length = 3.14
        interv.save()
        self.assertEqual(interv.length, 3.14)

    def test_area_auto(self):
        # Line
        interv = InfrastructureInterventionFactory.create(width=10.0)
        interv.reload()
        self.assertAlmostEqual(interv.area, interv.length * 10.0)

        # Points
        interv = InfrastructurePointInterventionFactory.create()
        interv.reload()
        self.assertEqual(interv.length, 0.0)
        self.assertEqual(interv.area, 0.0)

        interv = InfrastructurePointInterventionFactory.create(length=50, width=10.0)
        interv.reload()
        self.assertEqual(interv.area, 500)

        interv = InfrastructurePointInterventionFactory.create(width=0.5, length=0.5)
        interv.reload()
        self.assertEqual(interv.area, 0.25)

        interv = InfrastructurePointInterventionFactory.create(width=0.5)
        interv.reload()
        self.assertEqual(interv.area, 0.0)

    def test_infrastructure_display_is_path_by_default(self):
        translation.activate('en')
        on_path = InterventionFactory.create()
        self.assertIn(b'Path', on_path.infrastructure_display)
        self.assertIn(b'path-16.png', on_path.infrastructure_display)

    def test_infrastructure_display_shows_infrastructure_name(self):
        interv = InfrastructureInterventionFactory.create()
        self.assertIn(b'Infrastructure', interv.infrastructure_display)
        self.assertIn(b'infrastructure-16.png', interv.infrastructure_display)
        name = interv.infrastructure.name
        self.assertIn(name, interv.infrastructure_display)

        interv = SignageInterventionFactory.create()
        self.assertIn(b'Signage', interv.infrastructure_display)
        self.assertIn(b'signage-16.png', interv.infrastructure_display)
        name = interv.signage.name
        self.assertIn(name, interv.infrastructure_display)
