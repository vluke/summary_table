from django.conf.urls.defaults import patterns

urlpatterns = patterns(
    'tardis.apps.summary_table.views',
    (r'^(?P<experiment_id>\d+)/$', 'index'),
    )

