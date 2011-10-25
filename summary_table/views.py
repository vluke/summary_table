# -*- coding: utf-8 -*-

from django.db.models import Q
from django.http import HttpResponse
from django.template import Context
from django.shortcuts import render_to_response, redirect
from django.views.decorators.cache import never_cache

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.creativecommonshandler import CreativeCommonsHandler
from tardis.tardis_portal.models import Experiment, DatafileParameter, ParameterName, Dataset_File
from tardis.tardis_portal.shortcuts import render_response_index

import json

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

    c['parameter_names'] = parameter_names
    c['experiment'] = experiment

    return HttpResponse(render_response_index(request, url, c))

@authz.experiment_access_required
def table(request, experiment_id):
    # http://datatables.net/usage/server-side

    experiment = Experiment.objects.get(pk=experiment_id)

    parameter_names = ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment).distinct()
    datafiles = Dataset_File.objects.filter(dataset__experiment=experiment)

    limit = int(request.GET['iDisplayLength'])
    offset = int(request.GET['iDisplayStart'])

    filter = request.GET['sSearch']

    filtered_datafiles = _filter(datafiles, filter)

    rows = []
    for df in filtered_datafiles[offset:offset+limit]:
        row = []
        row.append(df.filename)
        for pn in parameter_names:
            params = DatafileParameter.objects.filter(parameterset__dataset_file=df, name=pn)
            row.append(','.join([param.get() for param in params]))
        rows.append(row)

    resp = {}
    resp['sEcho'] = request.GET['sEcho']
    resp['aaData'] = rows
    resp['iTotalRecords'] = datafiles.count()
    resp['iTotalDisplayRecords'] = filtered_datafiles.count()
    return HttpResponse(json.dumps(resp), mimetype='application/json')

def _filter(datafile_queryset, filter):
    if len(filter) < 1:
        return datafile_queryset
    else:
        query = Q(filename__icontains=filter)
        query |= Q(datafileparameterset__datafileparameter__string_value__icontains=filter)
        query |= Q(datafileparameterset__datafileparameter__numerical_value__icontains=filter)
        return datafile_queryset.filter(query).distinct()
