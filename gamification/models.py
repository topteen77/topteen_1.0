"""Proxy models so dashboard gamification settings appear under their own admin sidebar section."""

from core.models import (
    DashboardLevelBand as CoreDashboardLevelBand,
    DashboardPointRule as CoreDashboardPointRule,
    DashboardStreakConfig as CoreDashboardStreakConfig,
    DashboardTrophyDefinition as CoreDashboardTrophyDefinition,
)


class DashboardLevelBand(CoreDashboardLevelBand):
    class Meta:
        proxy = True
        verbose_name = 'Dashboard Level Band'
        verbose_name_plural = 'Dashboard Level Bands'


class DashboardPointRule(CoreDashboardPointRule):
    class Meta:
        proxy = True
        verbose_name = 'Dashboard Point Rule'
        verbose_name_plural = 'Dashboard Point Rules'


class DashboardTrophyDefinition(CoreDashboardTrophyDefinition):
    class Meta:
        proxy = True
        verbose_name = 'Dashboard Trophy Definition'
        verbose_name_plural = 'Dashboard Trophy Definitions'


class DashboardStreakConfig(CoreDashboardStreakConfig):
    class Meta:
        proxy = True
        verbose_name = 'Dashboard Streak Config'
        verbose_name_plural = 'Dashboard Streak Config'
