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

    descs = [{'mDataProp': 'filename', 'sTitle': 'filename'}]
    for x in parameter_names:
        descs.append({'mDataProp': str(x.id), 'sTitle': x.name})
    c['joined'] = json.dumps(descs)
    c['experiment'] = experiment

    return HttpResponse(render_response_index(request, url, c))

@authz.experiment_access_required
def table(request, experiment_id):
    # http://datatables.net/usage/server-side
    logger.debug(request.GET)
    logger.debug(request.GET['sColumns'])
    if not int(request.GET['iSortingCols']) == 1:
        raise Exception('this should not happen')
    sort_col_index = request.GET['iSortCol_0']
    sort_col_name = request.GET['mDataProp_' + sort_col_index]
    sort_desc = request.GET['sSortDir_0'] == 'desc'

    experiment = Experiment.objects.get(pk=experiment_id)

    parameter_names = ParameterName.objects.filter(datafileparameter__parameterset__dataset_file__dataset__experiment=experiment).distinct()
    datafiles = Dataset_File.objects.filter(dataset__experiment=experiment)

    if sort_col_name == 'filename':
        if sort_desc:
            datafiles = datafiles.order_by('-filename')
        else:
            datafiles = datafiles.order_by('filename')
        post_filter = False
    else:
        datafiles = datafiles.order_by('filename')
        post_filter = True

    limit = int(request.GET['iDisplayLength'])
    offset = int(request.GET['iDisplayStart'])

    filter = request.GET['sSearch']

    filtered_datafiles = _filter(datafiles, filter)


    pndict = dict([[pn.id, pn] for pn in parameter_names])
    pn_ids = [x for x in pndict.keys()]

    dfs = [(x.id, x.filename) for x in filtered_datafiles[offset:offset+limit]]
    df_ids = [x[0] for x in dfs]
    dfdict = dict(dfs)

    name_ids = [pn.id for pn in parameter_names]

    dfps = DatafileParameter.objects.filter(parameterset__dataset_file__in=df_ids, name__in=name_ids).values('parameterset__dataset_file__id', 'name__id', 'numerical_value', 'datetime_value', 'string_value')

    params_by_file = {}
    for dfp in dfps:
        f_id = dfp['parameterset__dataset_file__id']
        n_id = dfp['name__id']
        if f_id not in params_by_file:
            params_by_file[f_id] = {}

        dfps_by_name = params_by_file[f_id]

        if n_id not in dfps_by_name:
            dfps_by_name[n_id] = []

        dfp_vals = {'datetime_value': dfp['datetime_value'], 'numerical_value': dfp['numerical_value'], 'string_value': dfp['string_value'] }
        dfps_by_name[n_id].append(dfp)

    rows = []
    for dft in dfs:
        df_id = dft[0]
        df_name = dft[1]

        row = {}
        row['filename'] = df_name
        for pn_id in pn_ids:
            row[str(pn_id)] = ''
            if post_filter:
                row['sortable'] = 0
        for pn_id, params in params_by_file[df_id].items():
            pn = pndict[pn_id]
            if pn.isString() or pn.isLongString():
                row[str(pn_id)] = ','.join([param['string_value'] for param in params])
            elif pn.isNumeric():
                row[str(pn_id)] = ','.join([str(param['numerical_value']) for param in params])
            elif pn.isDateTime():
                row[str(pn_id)] = ','.join([str(param['datetime_value']) for param in params])

            if post_filter and sort_col_name == str(pn.id):
                if len(params) > 0:
                    if pn.isString() or pn.isLongString():
                        row['sortable'] = sorted([x['string_value'] for x in params])[0]
                    elif pn.isNumeric():
                        row['sortable'] = sorted([x['numerical_value'] for x in params])[0]
                    elif pn.isDateTime():
                        row['sortable'] = sorted([x['datetime_value'] for x in params])[0]
                    else:
                        row['sortable'] = 0
        rows.append(row)

#    for df in filtered_datafiles[offset:offset+limit]:
#        row = {}
#        row['filename'] = df.filename
#        for pn in parameter_names:
#            params = DatafileParameter.objects.filter(parameterset__dataset_file=df, name=pn)
#            row[str(pn.id)] = ','.join([param.get() for param in params])
#            if post_filter and sort_col_name == str(pn.id):
#                if len(params) == 0:
#                    row['sortable'] = 0
#                else:
#                    if pn.isString() or pn.isLongString():
#                        row['sortable'] = sorted([x.string_value for x in params])[0]
#                    elif pn.isNumeric():
#                        row['sortable'] = sorted([x.numerical_value for x in params])[0]
#                    elif pn.isDateTime():
#                        row['sortable'] = sorted([x.datetime_value for x in params])[0]
#                    else:
#                        row['sortable'] = 0
#        rows.append(row)
    if post_filter:
        rows = sorted(rows, key=lambda x: x['sortable'], reverse=sort_desc)
        for row in rows:
            del row['sortable']

    resp = {}
    resp['sEcho'] = int(request.GET['sEcho'])
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
