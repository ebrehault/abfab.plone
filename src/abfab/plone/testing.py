# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    applyProfile,
    FunctionalTesting,
    IntegrationTesting,
    PLONE_FIXTURE
    PloneSandboxLayer,
)
from plone.testing import z2

import abfab.plone


class AbfabPloneLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity
        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=abfab.plone)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'abfab.plone:default')


ABFAB_PLONE_FIXTURE = AbfabPloneLayer()


ABFAB_PLONE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(ABFAB_PLONE_FIXTURE,),
    name='AbfabPloneLayer:IntegrationTesting',
)


ABFAB_PLONE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(ABFAB_PLONE_FIXTURE,),
    name='AbfabPloneLayer:FunctionalTesting',
)


ABFAB_PLONE_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        ABFAB_PLONE_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name='AbfabPloneLayer:AcceptanceTesting',
)
