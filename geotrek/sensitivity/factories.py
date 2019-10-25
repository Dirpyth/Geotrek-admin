# -*- coding: utf-8 -*-

import factory

from django.contrib.auth.models import Permission

from geotrek.authent.factories import StructureRelatedDefaultFactory
from geotrek.common.utils.testdata import dummy_filefield_as_sequence

from . import models

from mapentity.factories import UserFactory


class SportPracticeFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SportPractice

    name = factory.Sequence(lambda n: "Practice %s" % n)


class SpeciesFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Species

    name = factory.Sequence(lambda n: "Species %s" % n)
    pictogram = dummy_filefield_as_sequence('species-%s.png')
    url = factory.Sequence(lambda n: "http://url%s.com" % n)
    period06 = True
    period07 = True
    category = models.Species.SPECIES

    @factory.post_generation
    def practices(obj, create, extracted=None, **kwargs):
        if create:
            if not extracted:
                practices = [SportPracticeFactory.create(), SportPracticeFactory.create()]
            for practice in practices:
                obj.practices.add(practice)


class RegulatorySpeciesFactory(SpeciesFactory):
    category = models.Species.REGULATORY


class SensitiveAreaFactory(StructureRelatedDefaultFactory):
    class Meta:
        model = models.SensitiveArea

    species = factory.SubFactory(SpeciesFactory)
    geom = 'POLYGON((700000 6600000, 700000 6600003, 700003 6600003, 700003 6600000, 700000 6600000))'
    published = True
    description = "Blabla"
    contact = "<a href=\"mailto:toto@tata.com\">toto@tata.com</a>"


class RegulatorySensitiveAreaFactory(SensitiveAreaFactory):
    species = factory.SubFactory(RegulatorySpeciesFactory)


class BiodivManagerFactory(UserFactory):
    is_staff = True

    @factory.post_generation
    def create_biodiv_manager(obj, create, extracted, **kwargs):
        for perm in Permission.objects.exclude(codename='can_bypass_structure'):
            obj.user_permissions.add(perm)
