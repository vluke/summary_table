from django.conf.urls.defaults import patterns

urlpatterns = patterns(
    'tardis.apps.summary_table.views',
    (r'^(?P<experiment_id>\d+)/$', 'index'),
    (r'^(?P<experiment_id>\d+)/full_page$', 'full_page'),
    (r'^(?P<experiment_id>\d+)/table/$', 'table'),
    )

