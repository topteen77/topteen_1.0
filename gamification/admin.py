from django.contrib import admin

from core.admin import (
    DashboardLevelBandAdmin,
    DashboardPointRuleAdmin,
    DashboardStreakConfigAdmin,
    DashboardTrophyDefinitionAdmin,
)
from gamification.models import (
    DashboardLevelBand,
    DashboardPointRule,
    DashboardStreakConfig,
    DashboardTrophyDefinition,
)

admin.site.register(DashboardLevelBand, DashboardLevelBandAdmin)
admin.site.register(DashboardPointRule, DashboardPointRuleAdmin)
admin.site.register(DashboardTrophyDefinition, DashboardTrophyDefinitionAdmin)
admin.site.register(DashboardStreakConfig, DashboardStreakConfigAdmin)
