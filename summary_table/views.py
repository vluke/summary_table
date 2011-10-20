# -*- coding: utf-8 -*-

from django.http import HttpResponse
from django.template import Context
from django.shortcuts import render_to_response, redirect
from django.views.decorators.cache import never_cache

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.creativecommonshandler import CreativeCommonsHandler
from tardis.tardis_portal.models import Experiment, DatafileParameter, ParameterName, Dataset_File
from tardis.tardis_portal.shortcuts import render_response_index

import logging
logger = logging.getLogger(__name__)


@never_cache
@authz.experiment_access_required
def index(request, experiment_id):
    url = 'summary_table/index.html'
    c = Context()
    experiment = Experiment.objects.get(pk=experiment_id)

    parameter_names = ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment).distinct()
    datafiles = Dataset_File.objects.filter(dataset__experiment=experiment)

    grid = []
    for df in datafiles:
        row = []
        row.append(df.filename)
        for pn in parameter_names:
            params = DatafileParameter.objects.filter(parameterset__dataset_file=df, name=pn)
            row.append(','.join([param.get() for param in params]))
        grid.append(row)

    c['parameter_names'] = parameter_names
    c['grid'] = grid

    return HttpResponse(render_response_index(request, url, c))
